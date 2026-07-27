"""住戶收到報價後的選擇。

先前住戶只有「同意」一條路——那不是流程設計，是缺漏。真實情況下住戶會嫌貴、
會想換一家、會乾脆不修了。這裡驗證三條路都走得通，而且該擋的仍然擋著。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import (
    CANCELLED,
    COMPLETED,
    CONFIRMED,
    PENDING_QUOTE,
    QUOTED,
    InquiryTransitionError,
    SqliteInquiryRepository,
)
from core.services import LifeServicesService

FEEDBACK = {"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "燈具／開關", "answerId": 1071}]}]}
QUOTE_ITEMS = [{"name": "材料費", "amount": 300}, {"name": "施工費", "amount": 900}]
ME = "A001"


@pytest.fixture
def repository(tmp_path: Path) -> SqliteInquiryRepository:
    return SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3", now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)
    )


@pytest.fixture
def services(repository: SqliteInquiryRepository) -> LifeServicesService:
    return LifeServicesService(repository, today=date(2026, 7, 25))


def _quoted(services: LifeServicesService) -> str:
    """做出一張「已報價、待住戶決定」的單。"""
    record = services.submit_inquiry(
        form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id=ME
    )
    services.quote_inquiry(record["id"], items=QUOTE_ITEMS, vendor_name="速修水電")
    return record["id"]


class TestRequestRevision:
    def test_sends_the_case_back_for_a_new_quote(self, services):
        inquiry_id = _quoted(services)

        record = services.request_quote_revision(inquiry_id, note="預算希望壓在 1000 以內")

        assert record["status"] == PENDING_QUOTE
        assert record["quote"] is None, "舊報價要清掉，強迫廠商真的重新出價"

    def test_keeps_the_old_quote_in_the_history(self, services):
        """第二次報價不能只是重猜——廠商要看得到上次報多少、為什麼被退。"""
        inquiry_id = _quoted(services)

        record = services.request_quote_revision(inquiry_id, note="太貴了")

        event = next(e for e in record["events"] if e["type"] == "quote.revision_requested")
        assert "速修水電" in event["detail"]
        assert "1200" in event["detail"]
        assert "太貴了" in event["detail"]

    def test_the_vendor_can_quote_again_afterwards(self, services):
        inquiry_id = _quoted(services)
        services.request_quote_revision(inquiry_id, note="太貴了")

        record = services.quote_inquiry(inquiry_id, items=[{"name": "施工費", "amount": 800}], vendor_name="冠家水電")

        assert record["status"] == QUOTED
        assert record["quote"]["amount"] == 800
        assert record["quote"]["vendorName"] == "冠家水電"

    def test_requires_a_reason(self, services):
        """沒說要改什麼，廠商只能重猜一次——那對雙方都是浪費。"""
        inquiry_id = _quoted(services)

        with pytest.raises(InquiryTransitionError, match="說明"):
            services.request_quote_revision(inquiry_id, note="   ")

    def test_cannot_renegotiate_after_confirming(self, services):
        inquiry_id = _quoted(services)
        services.confirm_inquiry_quote(inquiry_id)

        with pytest.raises(InquiryTransitionError):
            services.request_quote_revision(inquiry_id, note="反悔了")


class TestCancel:
    def test_can_cancel_while_waiting_for_a_quote(self, services):
        record = services.submit_inquiry(
            form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id=ME
        )

        cancelled = services.cancel_inquiry(record["id"], reason="自己修好了")

        assert cancelled["status"] == CANCELLED
        assert cancelled["official_status"] == "90"

    def test_can_cancel_after_seeing_a_quote(self, services):
        inquiry_id = _quoted(services)
        assert services.cancel_inquiry(inquiry_id, reason="太貴")["status"] == CANCELLED

    def test_records_the_reason(self, services):
        inquiry_id = _quoted(services)
        record = services.cancel_inquiry(inquiry_id, reason="決定不修了")

        event = next(e for e in record["events"] if e["type"] == "inquiry.cancelled")
        assert event["detail"] == "決定不修了"

    def test_cannot_cancel_once_the_vendor_is_scheduled(self, services):
        """已確認之後廠商已排程；給一個看起來能按的取消鈕反而是騙人。"""
        inquiry_id = _quoted(services)
        services.confirm_inquiry_quote(inquiry_id)

        with pytest.raises(InquiryTransitionError):
            services.cancel_inquiry(inquiry_id)

    def test_a_cancelled_case_is_terminal(self, services):
        inquiry_id = _quoted(services)
        services.cancel_inquiry(inquiry_id)

        with pytest.raises(InquiryTransitionError):
            services.confirm_inquiry_quote(inquiry_id)
        with pytest.raises(InquiryTransitionError):
            services.quote_inquiry(inquiry_id, items=QUOTE_ITEMS, vendor_name="別家")


class TestVendorWorkload:
    def test_a_case_sent_back_reappears_in_the_vendor_queue(self, services):
        """退回重報之後，廠商工作台要重新看得到它，否則單子就人間蒸發了。"""
        inquiry_id = _quoted(services)
        services.request_quote_revision(inquiry_id, note="太貴")

        workload = services.list_vendor_workload()
        assert any(record["id"] == inquiry_id for record in workload["pendingQuote"])

    def test_a_cancelled_case_leaves_the_vendor_queue(self, services):
        inquiry_id = _quoted(services)
        services.cancel_inquiry(inquiry_id)

        workload = services.list_vendor_workload()
        everything = workload["pendingQuote"] + workload["awaitingResident"] + workload["scheduled"]
        assert not [record for record in everything if record["id"] == inquiry_id]


class TestApi:
    @pytest.fixture
    def client(self, repository) -> TestClient:
        return TestClient(create_app(repository=repository))

    def test_exposes_all_three_choices(self, client, services):
        inquiry_id = _quoted(services)

        revised = client.post(f"/api/v1/inquiries/{inquiry_id}/revise", json={"note": "希望便宜一點"})
        assert revised.status_code == 200
        assert revised.json()["data"]["status"] == PENDING_QUOTE

        services.quote_inquiry(inquiry_id, items=QUOTE_ITEMS, vendor_name="速修水電")
        cancelled = client.post(f"/api/v1/inquiries/{inquiry_id}/cancel", json={"reason": "不用了"})
        assert cancelled.status_code == 200
        assert cancelled.json()["data"]["status"] == CANCELLED

    def test_reports_a_conflict_rather_than_silently_ignoring(self, client, services):
        inquiry_id = _quoted(services)
        services.confirm_inquiry_quote(inquiry_id)

        assert client.post(f"/api/v1/inquiries/{inquiry_id}/cancel", json={}).status_code == 409
        assert client.post(f"/api/v1/inquiries/{inquiry_id}/revise", json={"note": "x"}).status_code == 409

    def test_the_whole_loop_still_reaches_completion(self, client, services):
        """新增的分支不能把原本的正向流程弄壞。"""
        inquiry_id = _quoted(services)
        client.post(f"/api/v1/inquiries/{inquiry_id}/revise", json={"note": "便宜點"})
        services.quote_inquiry(inquiry_id, items=[{"name": "施工", "amount": 800}], vendor_name="冠家水電")

        assert client.post(f"/api/v1/inquiries/{inquiry_id}/confirm").json()["data"]["status"] == CONFIRMED
        assert client.post(
            f"/api/v1/inquiries/{inquiry_id}/complete", json={"note": "已完工"}
        ).json()["data"]["status"] == COMPLETED
