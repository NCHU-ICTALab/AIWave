"""今日摘要：回答「我現在該做什麼」（spec 08 產品原則第一條）。

守住的核心性質：**摘要上的每一則都對應到一件真實的事**。
一則指不出來源的待辦，比沒有摘要更糟——它會讓使用者去找一件不存在的事。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.community import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from core.insights.today import CLOSING_SOON_DAYS, build_briefing
from core.services import LifeServicesService
from tests.auth import MEMBER_HEADERS, MEMBER_ID, NEW_MEMBER_HEADERS

TODAY = date(2026, 7, 25)
FEEDBACK = {"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "燈具／開關", "answerId": 1071}]}]}
ME = MEMBER_ID


def _campaign(campaign_id: int, *, close_in_days: int | None, joined: list[str] = ()) -> dict:
    close_time = None
    if close_in_days is not None:
        # 用 timedelta 而不是加天數——跨月時直接加會炸（7/25 + 8 天不是 7 月 33 日）
        close_time = (datetime(2026, 7, 25, tzinfo=timezone.utc) + timedelta(days=close_in_days)).isoformat()
    return {
        "id": campaign_id,
        "title": f"團購 {campaign_id}",
        "itemName": "文旦",
        "unitPrice": 300,
        "unit": "份",
        "status": "open",
        "closeTime": close_time,
        "householdCount": len(joined),
        "joins": [{"account_id": account} for account in joined],
    }


def _inquiry(inquiry_id: str, status: str, *, account_id: str = ME, quote: dict | None = None) -> dict:
    return {"id": inquiry_id, "status": status, "account_id": account_id, "quote": quote}


class TestOrdering:
    def test_what_blocks_the_user_comes_first(self):
        """廠商報好價了，流程卡在使用者身上——這件事最該先講。"""
        items = build_briefing(
            account_id=ME,
            inquiries=[
                _inquiry("INQ-1", "pending_quote"),
                _inquiry("INQ-2", "confirmed"),
                _inquiry("INQ-3", "quoted", quote={"amount": 1200, "vendorName": "速修水電"}),
            ],
            campaigns=[],
            today=TODAY,
        )
        assert items[0].kind == "needs_your_decision"
        assert "INQ-3" in items[0].source

    def test_a_deadline_outranks_a_suggestion(self):
        items = build_briefing(
            account_id=ME,
            inquiries=[],
            campaigns=[_campaign(1, close_in_days=1)],
            today=TODAY,
        )
        kinds = [item.kind for item in items]
        assert kinds.index("closing_soon") < len(kinds)
        assert items[0].kind == "closing_soon"

    def test_a_sooner_deadline_outranks_a_later_one(self):
        items = build_briefing(
            account_id=ME,
            inquiries=[],
            campaigns=[_campaign(1, close_in_days=3), _campaign(2, close_in_days=0)],
            today=TODAY,
        )
        assert items[0].source == "campaign-2"


class TestOnlyRealThings:
    def test_every_item_points_at_something_real(self):
        items = build_briefing(
            account_id=ME,
            inquiries=[_inquiry("INQ-3", "quoted", quote={"amount": 1200, "vendorName": "速修"})],
            campaigns=[_campaign(1, close_in_days=1)],
            today=TODAY,
        )
        for item in items:
            assert item.source, f"{item.title} 指不出來源"
            assert item.evidence, f"{item.title} 沒有證據"
            assert item.to_dict()["computedBy"] == "rules"

    def test_ignores_other_households_inquiries(self):
        items = build_briefing(
            account_id=ME,
            inquiries=[_inquiry("INQ-9", "quoted", account_id="B002", quote={"amount": 999, "vendorName": "X"})],
            campaigns=[],
            today=TODAY,
        )
        assert not [item for item in items if "INQ-9" in item.source]

    def test_does_not_nag_about_a_group_buy_already_joined(self):
        """已經跟過的團不是待辦，是雜訊。"""
        items = build_briefing(
            account_id=ME, inquiries=[], campaigns=[_campaign(1, close_in_days=1, joined=[ME])], today=TODAY
        )
        assert not [item for item in items if item.kind == "closing_soon"]

    def test_ignores_a_group_buy_that_is_not_closing_soon(self):
        items = build_briefing(
            account_id=ME, inquiries=[], campaigns=[_campaign(1, close_in_days=CLOSING_SOON_DAYS + 5)], today=TODAY
        )
        assert not [item for item in items if item.kind == "closing_soon"]

    def test_ignores_a_group_buy_whose_deadline_has_passed(self):
        items = build_briefing(
            account_id=ME, inquiries=[], campaigns=[_campaign(1, close_in_days=-2)], today=TODAY
        )
        assert not [item for item in items if item.kind == "closing_soon"]

    def test_survives_a_campaign_without_a_deadline(self):
        items = build_briefing(account_id=ME, inquiries=[], campaigns=[_campaign(1, close_in_days=None)], today=TODAY)
        assert not [item for item in items if item.kind == "closing_soon"]


class TestSuggestionCap:
    def test_suggestions_never_crowd_out_the_briefing(self):
        """建議沒有時限，不能佔滿版面——實測小圓的推薦一度塞滿全部五格。"""
        from core.insights.today import MAX_SUGGESTIONS

        # 小圓（27 筆、5 種服務）推薦最多；摘要裡建議仍不得超過上限
        items = build_briefing(
            account_id="019a52d3-7f6b-7da3-b48d-9c9e2522d616",
            inquiries=[],
            campaigns=[],
            today=TODAY,
        )
        suggestions = [item for item in items if item.kind == "suggestion"]
        assert len(suggestions) <= MAX_SUGGESTIONS

    def test_real_recommendations_keep_their_own_slots_when_tasks_are_full(self):
        """送單不能讓首頁的主要賣點『可解釋推薦』整區消失。"""
        account_id = "019a52d3-7f6b-7da3-b48d-9c9e2522d616"
        items = build_briefing(
            account_id=account_id,
            inquiries=[_inquiry(f"INQ-{index}", "pending_quote", account_id=account_id) for index in range(5)],
            campaigns=[],
            today=TODAY,
            limit=5,
        )

        assert len(items) == 5
        assert [item for item in items if item.kind == "suggestion"]
        assert [item for item in items if item.kind == "waiting_on_vendor"]


class TestNewUser:
    def test_a_brand_new_user_gets_nothing_rather_than_filler(self):
        """新帳號真的沒有待辦；這時該由零狀態教學，不是塞假資料（spec 08）。"""
        assert build_briefing(account_id=None, inquiries=[], campaigns=[_campaign(1, close_in_days=1)], today=TODAY) == []


class TestApi:
    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        now = lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)  # noqa: E731
        repository = SqliteInquiryRepository(tmp_path / "inq.sqlite3", now=now)
        services = LifeServicesService(repository, today=TODAY)
        record = services.submit_inquiry(
            form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id=ME
        )
        services.quote_inquiry(record["id"], items=[{"name": "施工", "amount": 1200}], vendor_name="速修水電")
        return TestClient(
            create_app(
                repository=repository,
                group_buys=SqliteGroupBuyRepository(tmp_path / "gb.sqlite3", now=now),
            )
        )

    def test_surfaces_the_quote_awaiting_confirmation(self, client: TestClient):
        items = client.get(f"/api/v1/today/{ME}", headers=MEMBER_HEADERS).json()["data"]

        top = items[0]
        assert top["kind"] == "needs_your_decision"
        assert "1,200" in top["detail"]
        assert top["actionRoute"] == "/user/orders"

    def test_a_new_account_sees_an_empty_briefing(self, client: TestClient):
        assert client.get("/api/v1/today/me", headers=NEW_MEMBER_HEADERS).json()["data"] == []

    def test_respects_the_limit(self, client: TestClient):
        assert len(client.get(
            f"/api/v1/today/{ME}?limit=1", headers=MEMBER_HEADERS,
        ).json()["data"]) <= 1
