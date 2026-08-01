"""服務目錄／題組／試算 API——前端與 MCP 共用的契約。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import SqliteInquiryRepository
from tests.auth import MEMBER_HEADERS, THIRD_MEMBER_HEADERS


class UnusedLlm:
    """這些端點不該碰 LLM；碰了就讓測試失敗。"""

    def chat(self, *args, **kwargs) -> str:
        raise AssertionError("service catalog endpoints must not call the LLM")

    def json(self, *args, **kwargs) -> object:
        raise AssertionError("service catalog endpoints must not call the LLM")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    return TestClient(create_app(
        repository=repository,
        llm_factory=UnusedLlm,
        today=date(2026, 7, 25),
    ))


def test_service_catalog_lists_nine_services(client: TestClient) -> None:
    response = client.get("/api/v1/services")
    assert response.status_code == 200
    services = response.json()["data"]
    assert len(services) == 9
    assert {"id", "name", "category", "summary", "partner", "glyph"} <= set(services[0])


def test_form_definition_is_render_ready(client: TestClient) -> None:
    """前端拿到就能直接渲染：欄位鍵、題型、選項、絕對日期都齊。"""
    response = client.get("/api/v1/services/service-aircon/form")
    assert response.status_code == 200
    definition = response.json()["data"]

    assert definition["serviceId"] == "service-aircon"
    assert definition["action"] == "inquiry"
    assert definition["actionLabel"] == "建立冷氣清洗諮詢"
    assert definition["dataUse"]

    fields = {field["id"]: field for field in definition["fields"]}
    assert list(fields) == ["airconType", "quantity", "date", "slot"]
    assert fields["date"]["minDate"] == "2026-07-26"
    assert fields["airconType"]["options"][0] == {
        "value": "split", "label": "分離式", "optionId": 1020,
    }


def test_conditional_field_ships_visible_when(client: TestClient) -> None:
    definition = client.get("/api/v1/services/service-repair/form").json()["data"]
    detail = next(field for field in definition["fields"] if field["id"] == "detail")
    assert detail["visibleWhen"] == {"fieldId": "repairType", "equals": "other"}


def test_repair_form_captures_the_information_a_vendor_needs(client: TestClient) -> None:
    """修繕諮詢不是只有分類；正式題組必須真的留下到府履約與聯絡資料。"""
    definition = client.get("/api/v1/services/service-repair/form").json()["data"]
    fields = {field["id"]: field for field in definition["fields"]}

    assert {"repairType", "urgency", "region", "date", "slot", "contact"} <= set(fields)
    assert fields["region"]["type"] == 5
    assert fields["date"]["type"] == 9
    assert fields["contact"]["type"] == 8
    assert all(fields[field_id]["required"] for field_id in ("region", "date", "slot", "contact"))


def test_unknown_service_form_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/services/service-nope/form").status_code == 404


def test_quote_endpoint_applies_discount_chain(client: TestClient) -> None:
    response = client.post(
        "/api/v1/services/service-shopping/quote",
        json={"answers": {"bundle": "restock", "coupon": "apply", "points": "50", "payment": "icash-pay"}},
    )
    assert response.status_code == 200
    quote = response.json()["data"]
    assert quote["baseAmount"] == 699
    assert quote["finalAmount"] == 579
    assert len(quote["ruleSummary"]) == 3


def test_quote_for_unknown_service_is_404(client: TestClient) -> None:
    assert client.post("/api/v1/services/service-nope/quote", json={"answers": {}}).status_code == 404


def test_quote_accepts_empty_answers(client: TestClient) -> None:
    quote = client.post("/api/v1/services/service-aircon/quote", json={}).json()["data"]
    assert quote["finalAmount"] == 1800  # 未填台數視為 1 台


def test_manual_shopping_submission_is_persisted_and_idempotent(client: TestClient) -> None:
    headers = {**MEMBER_HEADERS, "Idempotency-Key": "web-shopping-one"}
    payload = {"answers": {
        "bundle": "restock", "delivery": "store",
        "coupon": "apply", "points": "50", "payment": "icash-pay",
    }}
    first = client.post("/api/v1/services/service-shopping/submissions", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    replay = client.post("/api/v1/services/service-shopping/submissions", json=payload, headers=headers)
    assert replay.status_code == 200
    assert first.json()["data"]["kind"] == "order"
    assert replay.json()["data"]["resource"]["id"] == first.json()["data"]["resource"]["id"]
    assert replay.json()["data"]["resource"]["idempotentReplay"] is True
    listed = client.get("/api/v1/orders", headers=MEMBER_HEADERS).json()["data"]
    assert [row["id"] for row in listed].count(first.json()["data"]["resource"]["id"]) == 1


def test_legacy_direct_order_endpoint_requires_and_replays_idempotency_key(client: TestClient) -> None:
    payload = {"account_id": "me", "answers": {
        "bundle": "coffee", "delivery": "store",
        "coupon": "skip", "points": "0", "payment": "card",
    }}
    assert client.post(
        "/api/v1/services/service-shopping/orders", json=payload, headers=MEMBER_HEADERS,
    ).status_code == 422
    headers = {**MEMBER_HEADERS, "Idempotency-Key": "legacy-shopping-order"}
    first = client.post(
        "/api/v1/services/service-shopping/orders", json=payload, headers=headers,
    )
    replay = client.post(
        "/api/v1/services/service-shopping/orders", json=payload, headers=headers,
    )
    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert replay.json()["data"]["idempotentReplay"] is True


def test_manual_inquiry_submission_is_persisted_and_account_isolated(client: TestClient) -> None:
    headers = {**MEMBER_HEADERS, "Idempotency-Key": "web-repair-one"}
    form = client.get("/api/v1/services/service-repair/form").json()["data"]
    visit_date = next(field["minDate"] for field in form["fields"] if field["id"] == "date")
    payload = {"answers": {
        "repairType": "plumbing", "urgency": "normal",
        "region": {"county_name": "臺中市", "district_name": "西屯區"},
        "date": visit_date, "slot": "morning",
        "contact": {"name": "王小明", "mobile": "0912345678", "address": "臺中市西屯區臺灣大道三段99號"},
    }}
    first = client.post("/api/v1/services/service-repair/submissions", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    replay = client.post("/api/v1/services/service-repair/submissions", json=payload, headers=headers)
    inquiry_id = first.json()["data"]["resource"]["id"]
    assert first.json()["data"]["kind"] == "service_request"
    assert replay.json()["data"]["resource"]["id"] == inquiry_id
    assert any(row["id"] == inquiry_id for row in client.get("/api/v1/inquiries", headers=MEMBER_HEADERS).json()["data"])
    assert all(row["id"] != inquiry_id for row in client.get("/api/v1/inquiries", headers=THIRD_MEMBER_HEADERS).json()["data"])


def test_manual_submission_rejects_reusing_key_for_different_payload(client: TestClient) -> None:
    headers = {**MEMBER_HEADERS, "Idempotency-Key": "web-shopping-conflict"}
    first = client.post(
        "/api/v1/services/service-shopping/submissions",
        json={"answers": {"bundle": "coffee", "delivery": "store", "coupon": "skip", "points": "0", "payment": "card"}},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/services/service-shopping/submissions",
        json={"answers": {"bundle": "snacks", "delivery": "store", "coupon": "skip", "points": "0", "payment": "card"}},
        headers=headers,
    )
    assert second.status_code == 409
