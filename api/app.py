"""AI-guided form API with deterministic validation and persistent inquiry writes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
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
    llm_factory: Callable[[], LlmClient] = get_llm,
) -> FastAPI:
    demo_db = Path(__file__).resolve().parents[1] / "tmp" / "life_ai_demo.sqlite3"
    demo_now = lambda: datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)  # noqa: E731
    inquiry_repository = repository or SqliteInquiryRepository(demo_db, now=demo_now)
    group_buy_repository = group_buys or SqliteGroupBuyRepository(demo_db, now=demo_now)
    session_store: SessionStore = sessions or InMemorySessionStore()
    life_services = LifeServicesService(inquiry_repository, today=DEMO_TODAY)
    insights = InsightsService(today=DEMO_TODAY)
    community = CommunityService(group_buy_repository)
    life_services_catalog = list_catalog_services
    # 能力層：規劃器與 MCP server 共用這一份（ADR-0017）
    tool_registry = build_registry(services=life_services, group_buys=group_buy_repository, today=DEMO_TODAY)
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

    @application.post("/api/chat/message")
    def message(req: MsgReq) -> dict:
        stored = session_store.get(req.session_id)
        if stored is None:
            raise HTTPException(404, "工作階段不存在，請重新開始")
        live = _revive(stored)
        state = live.state
        text = req.message.strip()

        if state.submitted_id:
            record = life_services.get_inquiry(state.submitted_id)
            assert record is not None
            operation = {"type": "inquiry.created", "id": record["id"], "status": record["status"]}
            return {"reply": "諮詢單已建立。", "done": True, "operation": operation, "progress": _progress(live.session), "trace": []}

        if state.awaiting_confirm:
            if _is_confirmation(text):
                record = life_services.submit_inquiry(
                    form_id=live.form.id,
                    feedback_content=live.session.to_feedback_content(),
                    service_id=live.form.service_id,
                    account_id=req.account_id,
                )
                state.submitted_id = record["id"]
                _persist(live)
                operation = {"type": "inquiry.created", "id": record["id"], "status": record["status"]}
                return {
                    "reply": f"已建立諮詢單 {record['id']}，合作夥伴稍後會回覆報價。",
                    "done": True,
                    "awaiting_confirmation": False,
                    "operation": operation,
                    "progress": _progress(live.session),
                    "trace": [{"stage": "write", "tool": "submit_inquiry", "status": "completed", "result_id": record["id"]}],
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

    @application.post("/api/v1/intent/match")
    def match_intent(req: IntentReq) -> dict:
        """把口語需求判讀成一項服務；判讀不出時回 null，由介面退回服務目錄。"""
        match = IntentAgent(llm_factory()).match(req.need)
        return {"data": None if match is None else match.to_dict()}

    # --- 規劃器：LLM 規劃、規則執行（ADR-0017） ---

    def _context(req: PlanReq) -> ToolContext:
        return ToolContext(account_id=req.account_id, role=req.role, display_name=req.display_name)

    @application.get("/api/v1/assistant/tools")
    def list_tools(role: str = "user") -> dict:
        """目前身分可用的能力清單——與 MCP server 對外曝露的是同一份。"""
        return {"data": tool_registry.describe(role=role)}

    @application.post("/api/v1/assistant/plan")
    def create_plan(req: PlanReq) -> dict:
        """把一句話拆成計畫並執行唯讀步驟；寫入步驟留著等使用者確認。"""
        planner = Planner(llm_factory(), tool_registry)
        context = _context(req)
        plan = planner.execute(planner.plan(req.message, context), context)
        return {"data": plan.to_dict()}

    @application.post("/api/v1/assistant/plan/execute")
    def execute_plan(req: ExecutePlanReq) -> dict:
        """執行使用者已確認的寫入步驟。

        步驟由前端帶回，但**不信任前端**：每一步都重新過一次註冊表的驗證與角色檢查，
        所以偽造的步驟過不了這一關。
        """
        planner = Planner(llm_factory(), tool_registry)
        context = _context(req)
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
