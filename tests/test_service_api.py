"""服務目錄／題組／試算 API——前端與 MCP 共用的契約。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import SqliteInquiryRepository


class UnusedLlm:
    """這些端點不該碰 LLM；碰了就讓測試失敗。"""

    def chat(self, *args, **kwargs) -> str:
        raise AssertionError("service catalog endpoints must not call the LLM")

    def json(self, *args, **kwargs) -> object:
        raise AssertionError("service catalog endpoints must not call the LLM")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    return TestClient(create_app(repository=repository, llm_factory=UnusedLlm))


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
