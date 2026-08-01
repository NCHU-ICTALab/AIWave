"""諮詢單生命週期：住戶送出 → 廠商報價 → 住戶確認 → 廠商完工。

這條線全部走真實資料——廠商工作台看到的就是住戶剛送出的那一筆。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import COMPLETED, CONFIRMED, PENDING_QUOTE, QUOTED, InquiryTransitionError, SqliteInquiryRepository
from core.services import LifeServicesService
from tests.auth import MEMBER_HEADERS, MEMBER_ID, NEW_MEMBER_HEADERS, PARTNER_HEADERS

FEEDBACK = {"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "燈具／開關", "answerId": 1071}]}]}
QUOTE_ITEMS = [{"name": "材料費", "amount": 300}, {"name": "施工費", "amount": 900}]
USER_HEADERS = MEMBER_HEADERS


@pytest.fixture
def repository(tmp_path: Path) -> SqliteInquiryRepository:
    return SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3",
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )


def _submit(repository: SqliteInquiryRepository) -> str:
    """走真實送出路徑（服務層會一併算出給廠商看的可讀摘要）。"""
    service = LifeServicesService(repository, today=date(2026, 7, 25))
    return service.submit_inquiry(
        form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id=MEMBER_ID,
    )["id"]


# ---- Repository ---------------------------------------------------------

def test_new_inquiry_starts_waiting_for_a_quote(repository: SqliteInquiryRepository):
    record = repository.create(form_id=105, feedback_content=FEEDBACK, service_id="service-repair")
    assert record["status"] == PENDING_QUOTE
    assert record["status_label"] == "待廠商報價"
    assert record["official_status"] == "12"   # 對齊官方 order_status
    assert record["quote"] is None


def test_quote_totals_the_line_items(repository: SqliteInquiryRepository):
    inquiry_id = _submit(repository)
    record = repository.add_quote(inquiry_id, items=QUOTE_ITEMS, vendor_name="安心修繕")

    assert record["status"] == QUOTED
    assert record["quote"]["amount"] == 1200
    assert record["quote"]["vendorName"] == "安心修繕"


def test_full_lifecycle_records_every_step(repository: SqliteInquiryRepository):
    inquiry_id = _submit(repository)
    repository.add_quote(inquiry_id, items=QUOTE_ITEMS, vendor_name="安心修繕")
    repository.confirm_quote(inquiry_id)
    record = repository.complete(inquiry_id, note="已更換燈具")

    assert record["status"] == COMPLETED
    assert [event["type"] for event in record["events"]] == [
        "inquiry.created", "quote.created", "quote.confirmed", "service.completed",
    ]
    assert record["events"][-1]["detail"] == "已更換燈具"


def test_cannot_skip_resident_confirmation(repository: SqliteInquiryRepository):
    """未經住戶同意就完工是不允許的。"""
    inquiry_id = _submit(repository)
    repository.add_quote(inquiry_id, items=QUOTE_ITEMS, vendor_name="安心修繕")
    with pytest.raises(InquiryTransitionError):
        repository.complete(inquiry_id)


def test_cannot_confirm_before_a_quote_exists(repository: SqliteInquiryRepository):
    with pytest.raises(InquiryTransitionError):
        repository.confirm_quote(_submit(repository))


def test_cannot_quote_twice(repository: SqliteInquiryRepository):
    inquiry_id = _submit(repository)
    repository.add_quote(inquiry_id, items=QUOTE_ITEMS, vendor_name="安心修繕")
    with pytest.raises(InquiryTransitionError):
        repository.add_quote(inquiry_id, items=QUOTE_ITEMS, vendor_name="別家")


def test_vendor_queue_only_shows_what_needs_quoting(repository: SqliteInquiryRepository):
    quoted = _submit(repository)
    waiting = _submit(repository)
    repository.add_quote(quoted, items=QUOTE_ITEMS, vendor_name="安心修繕")

    pending = [record["id"] for record in repository.list_by_status(PENDING_QUOTE)]
    assert pending == [waiting]
    assert [record["id"] for record in repository.list_by_status(QUOTED)] == [quoted]


# ---- API：三個角色真的互相看得到 ---------------------------------------

class UnusedLlm:
    def chat(self, *args, **kwargs) -> str:
        raise AssertionError("lifecycle endpoints must not call the LLM")

    def json(self, *args, **kwargs) -> object:
        raise AssertionError("lifecycle endpoints must not call the LLM")


@pytest.fixture
def client(repository: SqliteInquiryRepository) -> TestClient:
    return TestClient(create_app(repository=repository, llm_factory=UnusedLlm))


def test_resident_submission_appears_in_the_vendor_workload(client: TestClient, repository: SqliteInquiryRepository):
    inquiry_id = _submit(repository)

    workload = client.get("/api/v1/vendor/workload", headers=PARTNER_HEADERS).json()["data"]
    assert [record["id"] for record in workload["pendingQuote"]] == [inquiry_id]
    # 廠商看得到住戶填了什麼，而不是只有一個編號
    assert workload["pendingQuote"][0]["summary"] == [{"label": "修繕項目", "value": "燈具／開關"}]


def test_resident_inquiry_list_is_scoped_to_the_signed_in_account(
    client: TestClient, repository: SqliteInquiryRepository,
):
    services = LifeServicesService(repository, today=date(2026, 7, 25))
    mine = services.submit_inquiry(
        form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id=MEMBER_ID,
    )
    services.submit_inquiry(
        form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id="B002",
    )

    response = client.get(
        "/api/v1/inquiries", headers=MEMBER_HEADERS,
    )
    assert response.status_code == 200
    assert [record["id"] for record in response.json()["data"]] == [mine["id"]]

    new_account = client.get("/api/v1/inquiries", headers=NEW_MEMBER_HEADERS)
    assert new_account.status_code == 200
    assert new_account.json()["data"] == []


def test_vendor_workload_is_scoped_to_the_signed_in_vendor(
    client: TestClient, repository: SqliteInquiryRepository,
):
    services = LifeServicesService(repository, today=date(2026, 7, 25))
    repair = services.submit_inquiry(
        form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id=MEMBER_ID,
    )
    cleaning = services.submit_inquiry(
        form_id=103,
        feedback_content={"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "20 坪以下", "answerId": 1030}]}]},
        service_id="service-cleaning", account_id="B002",
    )

    prince = client.get("/api/v1/vendor/workload", headers=PARTNER_HEADERS)
    spoofed = client.get(
        "/api/v1/vendor/workload",
        headers={**PARTNER_HEADERS, "X-Role": "partner", "X-Account-Id": "vendor-duskin"},
    )

    assert [row["id"] for row in prince.json()["data"]["pendingQuote"]] == [repair["id"]]
    assert [row["id"] for row in spoofed.json()["data"]["pendingQuote"]] == [repair["id"]]
    assert cleaning["id"] not in [row["id"] for row in spoofed.json()["data"]["pendingQuote"]]


def test_quote_then_confirm_then_complete_over_http(client: TestClient, repository: SqliteInquiryRepository):
    inquiry_id = _submit(repository)

    quoted = client.post(
        f"/api/v1/inquiries/{inquiry_id}/quote", headers=PARTNER_HEADERS,
        json={"items": QUOTE_ITEMS, "vendor_name": "安心修繕"},
    ).json()["data"]
    assert quoted["status"] == QUOTED
    assert quoted["quote"]["amount"] == 1200

    confirmed = client.post(
        f"/api/v1/inquiries/{inquiry_id}/confirm", headers=USER_HEADERS,
    ).json()["data"]
    assert confirmed["status"] == CONFIRMED

    completed = client.post(
        f"/api/v1/inquiries/{inquiry_id}/complete", headers=PARTNER_HEADERS, json={"note": "已完工"},
    ).json()["data"]
    assert completed["status"] == COMPLETED

    # 住戶端查得到同一筆的最終狀態
    assert client.get(f"/api/v1/inquiries/{inquiry_id}", headers=USER_HEADERS).json()["data"]["status"] == COMPLETED


def test_illegal_transition_is_rejected_with_a_readable_reason(client: TestClient, repository: SqliteInquiryRepository):
    inquiry_id = _submit(repository)
    response = client.post(f"/api/v1/inquiries/{inquiry_id}/complete", headers=PARTNER_HEADERS, json={})

    assert response.status_code == 409
    assert "待廠商報價" in response.json()["detail"]


def test_quote_for_unknown_inquiry_is_rejected(client: TestClient):
    response = client.post("/api/v1/inquiries/INQ-NOPE/quote",
                           headers=PARTNER_HEADERS,
                           json={"items": QUOTE_ITEMS, "vendor_name": "安心修繕"})
    assert response.status_code == 409
