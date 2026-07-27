"""Life-services application boundary.

FastAPI and the future `life-services` MCP server must call this service rather
than duplicating inquiry business rules in their transport adapters.
"""

from __future__ import annotations

from datetime import date

from core.forms import service_catalog
from core.forms.dto import form_to_dict, service_to_dict, summarize_feedback
from core.inquiries import CONFIRMED, PENDING_QUOTE, QUOTED, InquiryRepository

from .pricing import Quote, calculate_quote


class LifeServicesService:
    def __init__(self, inquiries: InquiryRepository, *, today: date | None = None) -> None:
        self.inquiries = inquiries
        self.today = today or date.today()

    # ---- 服務目錄與題組（單一事實來源） -------------------------------

    def list_services(self) -> list[dict]:
        return [service_to_dict(service) for service in service_catalog.list_services()]

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
