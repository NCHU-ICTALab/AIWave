"""VendorClient 的 fake/real HTTP seam 與失敗行為。"""

import httpx
import pytest
from fastapi.testclient import TestClient

from core.vendors import (
    MockVendorClient,
    RealVendorClient,
    VendorClientError,
    VendorService,
    build_vendor_client,
)
from fake_upstreams.vendor_app import create_fake_vendor_app

CONTROL_KEY = "vendor-client-test"


def _mock_client() -> tuple[TestClient, MockVendorClient]:
    upstream = TestClient(create_fake_vendor_app(control_key=CONTROL_KEY))
    return upstream, MockVendorClient(base_url="http://vendor-fake", client=upstream)


def test_mock_client_calls_independent_http_contract_and_matches_authentic_brands():
    _, client = _mock_client()
    service = VendorService(client)

    result = service.match(
        "service-repair", county_code="01", district_code="002",
        budget=2000, slot="weekend", urgent=True,
    )

    assert len(result["vendors"]) == 2
    assert {item["vendorName"] for item in result["vendors"]} == {"太子物業", "王子水電"}
    assert result["vendors"][0]["vendorName"] == "王子水電"
    assert result["meta"]["connectorMode"] == "mock_http"
    assert result["meta"]["dataSource"] == "fake_vendor:vendor_demo_seed_v1"
    assert all(item["source"]["dataPolicy"] for item in result["vendors"])


def test_malformed_success_response_becomes_domain_error_and_visible_fallback():
    upstream, client = _mock_client()
    upstream.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "GET", "path": "/v1/vendors", "status": 200,
        "body": {"unexpected": "contract drift"},
    })

    result = VendorService(client).match("service-repair", county_code="01")

    assert result["vendors"]
    assert result["meta"]["connectorMode"] == "offline_fallback"
    assert "不符合 OpenAPI 契約" in result["meta"]["degradedReason"]
    assert all(item["dataSource"] == "competition_seed_offline_fallback" for item in result["vendors"])


def test_real_client_sends_bearer_token_but_keeps_same_contract():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json={
            "data": [], "meta": {"dataSource": "partner-api", "traceId": "trc-real"},
        })

    client = httpx.Client(base_url="https://partner.example", transport=httpx.MockTransport(handler))
    adapter = RealVendorClient(base_url="https://partner.example", api_token="secret-token", client=client)

    assert adapter.search_vendors(serviceId="service-repair")["data"] == []
    assert seen["authorization"] == "Bearer secret-token"
    assert adapter.connector_mode == "real_http"


def test_factory_only_accepts_explicit_fake_or_real_configuration():
    fake = build_vendor_client(
        mode="fake", fake_url="http://127.0.0.1:8020", real_url="", api_token="", timeout_seconds=1,
    )
    assert isinstance(fake, MockVendorClient)
    with pytest.raises(ValueError, match="VENDOR_API_TOKEN"):
        build_vendor_client(
            mode="real", fake_url="", real_url="https://partner.example", api_token="", timeout_seconds=1,
        )
    with pytest.raises(ValueError, match="fake 或 real"):
        build_vendor_client(
            mode="auto", fake_url="http://127.0.0.1:8020", real_url="", api_token="", timeout_seconds=1,
        )


def test_write_failure_never_claims_offline_success():
    _, client = _mock_client()
    with pytest.raises(VendorClientError):
        client.create_inquiry({}, idempotency_key="invalid-payload")


def test_timeout_becomes_visible_read_fallback_but_never_fake_write_success():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout", request=request)

    http = httpx.Client(base_url="https://slow.vendor", transport=httpx.MockTransport(timeout))
    client = MockVendorClient(base_url="https://slow.vendor", client=http)
    result = VendorService(client).match("service-repair", county_code="01")

    assert result["meta"]["connectorMode"] == "offline_fallback"
    assert "timeout" in result["meta"]["degradedReason"]
    with pytest.raises(VendorClientError, match="timeout"):
        client.create_inquiry({}, idempotency_key="must-not-succeed")
