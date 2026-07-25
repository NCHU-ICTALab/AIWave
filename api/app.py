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
from core.clients import LlmClient, get_llm
from core.forms import Form, FormError, FormSession
from core.forms.seed_forms import facility_form, group_buy_form, repair_form
from core.inquiries import InquiryRepository, SqliteInquiryRepository
from core.services import InsightsService, LifeServicesService

DEMO_TODAY = date(2026, 7, 25)
FORMS: dict[str, tuple[str, Callable[[], Form]]] = {
    "repair": ("水電修繕諮詢", repair_form),
    "groupbuy": ("團購跟團（愛文芒果）", lambda: group_buy_form("愛文芒果", 5)),
    "facility": ("公設預約", facility_form),
}
_CONFIRM_WORDS = {"對", "好", "沒問題", "確認", "確認送出", "送出", "可以", "ok", "yes", "是", "嗯"}


@dataclass
class SessionState:
    form: Form
    session: FormSession
    agent: FormAgent
    awaiting_confirm: bool = False
    submitted_id: str | None = None


class StartReq(BaseModel):
    form_id: str


class MsgReq(BaseModel):
    session_id: str
    message: str


class QuoteReq(BaseModel):
    answers: dict[str, Any] = {}


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
    application = FastAPI(title="智慧生活管家 AI API")

    @application.get("/api/forms")
    def list_forms() -> list[dict]:
        return [{"id": key, "name": name} for key, (name, _) in FORMS.items()]

    @application.post("/api/chat/start")
    def start(req: StartReq) -> dict:
        if req.form_id not in FORMS:
            raise HTTPException(404, "無此題組")
        name, factory = FORMS[req.form_id]
        form = factory()
        session = FormSession(form, today=DEMO_TODAY)
        agent = FormAgent(llm_factory(), today=DEMO_TODAY)
        session_id = uuid4().hex
        sessions[session_id] = SessionState(form, session, agent)
        first = session.next_topic()
        reply = f"好的，我幫您處理「{name}」。\n{agent.question_text(first)}" if first else f"好的，我幫您處理「{name}」。"
        return {
            "session_id": session_id,
            "reply": reply,
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
                record = life_services.submit_inquiry(form_id=state.form.id, feedback_content=state.session.to_feedback_content())
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
                "reply": "尚未送出。若內容正確請輸入「確認送出」；需要修改時可回到服務表單調整。",
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
