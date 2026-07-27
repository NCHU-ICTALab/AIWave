"""個人洞察 API 契約（前端儀表板與推薦卡片依賴此形狀）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import SqliteInquiryRepository


class UnusedLlm:
    """洞察端點全由官方資料規則算出，不該碰 LLM。"""

    def chat(self, *args, **kwargs) -> str:
        raise AssertionError("insights endpoints must not call the LLM")

    def json(self, *args, **kwargs) -> object:
        raise AssertionError("insights endpoints must not call the LLM")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    return TestClient(create_app(repository=repository, llm_factory=UnusedLlm))


def test_accounts_endpoint_lists_the_three_demo_households(client: TestClient) -> None:
    """登入清單是三位展示住戶，不是 10 個通路帳號。

    原本每個官方帳號各成一個「使用者」，7/10 只用過單一服務——那是通路切分的
    結果，不是 10 個真實的人。整併見 core/data/identity.py 與 personas.py。
    """
    accounts = client.get("/api/v1/insights/accounts").json()["data"]
    assert len(accounts) == 3
    assert sum(1 for account in accounts if account["isDefault"]) == 1
    for account in accounts:
        assert account["serviceCount"] >= 3, f"{account['name']} 只有 {account['serviceCount']} 種服務"
        assert account["source"] == "demo_composition"   # 介面要能標示這是展示組合


def test_me_resolves_to_the_demo_persona(client: TestClient) -> None:
    summary = client.get("/api/v1/insights/me/summary").json()["data"]
    assert summary["source"] == "official_order_record"
    assert summary["totalOrders"] > 0
    assert summary["openOrders"] > 0  # 展示 persona 有未完成訂單


def test_summary_supplies_real_dashboard_numbers(client: TestClient) -> None:
    """儀表板不再用寫死數字：金額、點數、服務分布都來自官方訂單。"""
    summary = client.get("/api/v1/insights/me/summary").json()["data"]
    assert set(summary) >= {"totalSpend", "earnedPoints", "distinctServices", "services", "lastActivity"}
    assert summary["totalSpend"] == sum(usage["totalAmount"] for usage in summary["services"])


def test_trail_is_cross_service(client: TestClient) -> None:
    trail = client.get("/api/v1/insights/me/trail").json()["data"]
    assert len({event["serviceName"] for event in trail}) >= 2
    assert all(event["recordId"] > 0 for event in trail)


def test_recommendations_expose_evidence_for_the_ui(client: TestClient) -> None:
    recs = client.get("/api/v1/insights/me/recommendations").json()["data"]
    assert recs
    top = recs[0]
    assert top["computedBy"] == "rules"
    assert top["reasonText"]
    assert top["evidence"][0]["recordId"] > 0


def test_recommendation_limit_is_honoured(client: TestClient) -> None:
    recs = client.get("/api/v1/insights/me/recommendations?limit=1").json()["data"]
    assert len(recs) == 1


def test_unknown_account_returns_empty_rather_than_failing(client: TestClient) -> None:
    response = client.get("/api/v1/insights/no-such-account/summary")
    assert response.status_code == 200
    assert response.json()["data"]["totalOrders"] == 0
