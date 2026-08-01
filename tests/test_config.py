"""部署設定的時間基準。"""

from datetime import datetime, timezone

import core.config as config


def test_default_today_uses_taipei_calendar_date(monkeypatch) -> None:
    """AWS 主機即使是 UTC，台灣跨日後也必須把『今天』視為台灣日期。"""

    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            moment = datetime(2026, 7, 29, 16, 30, tzinfo=timezone.utc)
            return moment.astimezone(tz) if tz is not None else moment

    monkeypatch.delenv("DEMO_TODAY", raising=False)
    monkeypatch.setattr(config, "datetime", FrozenDateTime)
    config.get_settings.cache_clear()
    try:
        assert config.get_settings().demo_today.isoformat() == "2026-07-30"
    finally:
        config.get_settings.cache_clear()


def test_partner_connector_mode_and_endpoint_are_environment_only(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_MODE", "standard")
    monkeypatch.setenv("PARTNER_MODE", "real")
    monkeypatch.setenv("PARTNER_REAL_URL", "https://partner.example.test")
    monkeypatch.setenv("PARTNER_API_KEY", "server-side-secret")
    monkeypatch.setenv("PARTNER_TIMEOUT_SECONDS", "3.5")
    config.get_settings.cache_clear()
    try:
        settings = config.get_settings()
        assert settings.provider_mode == "standard"
        assert settings.partner_mode == "real"
        assert settings.partner_real_url == "https://partner.example.test"
        assert settings.partner_api_key == "server-side-secret"
        assert settings.partner_timeout_seconds == 3.5
    finally:
        config.get_settings.cache_clear()
