from __future__ import annotations

from fastapi.testclient import TestClient

import core.config as config
import core.demo_reset as demo_reset_module
from api.app import create_app
from core.providers import StandardProviderConnector
from fake_upstreams.partner_app import ALL_PARTNER_SCOPES, create_partner_fake_app


class UnusedLlm:
    def complete(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("reset must not call an LLM")


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def write_headers(key: str, idempotency_key: str) -> dict[str, str]:
    return {**bearer(key), "Idempotency-Key": idempotency_key}


def test_member_reset_is_bearer_secured_and_scoped_to_personal_workspace(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "demo.sqlite3", llm_factory=UnusedLlm))
    chat = client.post(
        "/api/chat/start", headers=bearer("aiwave"), json={"service_id": "service-repair"},
    )
    assert chat.status_code == 200
    session_id = chat.json()["session_id"]
    created = client.post(
        "/api/v1/platform/task-drafts",
        headers=write_headers("aiwave", "reset-member-draft"),
        json={"domain_type": "repair", "values": {"problem": "燈不亮"}},
    )
    assert created.status_code == 200
    event = client.post(
        "/api/v1/platform/calendar/events",
        headers=write_headers("aiwave", "reset-member-calendar"),
        json={
            "title": "測試行程", "starts_at": "2026-08-01T09:00:00+08:00",
            "ends_at": "2026-08-01T10:00:00+08:00",
        },
    )
    assert event.status_code == 200

    assert client.post("/api/v1/platform/demo/reset").status_code == 401
    assert client.post(
        "/api/v1/platform/demo/reset", headers=bearer("aiwave-partner"),
    ).status_code == 403
    reset = client.post("/api/v1/platform/demo/reset", headers=bearer("aiwave"))
    assert reset.status_code == 200
    payload = reset.json()["data"]
    assert payload["scope"] == "workspace"
    assert payload["upstreams"]["partner"] == "not_applicable"
    assert client.get(
        "/api/v1/platform/task-drafts", headers=bearer("aiwave"),
    ).json()["data"] == []
    assert client.get(
        "/api/v1/platform/calendar/events", headers=bearer("aiwave"),
    ).json()["data"] == []
    assert client.post(
        "/api/chat/message", headers=bearer("aiwave"),
        json={"session_id": session_id, "message": "水管漏水"},
    ).status_code == 404
    assert client.get(
        "/api/v1/platform/points", headers=bearer("aiwave"),
    ).json()["data"]["balance"] == 180


def test_admin_reset_clears_platform_and_partner_with_matching_seed(tmp_path, monkeypatch):
    control_key = "reset-control-key"
    partner_api_key = "reset-partner-key"
    upstream = TestClient(create_partner_fake_app(
        control_key=control_key,
        partner_keys={partner_api_key: ("vendor-prince-electric", ALL_PARTNER_SCOPES)},
    ))
    connector = StandardProviderConnector(
        base_url="http://partner-fake", api_key=partner_api_key, client=upstream,
    )
    monkeypatch.setenv("VENDOR_FAKE_CONTROL_KEY", control_key)
    monkeypatch.setenv("PARTNER_FAKE_URL", "http://partner-fake")
    config.get_settings.cache_clear()

    def fake_post(url: str, *, headers: dict, timeout: float):
        return upstream.post(url.removeprefix("http://partner-fake"), headers=headers)

    monkeypatch.setattr(demo_reset_module.httpx, "post", fake_post)
    try:
        client = TestClient(create_app(
            demo_db_path=tmp_path / "demo.sqlite3", llm_factory=UnusedLlm,
            provider_connector=connector,
        ))
        catalog = client.get(
            "/api/v1/platform/provider/catalog", headers=bearer("aiwave"),
        ).json()["data"]
        slot = client.get(
            "/api/v1/platform/provider/availability", headers=bearer("aiwave"),
        ).json()["data"][0]
        created = client.post(
            "/api/v1/platform/bookings",
            headers=write_headers("aiwave", "reset-admin-booking"),
            json={
                "provider_id": catalog["provider"]["id"],
                "location_id": slot["locationId"], "offering_id": slot["offeringId"],
                "resource_id": slot["resourceId"], "slot_id": slot["id"],
                "starts_at": slot["startsAt"], "ends_at": slot["endsAt"],
            },
        )
        assert created.status_code == 200
        assert upstream.get(
            "/partner/v1/snapshot", headers=bearer(partner_api_key),
        ).json()["data"]["counts"]["bookings"] == 1

        reset = client.post(
            "/api/v1/platform/demo/reset", headers=bearer("aiwave-admin"),
        )
        assert reset.status_code == 200
        payload = reset.json()["data"]
        assert payload["scope"] == "demo_workspace"
        assert payload["seedVersion"] == "platform-demo-v2"
        assert payload["upstreams"]["partner"] == {
            "status": "reset", "seedVersion": "partner-demo-v5",
        }
        assert client.get(
            "/api/v1/platform/bookings", headers=bearer("aiwave"),
        ).json()["data"] == []
        assert upstream.get(
            "/partner/v1/snapshot", headers=bearer(partner_api_key),
        ).json()["data"]["counts"]["bookings"] == 0
        assert client.get(
            "/api/v1/platform/points", headers=bearer("aiwave"),
        ).json()["data"]["balance"] == 180
        # 王小明是主展示住戶。點數種子若只跑 PERSONAS,按過重設之後他的餘額會掉回
        # 0 直到重啟——正好會在彩排按下重設鍵時發生。
        assert client.get(
            "/api/v1/platform/points", headers=bearer("aiwave-demo-resident"),
        ).json()["data"]["balance"] == 180
    finally:
        config.get_settings.cache_clear()
