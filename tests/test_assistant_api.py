"""規劃器與媒合的 HTTP 介面。

除了「會動」之外，這裡守住一條安全性質：**執行端不信任前端傳回來的步驟**。
計畫在前端往返一圈，中間可以被竄改；伺服器必須重新驗證每一步。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.community import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository

RESIDENT_HEADERS = {"X-Account-Id": "A001", "X-Role": "user"}
MANAGER_HEADERS = {"X-Role": "manager"}


class ScriptedLlm:
    """依序回傳預先寫好的規劃結果。"""

    def __init__(self, *payloads) -> None:
        self.payloads = list(payloads)

    def json(self, messages):
        return self.payloads.pop(0) if self.payloads else {"understanding": "", "steps": []}

    def complete(self, messages):  # pragma: no cover
        return json.dumps(self.json(messages), ensure_ascii=False)


@pytest.fixture
def make_client(tmp_path: Path):
    def _make(*payloads) -> TestClient:
        now = lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)  # noqa: E731
        return TestClient(
            create_app(
                repository=SqliteInquiryRepository(tmp_path / "inq.sqlite3", now=now),
                group_buys=SqliteGroupBuyRepository(tmp_path / "gb.sqlite3", now=now),
                llm_factory=lambda: ScriptedLlm(*payloads),
            )
        )

    return _make


# ---- 能力清單 -----------------------------------------------------------

def test_exposes_the_tool_list_for_the_current_role(make_client):
    client = make_client()
    names = {tool["name"] for tool in client.get("/api/v1/assistant/tools").json()["data"]}

    assert "match_vendors" in names
    assert "open_group_buy" not in names, "住戶不該看到管委會的能力"
    assert "open_group_buy" in {
        tool["name"] for tool in client.get("/api/v1/assistant/tools", headers=MANAGER_HEADERS).json()["data"]
    }


# ---- 規劃 ---------------------------------------------------------------

def test_plans_and_runs_read_only_steps_in_one_call(make_client):
    client = make_client({
        "understanding": "冷氣要清洗，順便看團購",
        "steps": [
            {"tool": "list_services", "arguments": {}, "why": "確認服務"},
            {"tool": "list_group_buys", "arguments": {"status": "open"}, "why": "看團購"},
        ],
    })
    response = client.post(
        "/api/v1/assistant/plan",
        headers=RESIDENT_HEADERS,
        json={"message": "冷氣不冷想找人洗，另外社區有團購嗎"},
    )

    plan = response.json()["data"]
    assert response.status_code == 200
    assert plan["understanding"] == "冷氣要清洗，順便看團購"
    assert [step["status"] for step in plan["steps"]] == ["done", "done"]


def test_a_write_step_comes_back_needing_confirmation(make_client):
    client = make_client({
        "understanding": "跟團",
        "steps": [{"tool": "join_group_buy", "arguments": {"campaign_id": 1, "quantity": 2}, "why": "跟團"}],
    })
    campaign = client.post(
        "/api/v1/community/campaigns",
        json={"title": "中秋", "item_name": "文旦", "unit_price": 300},
    ).json()["data"]

    plan = client.post(
        "/api/v1/assistant/plan", headers=RESIDENT_HEADERS, json={"message": "幫我跟團兩份"}
    ).json()["data"]

    assert plan["needsConfirmation"], "寫入動作應該先問過使用者"
    assert client.get(f"/api/v1/community/campaigns").json()["data"][0]["totalQuantity"] == 0
    assert campaign["id"] == 1


def test_reports_the_reason_when_planning_is_rejected(make_client):
    client = make_client({"understanding": "退費", "steps": [{"tool": "refund_all", "arguments": {}, "why": "幻覺"}]})
    plan = client.post("/api/v1/assistant/plan", json={"message": "我要退費"}).json()["data"]

    assert plan["steps"] == []
    assert "不存在的能力" in plan["rejectedReason"]


# ---- 執行：不信任前端 ---------------------------------------------------

def test_executing_a_confirmed_step_actually_writes(make_client):
    client = make_client()
    client.post("/api/v1/community/campaigns", json={"title": "中秋", "item_name": "文旦", "unit_price": 300})

    response = client.post(
        "/api/v1/assistant/plan/execute",
        headers=RESIDENT_HEADERS,
        json={
            "message": "跟團",
            "steps": [{"tool": "join_group_buy", "arguments": {"campaign_id": 1, "quantity": 2}, "why": "跟團"}],
            "approved": [0],
        },
    )

    assert response.json()["data"]["steps"][0]["status"] == "done"
    assert client.get("/api/v1/community/campaigns").json()["data"][0]["totalQuantity"] == 2


def test_rejects_a_step_the_role_may_not_run_even_if_the_client_sends_it(make_client):
    """前端可以竄改送回來的計畫；伺服器必須自己再驗一次。"""
    client = make_client()
    response = client.post(
        "/api/v1/assistant/plan/execute",
        json={
            "message": "開團",
            "account_id": "A001",
            "role": "manager",
            "steps": [{"tool": "open_group_buy", "arguments": {"title": "米", "item_name": "米", "unit_price": 1}, "why": "越權"}],
            "approved": [0],
        },
    )

    assert response.status_code == 400


def test_rejects_a_fabricated_tool_name(make_client):
    client = make_client()
    response = client.post(
        "/api/v1/assistant/plan/execute",
        json={"message": "x", "steps": [{"tool": "drop_database", "arguments": {}, "why": ""}], "approved": [0]},
    )

    assert response.status_code == 400


def test_an_unapproved_write_step_is_not_executed_even_when_posted(make_client):
    client = make_client()
    client.post("/api/v1/community/campaigns", json={"title": "中秋", "item_name": "文旦", "unit_price": 300})

    response = client.post(
        "/api/v1/assistant/plan/execute",
        headers=RESIDENT_HEADERS,
        json={
            "message": "跟團",
            "steps": [{"tool": "join_group_buy", "arguments": {"campaign_id": 1, "quantity": 2}, "why": "跟團"}],
            "approved": [],
        },
    )

    assert response.json()["data"]["steps"][0]["status"] == "needs_confirmation"
    assert client.get("/api/v1/community/campaigns").json()["data"][0]["totalQuantity"] == 0


# ---- 媒合 ---------------------------------------------------------------

def test_matches_vendors_with_explainable_reasons(make_client):
    client = make_client()
    response = client.get("/api/v1/match/service-repair?district=大同區&county=台北市&urgent=true&budget=1500")

    data = response.json()["data"]
    assert response.status_code == 200
    assert 2 <= len(data["vendors"]) <= 3, "命題要求列 2–3 家比較"
    assert data["region"]["district_name"] == "大同區"
    for vendor in data["vendors"]:
        assert vendor["reasons"]
        assert vendor["dataSource"] == "competition_seed"


def test_rejects_an_unknown_service(make_client):
    assert make_client().get("/api/v1/match/service-teleport").status_code == 404


def test_rejects_an_unrecognised_district(make_client):
    assert make_client().get("/api/v1/match/service-repair?district=瓦干達").status_code == 404
