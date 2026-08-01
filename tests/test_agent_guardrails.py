"""M8 守門模組的確定性測試:Service Registry、TimeResolver、ExecutionGrant。

這三個模組完全不碰 LLM;它們是 Agent 不能繞過的裁決層。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.agent_core import GrantError, ServiceRegistry, SqliteGrantRepository, TimeResolver

TAIPEI = timezone(timedelta(hours=8))


class TestServiceRegistry:
    def test_resolves_clear_phrases_to_a_single_domain(self):
        registry = ServiceRegistry()
        assert registry.resolve("浴室的燈不亮了").matched == "home_repair"
        assert registry.resolve("這週末想訂餐廳聚餐").matched == "dining_reservation"
        assert registry.resolve("幫我找人來打掃").matched == "home_cleaning"
        assert registry.resolve("我要寄包裹到台中").matched == "c2c_shipping"
        assert registry.resolve("想訂谷關的溫泉住宿").matched == "resort_booking"

    def test_ambiguous_laundry_asks_instead_of_guessing(self):
        """spec §4.2:「洗衣服」應釐清是到府家務或洗衣機清洗,不能直接回答沒有服務。"""
        result = ServiceRegistry().resolve("我想洗衣服")
        assert result.matched is None
        assert result.clarify and "家事" in result.clarify
        assert len(result.options) == 2

    def test_ambiguous_aircon_is_disambiguated_by_context(self):
        registry = ServiceRegistry()
        vague = registry.resolve("冷氣的事想處理一下")
        assert vague.matched is None and vague.clarify
        precise = registry.resolve("冷氣不冷,好像壞了")
        assert precise.matched == "home_repair"

    def test_unknown_phrase_returns_nothing_matched_not_an_error(self):
        result = ServiceRegistry().resolve("幫我報稅")
        assert result.matched is None and not result.ambiguous


class TestTimeResolver:
    def make(self, iso: str) -> TimeResolver:
        fixed = datetime.fromisoformat(iso).replace(tzinfo=TAIPEI)
        return TimeResolver(now=lambda: fixed)

    def test_tomorrow_and_absolute_dates_echo_weekday(self):
        resolver = self.make("2026-07-30T09:00:00")  # 週四
        tomorrow = resolver.resolve("明天下午")
        assert tomorrow.date.isoformat() == "2026-07-31"
        assert tomorrow.echo == "7/31(週五)"
        absolute = resolver.resolve("8/9 晚上")
        assert absolute.date.isoformat() == "2026-08-09"

    def test_next_wednesday_is_next_calendar_week(self):
        resolver = self.make("2026-07-30T09:00:00")  # 週四
        result = resolver.resolve("下週三")
        assert result.date.isoformat() == "2026-08-05"
        assert "週三" in result.echo

    def test_this_weekend_is_a_range(self):
        resolver = self.make("2026-07-30T09:00:00")
        result = resolver.resolve("這週末")
        assert result.date.isoformat() == "2026-08-01"
        assert result.end_date.isoformat() == "2026-08-02"

    def test_unparseable_phrase_returns_none_not_a_guess(self):
        assert self.make("2026-07-30T09:00:00").resolve("改天再說").date is None


class TestExecutionGrant:
    def make(self, tmp_path, iso: str = "2026-07-30T09:00:00"):
        moment = datetime.fromisoformat(iso).replace(tzinfo=TAIPEI)
        holder = {"now": moment}
        repo = SqliteGrantRepository(tmp_path / "grants.sqlite3", now=lambda: holder["now"])
        return repo, holder

    def owner(self):
        return {"demo_workspace_id": "demo-default", "workspace_id": "ws-1", "account_id": "acct-1"}

    def propose(self, repo, **overrides):
        payload = {
            **self.owner(), "session_id": "sess-1",
            "provider_ids": ["vendor-prince-electric"],
            "window_start": "2026-07-31", "window_end": "2026-08-02",
            "budget_limit": 2000, "points_limit": 100,
            "summary": "修繕與清潔,總預算 NT$2,000",
        }
        payload.update(overrides)
        return repo.propose(**payload)

    def test_spend_requires_approval_first(self, tmp_path):
        repo, _ = self.make(tmp_path)
        grant = self.propose(repo)
        with pytest.raises(GrantError, match="尚未獲得你的授權"):
            repo.authorize_spend(grant["id"], **self.owner(),
                                 provider_id="vendor-prince-electric",
                                 starts_at="2026-08-01T09:00:00", amount=1200, points=0)

    def test_budget_and_scope_and_window_are_enforced(self, tmp_path):
        repo, _ = self.make(tmp_path)
        grant = self.propose(repo)
        repo.approve(grant["id"], **self.owner())
        with pytest.raises(GrantError, match="超過你核准的預算上限"):
            repo.authorize_spend(grant["id"], **self.owner(),
                                 provider_id="vendor-prince-electric",
                                 starts_at="2026-08-01T09:00:00", amount=2500, points=0)
        with pytest.raises(GrantError, match="不在你核准的範圍"):
            repo.authorize_spend(grant["id"], **self.owner(),
                                 provider_id="vendor-duskin",
                                 starts_at="2026-08-01T09:00:00", amount=100, points=0)
        with pytest.raises(GrantError, match="時間範圍"):
            repo.authorize_spend(grant["id"], **self.owner(),
                                 provider_id="vendor-prince-electric",
                                 starts_at="2026-08-09T09:00:00", amount=100, points=0)
        # 範圍內即通過並累計;第二筆超出剩餘額度被擋
        repo.authorize_spend(grant["id"], **self.owner(),
                             provider_id="vendor-prince-electric",
                             starts_at="2026-08-01T09:00:00", amount=1500, points=50)
        with pytest.raises(GrantError, match="預算上限"):
            repo.authorize_spend(grant["id"], **self.owner(),
                                 provider_id="vendor-prince-electric",
                                 starts_at="2026-08-01T14:00:00", amount=600, points=0)

    def test_expired_grant_is_rejected(self, tmp_path):
        repo, holder = self.make(tmp_path)
        grant = self.propose(repo)
        repo.approve(grant["id"], **self.owner())
        holder["now"] = holder["now"] + timedelta(hours=2)  # 超過 30 分鐘 TTL
        with pytest.raises(GrantError, match="已過期"):
            repo.authorize_spend(grant["id"], **self.owner(),
                                 provider_id="vendor-prince-electric",
                                 starts_at="2026-08-01T09:00:00", amount=100, points=0)
