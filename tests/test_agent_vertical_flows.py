"""三條競賽主線的公開能力測試。

測試只穿過 service/MCP tool seam，不碰 repository 私有欄位；HTTP 與 Vue 會重用同一層。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.planner import Planner
from api.app import create_app
from core.community import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from core.personalization import PersonalizationService, SqlitePersonalizationRepository
from core.orders import SqliteOrderRepository
from core.retail import RetailService, SqliteRetailRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext


TODAY = date(2026, 7, 25)
ACCOUNT = "019a52d3-7f6b-7da3-b48d-9c9e2522d616"


@pytest.fixture
def registry(tmp_path: Path):
    now = lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)  # noqa: E731
    services = LifeServicesService(
        SqliteInquiryRepository(tmp_path / "flow.sqlite3", now=now),
        orders=SqliteOrderRepository(tmp_path / "flow.sqlite3", now=now),
        today=TODAY,
    )
    personalization = PersonalizationService(
        SqlitePersonalizationRepository(tmp_path / "flow.sqlite3", now=now), today=TODAY
    )
    retail = RetailService(SqliteRetailRepository(tmp_path / "flow.sqlite3", now=now))
    return build_registry(
        services=services,
        group_buys=SqliteGroupBuyRepository(tmp_path / "flow.sqlite3", now=now),
        personalization=personalization,
        retail=retail,
        today=TODAY,
    )


@pytest.fixture
def resident() -> ToolContext:
    return ToolContext(account_id=ACCOUNT, role="user", display_name="小圓")


def test_cleaning_search_excludes_unrelated_shipping_and_delivery(registry, resident):
    result = registry.call("search_services", {"query": "想找人來打掃", "limit": 3}, resident)

    ids = [item["id"] for item in result["matches"]]
    assert ids[:2] == ["service-cleaning", "service-housework"]
    assert "service-shipping" not in ids
    assert "service-delivery" not in ids
    assert result["confidence"] == "high"


def test_external_agent_can_submit_a_validated_cleaning_inquiry(registry, resident):
    result = registry.call(
        "submit_inquiry",
        {
            "service_id": "service-cleaning",
            "answers": {
                "homeSize": "medium",
                "focusArea": "whole",
                "date": "2026-07-28",
                "slot": "afternoon",
            },
        },
        resident,
    )

    assert result["id"].startswith("INQ-20260725-")
    assert result["status"] == "pending_quote"
    assert result["account_id"] == ACCOUNT
    assert [row["label"] for row in result["summary"]] == ["居家坪數", "主要清潔區域", "希望日期", "希望時段"]


def test_restock_plan_combines_history_wallet_and_explainable_best_price(registry, resident):
    result = registry.call("get_restock_plan", {}, resident)

    assert result["source"] == "official_orders+competition_seed_wallet"
    assert result["recommendation"]["serviceId"] == "service-shopping"
    assert result["bestOffer"]["finalAmount"] < result["bestOffer"]["baseAmount"]
    assert result["bestOffer"]["applied"]
    assert result["evidence"]


def test_recommendation_feedback_only_suppresses_the_selected_item_and_can_be_undone(registry, resident):
    dismissed = registry.call(
        "record_recommendation_feedback",
        {"recommendation_id": "restock-monthly", "action": "dismiss"},
        resident,
    )
    assert dismissed["active"] is True

    plan = registry.call("get_restock_plan", {}, resident)
    assert plan["recommendation"]["suppressed"] is True

    restored = registry.call(
        "record_recommendation_feedback",
        {"recommendation_id": "restock-monthly", "action": "undo"},
        resident,
    )
    assert restored["active"] is False
    assert registry.call("get_restock_plan", {}, resident)["recommendation"]["suppressed"] is False


def test_resident_can_persist_and_list_a_restock_reminder(registry, resident):
    created = registry.call(
        "create_restock_reminder",
        {"item_name": "衛生紙", "cadence_days": 30, "next_due_on": "2026-08-01"},
        resident,
    )
    assert created["nextDueOn"] == "2026-08-01"
    assert registry.call("list_reminders", {}, resident) == [created]


def test_restock_can_close_as_a_persistent_rule_priced_order(registry, resident):
    order = registry.call(
        "create_order",
        {
            "service_id": "service-shopping",
            "answers": {
                "bundle": "restock",
                "coupon": "apply",
                "points": "50",
                "delivery": "store",
                "payment": "icash-pay",
            },
        },
        resident,
    )

    assert order["id"].startswith("ORD-20260725-")
    assert order["amount"] == 579
    assert order["pricingSource"] == "deterministic_rules"
    assert registry.call("list_my_orders", {}, resident) == [order]


def test_store_search_returns_capability_inventory_and_ranked_alternative(registry, resident):
    result = registry.call(
        "search_store_inventory",
        {"query": "吉伊卡哇限定杯", "district": "大同區", "capability": "列印"},
        resident,
    )

    assert result["dataSource"] == "competition_seed"
    assert result["exactMatches"] == []
    assert result["alternatives"][0]["storeName"] == "7-ELEVEN 中興門市"
    assert result["alternatives"][0]["stock"] > 0
    assert "列印" in result["alternatives"][0]["capabilities"]


def test_out_of_stock_item_can_join_persistent_waitlist(registry, resident):
    joined = registry.call(
        "join_stock_waitlist",
        {"product_id": "limited-cup", "store_id": "qingchuan"},
        resident,
    )
    assert joined["status"] == "watching"
    assert joined["accountId"] == ACCOUNT
    assert registry.call("list_stock_watches", {}, resident) == [joined]


class BrokenLlm:
    def json(self, messages):
        raise RuntimeError("offline")


class BroadCatalogLlm:
    def json(self, messages):
        return {
            "understanding": "找打掃服務",
            "steps": [{"tool": "list_services", "arguments": {}, "why": "查看目錄"}],
        }


def test_planner_has_a_grounded_offline_fallback_for_the_three_demo_flows(registry, resident):
    planner = Planner(BrokenLlm(), registry)

    cleaning = planner.execute(planner.plan("想找人來打掃", resident), resident)
    restock = planner.execute(planner.plan("月初該補貨了，幫我算優惠", resident), resident)
    inventory = planner.execute(planner.plan("大同區哪間門市有吉伊卡哇限定杯而且可以列印", resident), resident)

    assert [step.tool for step in cleaning.steps] == ["search_services"]
    assert cleaning.steps[0].result["matches"][0]["id"] == "service-cleaning"
    assert [step.tool for step in restock.steps] == ["get_restock_plan"]
    assert [step.tool for step in inventory.steps] == ["search_store_inventory"]
    assert inventory.steps[0].arguments["district"] == "大同區"
    assert inventory.steps[0].arguments["capability"] == "列印"


def test_planner_replaces_an_overbroad_catalog_plan_with_grounded_search(registry, resident):
    plan = Planner(BroadCatalogLlm(), registry).plan("想找人來打掃", resident)

    assert [step.tool for step in plan.steps] == ["search_services"]
    assert plan.steps[0].arguments["query"] == "想找人來打掃"


def test_http_seams_expose_persistent_personalization_and_retail_flows(tmp_path: Path):
    now = lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)  # noqa: E731
    db = tmp_path / "http-flow.sqlite3"
    client = TestClient(
        create_app(
            repository=SqliteInquiryRepository(db, now=now),
            order_repository=SqliteOrderRepository(db, now=now),
            group_buys=SqliteGroupBuyRepository(db, now=now),
            personalization_repository=SqlitePersonalizationRepository(db, now=now),
            retail_repository=SqliteRetailRepository(db, now=now),
            llm_factory=BrokenLlm,
        )
    )

    search = client.get("/api/v1/services/search", params={"q": "想找人打掃"})
    assert search.status_code == 200
    assert search.json()["data"]["matches"][0]["id"] == "service-cleaning"

    feedback = client.post(
        f"/api/v1/personalization/{ACCOUNT}/feedback",
        json={"recommendation_id": "restock-monthly", "action": "dismiss"},
    )
    assert feedback.status_code == 200
    assert client.get(f"/api/v1/personalization/{ACCOUNT}/restock-plan").json()["data"]["recommendation"]["suppressed"] is True

    store_search = client.get(
        "/api/v1/retail/stores/search",
        params={"q": "吉伊卡哇限定杯", "district": "大同區", "capability": "列印"},
    )
    assert store_search.json()["data"]["alternatives"][0]["storeId"] == "zhongxing"

    watch = client.post(
        "/api/v1/retail/stock-watches",
        json={"account_id": ACCOUNT, "product_id": "limited-cup", "store_id": "qingchuan"},
    )
    assert watch.status_code == 200
    listed = client.get("/api/v1/retail/stock-watches", params={"account_id": ACCOUNT})
    assert listed.json()["data"][0]["productId"] == "limited-cup"
