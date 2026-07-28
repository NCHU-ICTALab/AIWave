"""平台透過真實 HTTP connector 連 fake upstream，失敗時明確降級。"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from core.config import get_settings
from core.inquiries import SqliteInquiryRepository
from core.retail import (
    FallbackRetailConnector,
    HttpRetailConnector,
    SeedRetailConnector,
    SqliteRetailRepository,
)
from fake_upstreams.app import create_fake_upstream_app

CONTROL_KEY = "connector-test-key"
NOW = lambda: datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc)  # noqa: E731


class UnusedLlm:
    def chat(self, *args, **kwargs):
        raise AssertionError("inventory flow must not call LLM")

    def json(self, *args, **kwargs):
        raise AssertionError("inventory flow must not call LLM")


def test_platform_uses_fake_upstream_contract_and_recovers_via_offline_adapter(tmp_path):
    upstream = TestClient(create_fake_upstream_app(control_key=CONTROL_KEY))
    connector = FallbackRetailConnector(
        primary=HttpRetailConnector(base_url="http://fake-upstream", client=upstream),
        fallback=SeedRetailConnector(),
    )
    platform = TestClient(create_app(
        repository=SqliteInquiryRepository(tmp_path / "platform.sqlite3", now=NOW),
        retail_repository=SqliteRetailRepository(tmp_path / "platform.sqlite3", now=NOW),
        retail_connector=connector,
        llm_factory=UnusedLlm,
    ))

    live = platform.get("/api/v1/retail/stores/search", params={"q": "吉伊卡哇限定杯", "district": "大同區"})
    assert live.status_code == 200
    assert live.json()["data"]["dataSource"] == "fake_upstream:demo_seed_v1"
    assert live.json()["data"]["connectorMode"] == "http"

    upstream.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "GET", "path": "/v1/retail/inventory/limited-cup", "status": 503,
        "detail": "品牌庫存維護中", "delay_ms": 0,
    })
    degraded = platform.get("/api/v1/retail/stores/search", params={"q": "吉伊卡哇限定杯", "district": "大同區"})
    assert degraded.status_code == 200
    assert degraded.json()["data"]["dataSource"] == "competition_seed_offline_fallback"
    assert degraded.json()["data"]["connectorMode"] == "offline_fallback"
    assert "品牌庫存維護中" in degraded.json()["data"]["degradedReason"]
    assert degraded.json()["data"]["alternatives"], "離線仍要能完成替代門市流程"

    recovered = platform.get("/api/v1/retail/stores/search", params={"q": "吉伊卡哇限定杯", "district": "大同區"})
    assert recovered.json()["data"]["connectorMode"] == "http"


def test_malformed_success_response_also_uses_visible_fallback(tmp_path):
    upstream = TestClient(create_fake_upstream_app(control_key=CONTROL_KEY))
    connector = FallbackRetailConnector(
        primary=HttpRetailConnector(base_url="http://fake-upstream", client=upstream),
        fallback=SeedRetailConnector(),
    )
    platform = TestClient(create_app(
        repository=SqliteInquiryRepository(tmp_path / "platform.sqlite3", now=NOW),
        retail_repository=SqliteRetailRepository(tmp_path / "platform.sqlite3", now=NOW),
        retail_connector=connector,
        llm_factory=UnusedLlm,
    ))
    upstream.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "GET", "path": "/v1/retail/products/resolve", "status": 200,
        "body": {"unexpected": "contract drift"},
    })

    response = platform.get(
        "/api/v1/retail/stores/search", params={"q": "吉伊卡哇限定杯", "district": "大同區"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["connectorMode"] == "offline_fallback"
    assert "不符合契約" in response.json()["data"]["degradedReason"]


def test_environment_configuration_reaches_api_connector_factory(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setenv("RETAIL_UPSTREAM_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("UPSTREAM_TIMEOUT_SECONDS", "1.25")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    def capture_factory(*, upstream_url, timeout_seconds):
        captured.update(upstream_url=upstream_url, timeout_seconds=timeout_seconds)
        return SeedRetailConnector()

    monkeypatch.setattr("api.app.build_retail_connector", capture_factory)
    create_app(llm_factory=UnusedLlm)

    assert captured == {"upstream_url": "http://127.0.0.1:8010", "timeout_seconds": 1.25}
    get_settings.cache_clear()
