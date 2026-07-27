"""Life-services application boundary.

FastAPI and the future `life-services` MCP server must call this service rather
than duplicating inquiry business rules in their transport adapters.
"""

from __future__ import annotations

from datetime import date

from core.forms import FormError, FormSession, service_catalog
from core.forms.dto import form_to_dict, service_to_dict, summarize_feedback
from core.inquiries import CONFIRMED, PENDING_QUOTE, QUOTED, InquiryRepository
from core.orders import SqliteOrderRepository

from .pricing import Quote, calculate_quote
from .service_search import search as search_catalog


class LifeServicesService:
    def __init__(
        self,
        inquiries: InquiryRepository,
        *,
        orders: SqliteOrderRepository | None = None,
        today: date | None = None,
    ) -> None:
        self.inquiries = inquiries
        self.orders = orders
        self.today = today or date.today()

    # ---- 服務目錄與題組（單一事實來源） -------------------------------

    def list_services(self) -> list[dict]:
        return [service_to_dict(service) for service in service_catalog.list_services()]

    def search_services(self, query: str, *, limit: int = 3) -> dict:
        return search_catalog(query, limit=limit)

    def get_service_form(self, service_id: str) -> dict | None:
        form = service_catalog.get_service_form(service_id)
        return None if form is None else form_to_dict(form, today=self.today)

    def quote(self, service_id: str, answers: dict | None = None) -> Quote:
        return calculate_quote(service_id, answers)

    # ---- 諮詢單與其生命週期 -------------------------------------------

    def submit_inquiry(
        self,
        *,
        form_id: int,
        feedback_content: dict,
        service_id: str | None = None,
        account_id: str | None = None,
    ) -> dict:
        """建立諮詢單，並存下可讀摘要供廠商檢視。"""
        summary: list[dict] = []
        if service_id:
            form = service_catalog.get_service_form(service_id)
            if form is not None:
                summary = summarize_feedback(form, feedback_content)
        return self.inquiries.create(
            form_id=form_id,
            feedback_content=feedback_content,
            service_id=service_id,
            account_id=account_id,
            summary=summary,
        )

    def submit_structured_inquiry(
        self, *, service_id: str, answers: dict, account_id: str
    ) -> dict:
        """外部 Agent 依題組欄位代碼送件；仍須走同一個題組引擎驗證。

        單選可傳穩定的 option value（如 ``medium``），服務層會映射到官方 option id；
        這讓 MCP 呼叫端不必自行保存資料庫流水號，同時不會繞過 schema 規則。
        """
        form, session = self._validated_session(service_id, answers)
        return self.submit_inquiry(
            form_id=form.id,
            feedback_content=session.to_feedback_content(),
            service_id=service_id,
            account_id=account_id,
        )

    def _validated_session(self, service_id: str, answers: dict):
        form = service_catalog.get_service_form(service_id)
        if form is None:
            raise FormError(f"沒有這項服務：{service_id}")
        session = FormSession(form, today=self.today)
        known_keys = {topic.key for topic in form.ordered_topics()}
        unknown = set(answers) - known_keys
        if unknown:
            raise FormError(f"不認識的欄位：{'、'.join(sorted(unknown))}")
        for topic in form.ordered_topics():
            if not session.is_visible(topic):
                continue
            if topic.key not in answers:
                if topic.is_required:
                    raise FormError(f"缺少必填欄位：{topic.key}（{topic.title}）")
                continue
            value = answers[topic.key]
            if topic.options:
                values = value if isinstance(value, list) else [value]
                mapped = []
                for raw in values:
                    lookup = raw
                    if isinstance(raw, dict):
                        lookup = raw.get("option_id", raw.get("optionId"))
                    option = next(
                        (item for item in topic.options if lookup in (item.id, item.value, item.option_name)),
                        None,
                    )
                    if option is None:
                        raise FormError(f"「{topic.title}」無此選項：{raw}")
                    mapped.append(
                        {"option_id": option.id, "quantity": raw.get("quantity")}
                        if isinstance(raw, dict) else option.id
                    )
                value = mapped if topic.type.value == "4" else mapped[0]
            session.submit_answer(topic.id, value)
        if not session.is_complete():
            missing = session.next_topic()
            raise FormError(f"缺少必填欄位：{missing.key if missing else 'unknown'}")
        return form, session

    def create_order(self, *, service_id: str, answers: dict, account_id: str) -> dict:
        if self.orders is None:
            raise ValueError("訂單服務尚未設定")
        form, session = self._validated_session(service_id, answers)
        if form.action.value != "order":
            raise ValueError("這項服務需要建立諮詢或預約，不是直接訂單")
        pricing_answers: dict = {}
        for topic in form.ordered_topics():
            value = session.answers.get(topic.id)
            if value is None:
                continue
            if topic.options:
                option_values = [topic.option(selection.option_id).value for selection in value]
                pricing_answers[topic.key] = option_values if topic.type.value == "4" else option_values[0]
            else:
                pricing_answers[topic.key] = value
        pricing = self.quote(service_id, pricing_answers).to_dict()
        return self.orders.create(
            account_id=account_id,
            service_id=service_id,
            answers=session.to_feedback_content(),
            pricing=pricing,
        )

    def get_order(self, order_id: str) -> dict | None:
        return None if self.orders is None else self.orders.get(order_id)

    def list_orders_for(self, account_id: str) -> list[dict]:
        return [] if self.orders is None else self.orders.list_for_account(account_id)

    def get_inquiry(self, inquiry_id: str) -> dict | None:
        return self.inquiries.get(inquiry_id)

    def list_inquiries(self) -> list[dict]:
        return self.inquiries.list_all()

    def list_inquiries_for(self, account_id: str) -> list[dict]:
        """住戶只看自己的委託（spec 08 驗收：看不到不屬於自己的資料）。"""
        return self.inquiries.list_for_account(account_id)

    def list_pending_for_vendor(self) -> list[dict]:
        """廠商待處理：等待報價的諮詢單。"""
        return self.inquiries.list_by_status(PENDING_QUOTE)

    def list_vendor_workload(self) -> dict:
        """廠商工作台一覽：待報價、待住戶確認、待履約。"""
        return {
            "pendingQuote": self.inquiries.list_by_status(PENDING_QUOTE),
            "awaitingResident": self.inquiries.list_by_status(QUOTED),
            "scheduled": self.inquiries.list_by_status(CONFIRMED),
        }

    def quote_inquiry(self, inquiry_id: str, *, items: list[dict], vendor_name: str) -> dict:
        return self.inquiries.add_quote(inquiry_id, items=items, vendor_name=vendor_name)

    def confirm_inquiry_quote(self, inquiry_id: str) -> dict:
        return self.inquiries.confirm_quote(inquiry_id)

    def request_quote_revision(self, inquiry_id: str, *, note: str) -> dict:
        """住戶請廠商重新報價（議價，或想換一家出價）。"""
        return self.inquiries.request_revision(inquiry_id, note=note)

    def cancel_inquiry(self, inquiry_id: str, *, reason: str | None = None) -> dict:
        """住戶取消委託；已確認之後不開放（廠商已排程）。"""
        return self.inquiries.cancel(inquiry_id, reason=reason)

    def complete_inquiry(self, inquiry_id: str, *, note: str | None = None) -> dict:
        return self.inquiries.complete(inquiry_id, note=note)
