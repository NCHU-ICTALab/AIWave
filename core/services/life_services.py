"""Life-services application boundary.

FastAPI and the future `life-services` MCP server must call this service rather
than duplicating inquiry business rules in their transport adapters.
"""

from __future__ import annotations

from datetime import date

from core.forms import service_catalog
from core.forms.dto import form_to_dict, service_to_dict
from core.inquiries import InquiryRepository

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

    # ---- 諮詢單 -------------------------------------------------------

    def submit_inquiry(self, *, form_id: int, feedback_content: dict) -> dict:
        return self.inquiries.create(form_id=form_id, feedback_content=feedback_content)

    def get_inquiry(self, inquiry_id: str) -> dict | None:
        return self.inquiries.get(inquiry_id)

    def list_inquiries(self) -> list[dict]:
        return self.inquiries.list_all()
