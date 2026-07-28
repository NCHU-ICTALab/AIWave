"""AI-guided form API with deterministic validation and persistent inquiry writes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agent.form_agent import FormAgent
from agent.intent_agent import IntentAgent
from agent.planner import Plan, PlanStep, Planner
from core.clients import LlmClient, get_llm
from core.forms import Form, FormError, FormSession
from core.forms.dto import topic_to_field
from core.forms.service_catalog import get_service as catalog_service
from core.forms.service_catalog import get_service_form as catalog_service_form
from core.forms.service_catalog import list_services as list_catalog_services
from core.community import GroupBuyError, GroupBuyRepository, SqliteGroupBuyRepository
from core.inquiries import InquiryRepository, InquiryTransitionError, SqliteInquiryRepository
from core.personalization import PersonalizationService, SqlitePersonalizationRepository
from core.orders import SqliteOrderRepository
from core.retail import RetailService, SqliteRetailRepository
from core.support import SupportError, SupportRepository, SupportService, SqliteSupportRepository
from core.insights.today import build_briefing
from core.services import CommunityService, InsightsService, LifeServicesService
from core.sessions import ConversationState, InMemorySessionStore, SessionStore
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext

DEMO_TODAY = date(2026, 7, 25)
_CONFIRM_WORDS = {"對", "好", "沒問題", "確認", "確認送出", "送出", "可以", "ok", "yes", "是", "嗯"}


@dataclass
class LiveSession:
    """由 `ConversationState` 重建出來的請求內物件。

    只在單一請求存活；狀態一律回寫 `SessionStore`（[ADR-0018]）。
    `FormAgent` 無狀態、`FormSession` 可由既有答案重建，所以不需要跨請求保存物件。
    """

    state: ConversationState
    form: Form
    session: FormSession
    agent: FormAgent


class StartReq(BaseModel):
    """以服務目錄的 service_id 開啟對話——與網頁表單讀同一份題組定義。"""

    service_id: str


class MsgReq(BaseModel):
    session_id: str
    message: str
    #: 送出諮詢單時要記錄是誰的委託（住戶只能看到自己的單）
    account_id: str | None = None


class QuoteReq(BaseModel):
    answers: dict[str, Any] = {}


class OrderReq(QuoteReq):
    account_id: str


class IntentReq(BaseModel):
    need: str


class QuoteItem(BaseModel):
    name: str
    amount: int


class CreateQuoteReq(BaseModel):
    items: list[QuoteItem]
    vendor_name: str = "合作廠商"


class CompleteReq(BaseModel):
    note: str | None = None


class ReviseReq(BaseModel):
    """住戶請廠商重新報價；`note` 必填——沒說要改什麼，廠商只能重猜一次。"""

    note: str


class CancelReq(BaseModel):
    reason: str | None = None


class CreateCampaignReq(BaseModel):
    title: str
    item_name: str
    unit_price: int
    unit: str = "份"
    min_quantity: int = 1
    close_time: str | None = None
    pickup: str | None = None


class JoinCampaignReq(BaseModel):
    account_id: str
    display_name: str = "住戶"
    quantity: int = 1


class PlanReq(BaseModel):
    """一句口語 ＋ 呼叫者身分。身分由前端的登入狀態帶入，不由 LLM 決定。"""

    message: str
    account_id: str | None = None
    role: str = "user"
    display_name: str = "住戶"


class ExecutePlanReq(PlanReq):
    """執行計畫；`approved` 是使用者已點頭的寫入步驟索引。"""

    steps: list[dict] = []
    approved: list[int] = []


class RecommendationFeedbackReq(BaseModel):
    recommendation_id: str
    action: str


class ReminderReq(BaseModel):
    item_name: str
    cadence_days: int
    next_due_on: str


class StockWatchReq(BaseModel):
    account_id: str
    product_id: str
    store_id: str


class SupportIssueReq(BaseModel):
    subject_id: str
    issue_text: str


class SupportTicketReq(SupportIssueReq):
    diagnosis_token: str


class SupportActionReq(BaseModel):
    note: str | None = None


def _support_http_context(
    account_id: str | None = Header(default=None, alias="X-Account-Id"),
    role: str = Header(default="user", alias="X-Role"),
) -> ToolContext:
    """競賽 Web 的單一身分 seam；正式部署只需在此改驗 OIDC/session。

    客服 request body 不接受帳號、角色或稽核 actor，避免模型或表單參數直接指定他人身分。
    目前 header 由假登入 adapter 提供，因此仍不可視為正式公開部署的認證機制。
    """
    if role not in {"user", "manager", "partner"}:
        raise HTTPException(403, "未知的使用者角色")
    display_name = {"user": "住戶", "manager": "社區管理者", "partner": "合作廠商"}[role]
    return ToolContext(account_id=account_id, role=role, display_name=display_name)


def _require_support_role(context: ToolContext, role: str) -> str:
    if context.role != role:
        raise HTTPException(403, "目前身分無法使用這項客服能力")
    if role == "user" and not context.account_id:
        raise HTTPException(401, "請先登入住戶帳號")
    return context.account_id or ""


def _progress(session: FormSession) -> dict[str, int]:
    return session.progress()


def _is_confirmation(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized.startswith(("不", "不要", "取消", "修改")):
        return False
    return normalized in _CONFIRM_WORDS


def create_app(
    *,
    repository: InquiryRepository | None = None,
    group_buys: GroupBuyRepository | None = None,
    sessions: SessionStore | None = None,
    personalization_repository: SqlitePersonalizationRepository | None = None,
    retail_repository: SqliteRetailRepository | None = None,
    order_repository: SqliteOrderRepository | None = None,
    support_repository: SupportRepository | None = None,
    llm_factory: Callable[[], LlmClient] = get_llm,
) -> FastAPI:
    demo_db = Path(__file__).resolve().parents[1] / "tmp" / "life_ai_demo.sqlite3"
    demo_now = lambda: datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)  # noqa: E731
    inquiry_repository = repository or SqliteInquiryRepository(demo_db, now=demo_now)
    group_buy_repository = group_buys or SqliteGroupBuyRepository(demo_db, now=demo_now)
    session_store: SessionStore = sessions or InMemorySessionStore()
    life_services = LifeServicesService(
        inquiry_repository,
        orders=order_repository or SqliteOrderRepository(demo_db, now=demo_now),
        today=DEMO_TODAY,
    )
    insights = InsightsService(today=DEMO_TODAY)
    community = CommunityService(group_buy_repository)
    personalization = PersonalizationService(
        personalization_repository or SqlitePersonalizationRepository(demo_db, now=demo_now),
        today=DEMO_TODAY,
    )
    retail = RetailService(retail_repository or SqliteRetailRepository(demo_db, now=demo_now))
    support = SupportService(
        support_repository or SqliteSupportRepository(demo_db, now=demo_now),
        inquiries=inquiry_repository,
        orders=life_services.orders,
        now=demo_now,
    )
    life_services_catalog = list_catalog_services
    # 能力層：規劃器與 MCP server 共用這一份（ADR-0017）
    tool_registry = build_registry(
        services=life_services,
        group_buys=group_buy_repository,
        personalization=personalization,
        retail=retail,
        support=support,
        today=DEMO_TODAY,
    )
    application = FastAPI(title="智慧生活管家 AI API")

    @application.get("/api/forms")
    def list_forms() -> list[dict]:
        """沿用舊路徑：回傳可對話的服務（即服務目錄）。"""
        return [{"id": service.id, "name": service.name} for service in life_services_catalog()]

    def _question(live: LiveSession, topic) -> dict | None:
        """把當前題目序列化成可渲染的形式，讓介面能畫成按鈕。"""
        return None if topic is None else topic_to_field(live.form, topic, today=DEMO_TODAY)

    def _revive(state: ConversationState) -> LiveSession:
        """由儲存的狀態重建這次請求要用的物件。"""
        form = catalog_service_form(state.service_id)
        if form is None:
            raise HTTPException(404, "查無服務")
        session = FormSession(form, today=DEMO_TODAY, known=dict(state.answers))
        for topic_id in state.skipped:
            # 略過紀錄要一併還原，否則重建後又會問一次已經略過的題目
            session.mark_skipped(topic_id)
        return LiveSession(state=state, form=form, session=session, agent=FormAgent(llm_factory(), today=DEMO_TODAY))

    def _persist(live: LiveSession) -> None:
        """把狀態寫回儲存層。

        刻意**不**存 `session.answers`——那裡放的是驗證後的 `Selection` 物件，
        序列化不了。狀態保存的是使用者/AI 提供的原始答案，重建時重新走一次
        `submit_answer` 驗證。這樣規則永遠是權威，也不會有「存進去的值繞過了驗證」。
        """
        live.state.skipped = sorted(live.session.skipped_ids)
        session_store.save(live.state)

    @application.post("/api/chat/start")
    def start(req: StartReq) -> dict:
        service = catalog_service(req.service_id)
        form = catalog_service_form(req.service_id)
        if service is None or form is None:
            raise HTTPException(404, "查無服務")
        session_id = uuid4().hex
        state = ConversationState(session_id=session_id, service_id=req.service_id)
        live = _revive(state)
        session, agent = live.session, live.agent
        _persist(live)
        first = session.next_topic()
        reply = (
            f"好的，我幫您安排「{service.name}」。\n{agent.question_text(first)}"
            if first else f"好的，我幫您安排「{service.name}」。"
        )
        return {
            "session_id": session_id,
            "service_id": service.id,
            "service_name": service.name,
            "reply": reply,
            "question": _question(live, first),
            "done": first is None,
            "awaiting_confirmation": False,
            "progress": _progress(session),
            "trace": [{"stage": "tool", "tool": "get_service_form", "status": "completed"}],
        }

    def _message_payload(req: MsgReq) -> dict:
        stored = session_store.get(req.session_id)
        if stored is None:
            raise HTTPException(404, "工作階段不存在，請重新開始")
        live = _revive(stored)
        state = live.state
        text = req.message.strip()

        if state.submitted_id:
            is_order = state.submitted_id.startswith("ORD-")
            record = life_services.get_order(state.submitted_id) if is_order else life_services.get_inquiry(state.submitted_id)
            assert record is not None
            operation = {"type": "order.created" if is_order else "inquiry.created", "id": record["id"], "status": record["status"]}
            return {"reply": "訂單已建立。" if is_order else "諮詢單已建立。", "done": True, "operation": operation, "progress": _progress(live.session), "trace": []}

        if state.awaiting_confirm:
            if _is_confirmation(text):
                is_order = live.form.action.value == "order"
                if is_order and not req.account_id:
                    raise HTTPException(401, "建立訂單前請先登入")
                if is_order:
                    keyed_answers = {
                        topic.key: state.answers[topic.id]
                        for topic in live.form.ordered_topics()
                        if topic.id in state.answers
                    }
                    record = life_services.create_order(
                        service_id=live.form.service_id,
                        answers=keyed_answers,
                        account_id=req.account_id,
                    )
                else:
                    record = life_services.submit_inquiry(
                        form_id=live.form.id,
                        feedback_content=live.session.to_feedback_content(),
                        service_id=live.form.service_id,
                        account_id=req.account_id,
                    )
                state.submitted_id = record["id"]
                _persist(live)
                operation = {"type": "order.created" if is_order else "inquiry.created", "id": record["id"], "status": record["status"]}
                return {
                    "reply": (
                        f"已建立訂單 {record['id']}，應付 NT${record['amount']:,}，可到訂單頁追蹤。"
                        if is_order else f"已建立諮詢單 {record['id']}，合作夥伴稍後會回覆報價。"
                    ),
                    "done": True,
                    "awaiting_confirmation": False,
                    "operation": operation,
                    "progress": _progress(live.session),
                    "trace": [{"stage": "write", "tool": "create_order" if is_order else "submit_inquiry", "status": "completed", "result_id": record["id"]}],
                }
            return {
                "reply": "還沒送出。內容沒問題的話按「確認送出」，需要修改請告訴我要改哪一項。",
                "done": False,
                "awaiting_confirmation": True,
                "progress": _progress(live.session),
                "trace": [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
            }

        current = live.session.next_topic()
        if current is None:
            state.awaiting_confirm = True
            _persist(live)
            return {
                "reply": live.agent.summary_text(live.session.to_feedback_content()),
                "done": False,
                "awaiting_confirmation": True,
                "progress": _progress(live.session),
                "trace": [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
            }

        interpretation = live.agent.interpret(current, text)
        trace: list[dict[str, Any]] = [{
            "stage": "ai", "tool": "extract_form_answer", "status": "completed" if interpretation.action != "unclear" else "needs_retry",
            "topic_id": current.id,
        }]
        if interpretation.action == "unclear":
            return {
                "reply": f"{interpretation.note}\n{live.agent.question_text(current)}",
                "question": _question(live, current),
                "done": False,
                "awaiting_confirmation": False,
                "progress": _progress(live.session),
                "trace": trace,
            }
        try:
            if interpretation.action == "skip":
                live.session.skip(current.id)
            else:
                live.session.submit_answer(current.id, interpretation.value)
                # 通過驗證才記錄；記的是原始值，重建時會再驗一次
                state.answers[current.id] = jsonable_encoder(interpretation.value)
        except FormError as exc:
            trace.append({"stage": "rule", "tool": "validate_form_answer", "status": "rejected", "topic_id": current.id})
            return {
                "reply": f"{exc}\n{live.agent.question_text(current)}",
                "question": _question(live, current),
                "done": False,
                "awaiting_confirmation": False,
                "progress": _progress(live.session),
                "trace": trace,
            }

        trace.append({"stage": "rule", "tool": "validate_form_answer", "status": "completed", "topic_id": current.id})
        next_topic = live.session.next_topic()
        if next_topic is not None:
            _persist(live)
            return {
                "reply": live.agent.question_text(next_topic),
                "question": _question(live, next_topic),
                "done": False,
                "awaiting_confirmation": False,
                "extracted": {"topic_id": current.id, "action": interpretation.action, "value": jsonable_encoder(interpretation.value), "note": interpretation.note},
                "progress": _progress(live.session),
                "trace": trace,
            }
        state.awaiting_confirm = True
        _persist(live)
        return {
            "reply": live.agent.summary_text(live.session.to_feedback_content()),
            "done": False,
            "awaiting_confirmation": True,
            "extracted": {"topic_id": current.id, "action": interpretation.action, "value": jsonable_encoder(interpretation.value), "note": interpretation.note},
            "progress": _progress(live.session),
            "trace": trace + [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
        }

    @application.post("/api/chat/message")
    def message(req: MsgReq) -> dict:
        """非串流相容端點；LINE／既有 client 仍可一次取得完整結果。"""
        return _message_payload(req)

    @application.post("/api/chat/message/stream")
    def message_stream(req: MsgReq) -> StreamingResponse:
        """以 NDJSON 回報安全的處理階段、文字增量與最終結構化狀態。"""
        if session_store.get(req.session_id) is None:
            raise HTTPException(404, "工作階段不存在，請重新開始")

        def encode(event: dict[str, Any]) -> str:
            return json.dumps(jsonable_encoder(event), ensure_ascii=False) + "\n"

        def events():
            # 第一個 event 在進入同步 LLM 判讀前送出，避免畫面長時間沒有回應。
            yield encode({"type": "status", "label": "正在理解你的回答"})
            payload = _message_payload(req)
            yield encode({"type": "status", "label": "正在整理回覆"})
            reply = str(payload.get("reply") or "")
            for offset in range(0, len(reply), 8):
                yield encode({"type": "delta", "text": reply[offset : offset + 8]})
            yield encode({"type": "complete", "data": payload})

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.get("/healthz")
    def healthz() -> dict:
        """負載平衡器的健康檢查端點。

        只回報「這個執行單元活著」，不去戳資料庫或 LLM——健康檢查若依賴外部服務，
        一次下游抖動就會讓 ALB 把好好的實例整批換掉。
        """
        return {"status": "ok"}

    @application.get("/api/v1/services")
    def list_services() -> dict:
        """服務目錄——前端與 MCP 共用的單一來源。"""
        return {"data": life_services.list_services()}

    @application.get("/api/v1/services/search")
    def search_services(q: str, limit: int = 3) -> dict:
        """以規則檢索相關服務；零分項目不進候選，避免整份目錄冒充意圖辨識。"""
        return {"data": life_services.search_services(q, limit=limit)}

    @application.get("/api/v1/services/{service_id}/form")
    def get_service_form(service_id: str) -> dict:
        """該服務的題組定義（已把相對日期換算成絕對日期）。"""
        definition = life_services.get_service_form(service_id)
        if definition is None:
            raise HTTPException(404, "查無服務")
        return {"data": definition}

    @application.post("/api/v1/services/{service_id}/quote")
    def quote_service(service_id: str, req: QuoteReq) -> dict:
        """依填答試算金額與折抵（業務規則在後端，跨通路一致）。"""
        if life_services.get_service_form(service_id) is None:
            raise HTTPException(404, "查無服務")
        return {"data": life_services.quote(service_id, req.answers).to_dict()}

    @application.post("/api/v1/services/{service_id}/orders")
    def create_service_order(service_id: str, req: OrderReq) -> dict:
        try:
            return {"data": life_services.create_order(
                service_id=service_id, answers=req.answers, account_id=req.account_id
            )}
        except (FormError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.get("/api/v1/orders")
    def list_platform_orders(account_id: str) -> dict:
        return {"data": life_services.list_orders_for(account_id)}

    @application.get("/api/v1/orders/{order_id}")
    def get_platform_order(order_id: str, account_id: str) -> dict:
        record = life_services.get_order(order_id)
        # 競賽版仍是假登入；至少不允許只猜流水號就讀到不同帳號的訂單。
        if record is None or record["accountId"] != account_id:
            raise HTTPException(404, "查無訂單")
        return {"data": record}

    @application.post("/api/v1/intent/match")
    def match_intent(req: IntentReq) -> dict:
        """把口語需求判讀成一項服務；判讀不出時回 null，由介面退回服務目錄。"""
        match = IntentAgent(llm_factory()).match(req.need)
        return {"data": None if match is None else match.to_dict()}

    # --- 規劃器：LLM 規劃、規則執行（ADR-0017） ---

    @application.get("/api/v1/assistant/tools")
    def list_tools(context: ToolContext = Depends(_support_http_context)) -> dict:
        """目前身分可用的能力清單——與 MCP server 對外曝露的是同一份。"""
        return {"data": tool_registry.describe(role=context.role)}

    @application.post("/api/v1/assistant/plan")
    def create_plan(req: PlanReq, context: ToolContext = Depends(_support_http_context)) -> dict:
        """把一句話拆成計畫並執行唯讀步驟；寫入步驟留著等使用者確認。"""
        planner = Planner(llm_factory(), tool_registry)
        plan = planner.execute(planner.plan(req.message, context), context)
        return {"data": plan.to_dict()}

    @application.post("/api/v1/assistant/plan/execute")
    def execute_plan(req: ExecutePlanReq, context: ToolContext = Depends(_support_http_context)) -> dict:
        """執行使用者已確認的寫入步驟。

        步驟由前端帶回，但**不信任前端**：每一步都重新過一次註冊表的驗證與角色檢查，
        所以偽造的步驟過不了這一關。
        """
        planner = Planner(llm_factory(), tool_registry)
        plan = Plan(understanding=req.message)
        for raw in req.steps:
            tool = tool_registry.get(raw.get("tool"))
            if tool is None or not tool.allows(context.role):
                raise HTTPException(400, f"無法執行的步驟：{raw.get('tool')}")
            plan.steps.append(
                PlanStep(
                    tool=tool.name,
                    arguments=raw.get("arguments") or {},
                    why=str(raw.get("why") or ""),
                    writes=tool.writes,
                    status="needs_confirmation" if tool.writes else "ready",
                )
            )
        return {"data": planner.execute(plan, context, approved=set(req.approved)).to_dict()}

    @application.get("/api/v1/match/{service_id}")
    def match_vendors(
        service_id: str,
        district: str | None = None,
        county: str | None = None,
        budget: int | None = None,
        slot: str | None = None,
        urgent: bool = False,
    ) -> dict:
        """服務媒合（FR-S-04）：依地區／時段／預算／緊急程度／評分列 2–3 家比較。"""
        try:
            result = tool_registry.call(
                "match_vendors",
                {
                    "service_id": service_id,
                    "district": district,
                    "county": county,
                    "budget": budget,
                    "slot": slot,
                    "urgent": urgent,
                },
                ToolContext(),
            )
        except Exception as error:  # noqa: BLE001
            raise HTTPException(404, str(error)) from error
        return {"data": result}

    # --- 個人洞察：全部由官方 mms_order_record 算出 ---

    @application.get("/api/v1/insights/accounts")
    def list_insight_accounts() -> dict:
        return {"data": insights.accounts()}

    @application.get("/api/v1/insights/{account_id}/summary")
    def insight_summary(account_id: str) -> dict:
        """消費與跨服務摘要；`me` 解析為展示 persona。"""
        return {"data": insights.summary(account_id)}

    @application.get("/api/v1/insights/{account_id}/trail")
    def insight_trail(account_id: str) -> dict:
        """行為軌跡：跨服務、跨時間的事件序列。"""
        return {"data": insights.trail(account_id)}

    @application.get("/api/v1/insights/{account_id}/recommendations")
    def insight_recommendations(account_id: str, limit: int = 3) -> dict:
        """可解釋推薦：規則產生，每則附官方訂單證據。"""
        return {"data": insights.recommendations(account_id, limit=limit)}

    @application.get("/api/v1/today/{account_id}")
    def today_briefing(account_id: str, limit: int = 5) -> dict:
        """今日摘要：由真實待辦與行為軌跡彙整，規則產生（非 LLM 生成）。"""
        resolved = None if account_id in ("", "none", "null") else account_id
        items = build_briefing(
            account_id=resolved,
            inquiries=life_services.list_inquiries(),
            campaigns=community.list_open_campaigns(),
            today=DEMO_TODAY,
            limit=limit,
        )
        if resolved:
            items = [
                item for item in items
                if item.kind != "suggestion" or not personalization.is_suppressed(resolved, item.source)
            ]
        return {"data": [item.to_dict() for item in items]}

    # --- 個人化補貨：官方行為證據＋競賽 seed 帳本＋可撤回偏好 ---

    @application.get("/api/v1/personalization/{account_id}/restock-plan")
    def restock_plan(account_id: str) -> dict:
        return {"data": personalization.restock_plan(account_id)}

    @application.post("/api/v1/personalization/{account_id}/feedback")
    def recommendation_feedback(account_id: str, req: RecommendationFeedbackReq) -> dict:
        try:
            return {"data": personalization.feedback(account_id, req.recommendation_id, req.action)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.get("/api/v1/personalization/{account_id}/reminders")
    def list_personal_reminders(account_id: str) -> dict:
        return {"data": personalization.list_reminders(account_id)}

    @application.post("/api/v1/personalization/{account_id}/reminders")
    def create_personal_reminder(account_id: str, req: ReminderReq) -> dict:
        try:
            return {"data": personalization.create_reminder(
                account_id,
                item_name=req.item_name,
                cadence_days=req.cadence_days,
                next_due_on=req.next_due_on,
            )}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    # --- 超商生態：能力／庫存、替代門市與候補 ---

    @application.get("/api/v1/retail/stores/search")
    def retail_search(q: str, district: str | None = None, capability: str | None = None) -> dict:
        try:
            return {"data": retail.search(query=q, district=district, capability=capability)}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.get("/api/v1/retail/stock-watches")
    def list_stock_watches(account_id: str) -> dict:
        return {"data": retail.list_watches(account_id)}

    @application.post("/api/v1/retail/stock-watches")
    def join_stock_watch(req: StockWatchReq) -> dict:
        try:
            return {"data": retail.join_waitlist(
                req.account_id, product_id=req.product_id, store_id=req.store_id
            )}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    # --- 訂單異常與客服：診斷預覽 → 人確認 → 工單與處理事件 ---

    @application.post("/api/v1/support/diagnose")
    def diagnose_support_issue(
        req: SupportIssueReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": support.diagnose(
                account_id=account_id, subject_id=req.subject_id, issue_text=req.issue_text
            )}
        except SupportError as exc:
            status_code = 404 if "查無" in str(exc) else 400
            raise HTTPException(status_code, str(exc)) from exc

    @application.post("/api/v1/support/tickets")
    def create_support_ticket(
        req: SupportTicketReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": support.create_ticket(
                account_id=account_id, subject_id=req.subject_id, issue_text=req.issue_text,
                diagnosis_token=req.diagnosis_token,
            )}
        except SupportError as exc:
            status_code = 404 if "查無" in str(exc) else 409
            raise HTTPException(status_code, str(exc)) from exc

    @application.get("/api/v1/support/tickets")
    def list_support_tickets(context: ToolContext = Depends(_support_http_context)) -> dict:
        return {"data": support.list_for_account(_require_support_role(context, "user"))}

    @application.get("/api/v1/support/queue")
    def list_support_queue(context: ToolContext = Depends(_support_http_context)) -> dict:
        _require_support_role(context, "manager")
        return {"data": support.list_queue()}

    @application.post("/api/v1/support/tickets/{ticket_id}/start")
    def start_support_ticket(
        ticket_id: str,
        req: SupportActionReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": support.start_ticket(ticket_id, actor=context.display_name)}
        except SupportError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/support/tickets/{ticket_id}/resolve")
    def resolve_support_ticket(
        ticket_id: str,
        req: SupportActionReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": support.resolve_ticket(ticket_id, actor=context.display_name, note=req.note or "")}
        except SupportError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.get("/api/v1/inquiries")
    def list_inquiries() -> dict:
        return {"data": life_services.list_inquiries()}

    @application.get("/api/v1/inquiries/{inquiry_id}")
    def get_inquiry(inquiry_id: str) -> dict:
        record = life_services.get_inquiry(inquiry_id)
        if record is None:
            raise HTTPException(404, "查無諮詢單")
        return {"data": record}

    # --- 社區團購：住戶與管委會看同一批資料，可做的動作不同 ---

    @application.get("/api/v1/community/campaigns")
    def list_campaigns(only_open: bool = False) -> dict:
        return {"data": community.list_open_campaigns() if only_open else community.list_all_campaigns()}

    @application.post("/api/v1/community/campaigns")
    def create_campaign(req: CreateCampaignReq) -> dict:
        """【管委會】開團。"""
        return {"data": community.create_campaign(**req.model_dump())}

    @application.post("/api/v1/community/campaigns/{campaign_id}/join")
    def join_campaign(campaign_id: int, req: JoinCampaignReq) -> dict:
        """【住戶】跟團。"""
        try:
            return {"data": community.join_campaign(
                campaign_id, account_id=req.account_id, display_name=req.display_name, quantity=req.quantity,
            )}
        except GroupBuyError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/community/campaigns/{campaign_id}/close")
    def close_campaign(campaign_id: int) -> dict:
        """【管委會】結單，並產出給廠商的採購彙總。"""
        try:
            campaign = community.close_campaign(campaign_id)
        except GroupBuyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"data": {"campaign": campaign, "purchaseOrder": community.purchase_order(campaign_id)}}

    @application.get("/api/v1/community/my-participation")
    def my_participation(account_id: str) -> dict:
        return {"data": community.my_participation(account_id)}

    # --- 諮詢單生命週期：住戶送出 → 廠商報價 → 住戶確認 → 廠商完工 ---

    @application.get("/api/v1/vendor/workload")
    def vendor_workload() -> dict:
        """廠商工作台：真的來自住戶送出的諮詢單，而非固定展示資料。"""
        return {"data": life_services.list_vendor_workload()}

    @application.post("/api/v1/inquiries/{inquiry_id}/quote")
    def create_quote(inquiry_id: str, req: CreateQuoteReq) -> dict:
        """【廠商】開立報價 → 住戶會在訂單頁看到並可確認。"""
        try:
            record = life_services.quote_inquiry(
                inquiry_id,
                items=[item.model_dump() for item in req.items],
                vendor_name=req.vendor_name,
            )
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"data": record}

    @application.post("/api/v1/inquiries/{inquiry_id}/confirm")
    def confirm_quote(inquiry_id: str) -> dict:
        """【住戶】同意報價。"""
        try:
            return {"data": life_services.confirm_inquiry_quote(inquiry_id)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/inquiries/{inquiry_id}/revise")
    def request_revision(inquiry_id: str, req: ReviseReq) -> dict:
        """【住戶】請廠商重新報價（議價，或想換一家出價）。"""
        try:
            return {"data": life_services.request_quote_revision(inquiry_id, note=req.note)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/inquiries/{inquiry_id}/cancel")
    def cancel_inquiry(inquiry_id: str, req: CancelReq) -> dict:
        """【住戶】取消委託。已確認之後不開放——廠商已排程，那需要協調。"""
        try:
            return {"data": life_services.cancel_inquiry(inquiry_id, reason=req.reason)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/inquiries/{inquiry_id}/complete")
    def complete_inquiry(inquiry_id: str, req: CompleteReq) -> dict:
        """【廠商】回報完工。"""
        try:
            return {"data": life_services.complete_inquiry(inquiry_id, note=req.note)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.get("/", response_class=HTMLResponse)
    def index() -> str:
        """API 根路徑。使用者介面在 Vue 應用（`web/app`），不由此服務。"""
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<title>AI 生活服務平台 API</title>"
            "<h1>AI 生活服務平台 API</h1>"
            "<p>這是後端 API。使用者介面請執行 <code>web/app</code>（<code>npm run dev</code>）。</p>"
            "<p><a href='/docs'>API 文件</a></p>"
        )

    return application


app = create_app()
