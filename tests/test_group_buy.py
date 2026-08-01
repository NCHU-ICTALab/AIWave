"""社區團購：管委會開團 → 住戶跟團 → 結單彙總給廠商。

社區是住戶共享的範圍（ADR-0003）：同一檔活動，兩個角色看到同一份資料。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.community import CLOSED, OPEN, GroupBuyError, SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from tests.auth import MANAGER_HEADERS, MEMBER_HEADERS, MEMBER_ID, SECOND_MEMBER_ID

RESIDENT_A = MEMBER_ID
RESIDENT_B = SECOND_MEMBER_ID


@pytest.fixture
def repository(tmp_path: Path) -> SqliteGroupBuyRepository:
    return SqliteGroupBuyRepository(
        tmp_path / "community.sqlite3",
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )


def _campaign(repository: SqliteGroupBuyRepository, **overrides) -> dict:
    return repository.create_campaign(**{
        "title": "七月社區團購",
        "item_name": "愛文芒果 5 斤",
        "unit_price": 350,
        "min_quantity": 10,
        "pickup": "社區管理室",
        **overrides,
    })


def test_new_campaign_is_open_and_empty(repository: SqliteGroupBuyRepository):
    campaign = _campaign(repository)
    assert campaign["status"] == OPEN
    assert campaign["statusLabel"] == "收單中"
    assert (campaign["householdCount"], campaign["totalQuantity"]) == (0, 0)
    assert campaign["reachedMinimum"] is False


def test_joins_accumulate_across_households(repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=2)
    campaign = repository.join(campaign_id, account_id=RESIDENT_B, display_name="B 戶", quantity=3)

    assert campaign["householdCount"] == 2
    assert campaign["totalQuantity"] == 5
    assert campaign["totalAmount"] == 5 * 350


def test_rejoining_updates_quantity_rather_than_duplicating(repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=2)
    campaign = repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=5)

    assert campaign["householdCount"] == 1
    assert campaign["totalQuantity"] == 5


def test_minimum_is_reported_once_reached(repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository, min_quantity=4)["id"]
    repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=1)
    assert repository.get_campaign(campaign_id)["reachedMinimum"] is False
    campaign = repository.join(campaign_id, account_id=RESIDENT_B, display_name="B 戶", quantity=3)
    assert campaign["reachedMinimum"] is True


def test_cannot_join_a_closed_campaign(repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.close_campaign(campaign_id)
    with pytest.raises(GroupBuyError, match="已結單"):
        repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=1)


def test_cannot_close_twice(repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.close_campaign(campaign_id)
    with pytest.raises(GroupBuyError):
        repository.close_campaign(campaign_id)


@pytest.mark.parametrize("quantity", [0, -1])
def test_quantity_must_be_positive(repository: SqliteGroupBuyRepository, quantity):
    campaign_id = _campaign(repository)["id"]
    with pytest.raises(GroupBuyError):
        repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=quantity)


# ---- API：住戶與管委會看同一份資料 -------------------------------------

class UnusedLlm:
    def chat(self, *args, **kwargs) -> str:
        raise AssertionError("community endpoints must not call the LLM")

    def json(self, *args, **kwargs) -> object:
        raise AssertionError("community endpoints must not call the LLM")


@pytest.fixture
def client(tmp_path: Path, repository: SqliteGroupBuyRepository) -> TestClient:
    inquiries = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    return TestClient(create_app(repository=inquiries, group_buys=repository, llm_factory=UnusedLlm))


def test_resident_sees_open_campaigns_and_can_join(client: TestClient, repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]

    listed = client.get(
        "/api/v1/community/campaigns?only_open=true", headers=MEMBER_HEADERS,
    ).json()["data"]
    assert [item["id"] for item in listed] == [campaign_id]

    joined = client.post(f"/api/v1/community/campaigns/{campaign_id}/join", headers=MEMBER_HEADERS,
                         json={"account_id": RESIDENT_A, "display_name": "小圓", "quantity": 2}).json()["data"]
    assert joined["totalQuantity"] == 2
    assert joined["householdCount"] == 1


def test_manager_creates_a_campaign_that_residents_immediately_see(client: TestClient):
    created = client.post("/api/v1/community/campaigns", headers=MANAGER_HEADERS, json={
        "title": "八月團購", "item_name": "文旦 10 斤", "unit_price": 400, "min_quantity": 5,
    }).json()["data"]

    listed = client.get(
        "/api/v1/community/campaigns?only_open=true", headers=MEMBER_HEADERS,
    ).json()["data"]
    assert created["id"] in [item["id"] for item in listed]


def test_closing_produces_a_purchase_order_for_the_vendor(client: TestClient, repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.join(campaign_id, account_id=RESIDENT_A, display_name="A 戶", quantity=2)
    repository.join(campaign_id, account_id=RESIDENT_B, display_name="B 戶", quantity=3)

    payload = client.post(
        f"/api/v1/community/campaigns/{campaign_id}/close", headers=MANAGER_HEADERS,
    ).json()["data"]

    assert payload["campaign"]["status"] == CLOSED
    order = payload["purchaseOrder"]
    assert order["totalQuantity"] == 5
    assert order["totalAmount"] == 1750
    assert {household["name"] for household in order["households"]} == {"A 戶", "B 戶"}


def test_joining_a_closed_campaign_is_rejected_with_a_reason(client: TestClient, repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.close_campaign(campaign_id)

    response = client.post(f"/api/v1/community/campaigns/{campaign_id}/join", headers=MEMBER_HEADERS,
                           json={"account_id": RESIDENT_A, "quantity": 1})
    assert response.status_code == 409
    assert "已結單" in response.json()["detail"]


def test_resident_can_see_what_they_joined(client: TestClient, repository: SqliteGroupBuyRepository):
    campaign_id = _campaign(repository)["id"]
    repository.join(campaign_id, account_id=RESIDENT_A, display_name="小圓", quantity=2)

    mine = client.get(
        f"/api/v1/community/my-participation?account_id={RESIDENT_A}", headers=MEMBER_HEADERS,
    ).json()["data"]
    assert len(mine) == 1
    assert mine[0]["myQuantity"] == 2

    assert client.get(
        f"/api/v1/community/my-participation?account_id={RESIDENT_B}", headers=MEMBER_HEADERS,
    ).status_code == 404
