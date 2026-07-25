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
from core.clients import LlmClient, get_llm
from core.forms import Form, FormError, FormSession
from core.forms.dto import topic_to_field
from core.forms.service_catalog import get_service as catalog_service
from core.forms.service_catalog import get_service_form as catalog_service_form
from core.forms.service_catalog import list_services as list_catalog_services
from core.inquiries import InquiryRepository, InquiryTransitionError, SqliteInquiryRepository
from core.services import InsightsService, LifeServicesService

DEMO_TODAY = date(2026, 7, 25)
_CONFIRM_WORDS = {"對", "好", "沒問題", "確認", "確認送出", "送出", "可以", "ok", "yes", "是", "嗯"}


@dataclass
class SessionState:
    form: Form
    session: FormSession
    agent: FormAgent
    awaiting_confirm: bool = False
    submitted_id: str | None = None


class StartReq(BaseModel):
    """以服務目錄的 service_id 開啟對話——與網頁表單讀同一份題組定義。"""

    service_id: str


class MsgReq(BaseModel):
    session_id: str
    message: str


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
    llm_factory: Callable[[], LlmClient] = get_llm,
) -> FastAPI:
    inquiry_repository = repository or SqliteInquiryRepository(
        Path(__file__).resolve().parents[1] / "tmp" / "life_ai_demo.sqlite3",
        now=lambda: datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc),
    )
    sessions: dict[str, SessionState] = {}
    life_services = LifeServicesService(inquiry_repository, today=DEMO_TODAY)
    insights = InsightsService(today=DEMO_TODAY)
    life_services_catalog = list_catalog_services
    application = FastAPI(title="智慧生活管家 AI API")

    @application.get("/api/forms")
    def list_forms() -> list[dict]:
        """沿用舊路徑：回傳可對話的服務（即服務目錄）。"""
        return [{"id": service.id, "name": service.name} for service in life_services_catalog()]

    def _question(state: SessionState, topic) -> dict | None:
        """把當前題目序列化成可渲染的形式，讓介面能畫成按鈕。"""
        return None if topic is None else topic_to_field(state.form, topic, today=DEMO_TODAY)

    @application.post("/api/chat/start")
    def start(req: StartReq) -> dict:
        service = catalog_service(req.service_id)
        form = catalog_service_form(req.service_id)
        if service is None or form is None:
            raise HTTPException(404, "查無服務")
        session = FormSession(form, today=DEMO_TODAY)
        agent = FormAgent(llm_factory(), today=DEMO_TODAY)
        session_id = uuid4().hex
        state = SessionState(form, session, agent)
        sessions[session_id] = state
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
            "question": _question(state, first),
            "done": first is None,
            "awaiting_confirmation": False,
            "progress": _progress(session),
            "trace": [{"stage": "tool", "tool": "get_service_form", "status": "completed"}],
        }

    @application.post("/api/chat/message")
    def message(req: MsgReq) -> dict:
        state = sessions.get(req.session_id)
        if state is None:
            raise HTTPException(404, "工作階段不存在，請重新開始")
        text = req.message.strip()

        if state.submitted_id:
            record = life_services.get_inquiry(state.submitted_id)
            assert record is not None
            operation = {"type": "inquiry.created", "id": record["id"], "status": record["status"]}
            return {"reply": "諮詢單已建立。", "done": True, "operation": operation, "progress": _progress(state.session), "trace": []}

        if state.awaiting_confirm:
            if _is_confirmation(text):
                record = life_services.submit_inquiry(
                    form_id=state.form.id,
                    feedback_content=state.session.to_feedback_content(),
                    service_id=state.form.service_id,
                )
                state.submitted_id = record["id"]
                operation = {"type": "inquiry.created", "id": record["id"], "status": record["status"]}
                return {
                    "reply": f"已建立諮詢單 {record['id']}，合作夥伴稍後會回覆報價。",
                    "done": True,
                    "awaiting_confirmation": False,
                    "operation": operation,
                    "progress": _progress(state.session),
                    "trace": [{"stage": "write", "tool": "submit_inquiry", "status": "completed", "result_id": record["id"]}],
                }
            return {
                "reply": "還沒送出。內容沒問題的話按「確認送出」，需要修改請告訴我要改哪一項。",
                "done": False,
                "awaiting_confirmation": True,
                "progress": _progress(state.session),
                "trace": [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
            }

        current = state.session.next_topic()
        if current is None:
            state.awaiting_confirm = True
            return {
                "reply": state.agent.summary_text(state.session.to_feedback_content()),
                "done": False,
                "awaiting_confirmation": True,
                "progress": _progress(state.session),
                "trace": [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
            }

        interpretation = state.agent.interpret(current, text)
        trace: list[dict[str, Any]] = [{
            "stage": "ai", "tool": "extract_form_answer", "status": "completed" if interpretation.action != "unclear" else "needs_retry",
            "topic_id": current.id,
        }]
        if interpretation.action == "unclear":
            return {
                "reply": f"{interpretation.note}\n{state.agent.question_text(current)}",
                "question": _question(state, current),
                "done": False,
                "awaiting_confirmation": False,
                "progress": _progress(state.session),
                "trace": trace,
            }
        try:
            if interpretation.action == "skip":
                state.session.skip(current.id)
            else:
                state.session.submit_answer(current.id, interpretation.value)
        except FormError as exc:
            trace.append({"stage": "rule", "tool": "validate_form_answer", "status": "rejected", "topic_id": current.id})
            return {
                "reply": f"{exc}\n{state.agent.question_text(current)}",
                "question": _question(state, current),
                "done": False,
                "awaiting_confirmation": False,
                "progress": _progress(state.session),
                "trace": trace,
            }

        trace.append({"stage": "rule", "tool": "validate_form_answer", "status": "completed", "topic_id": current.id})
        next_topic = state.session.next_topic()
        if next_topic is not None:
            return {
                "reply": state.agent.question_text(next_topic),
                "question": _question(state, next_topic),
                "done": False,
                "awaiting_confirmation": False,
                "extracted": {"topic_id": current.id, "action": interpretation.action, "value": jsonable_encoder(interpretation.value), "note": interpretation.note},
                "progress": _progress(state.session),
                "trace": trace,
            }
        state.awaiting_confirm = True
        return {
            "reply": state.agent.summary_text(state.session.to_feedback_content()),
            "done": False,
            "awaiting_confirmation": True,
            "extracted": {"topic_id": current.id, "action": interpretation.action, "value": jsonable_encoder(interpretation.value), "note": interpretation.note},
            "progress": _progress(state.session),
            "trace": trace + [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
        }

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
