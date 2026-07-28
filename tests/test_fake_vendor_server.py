"""廠商 fake server 是可獨立驗證的 HTTP 系統，不是單頁 demo 內的假陣列。"""

from copy import deepcopy
from time import perf_counter

import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate_spec

from fake_upstreams.vendor_app import create_fake_vendor_app

CONTROL_KEY = "vendor-contract-test"


def _client() -> TestClient:
    return TestClient(create_fake_vendor_app(control_key=CONTROL_KEY))


def _headers() -> dict[str, str]:
    return {"X-Fake-Control-Key": CONTROL_KEY}


def _new_inquiry() -> dict:
    return {
        "accountId": "user-001", "serviceId": "service-repair", "vendorId": "vendor-prince-electric",
        "consumer": {"name": "王小明", "phone": "0912-345-678", "email": "user@example.com"},
        "location": {"countyCode": "01", "countyName": "臺北市", "districtCode": "002",
                     "districtName": "大同區", "postalCode": "103", "address": "103臺北市大同區承德路一段1號"},
        "preferredSlots": ["weekend"], "budget": 2500, "urgency": "normal",
        "answers": {"description": "浴室燈無法開啟"}, "summary": "週六浴室燈修繕",
        "externalReference": "AIWAVE-DEMO-001",
    }


def test_checked_in_openapi_contract_is_valid():
    with open("contracts/vendor-openapi.yaml", encoding="utf-8") as file:
        validate_spec(yaml.safe_load(file))


def test_seed_is_reproducible_taiwanese_and_uses_authentic_allowlist():
    client = _client()
    vendors = client.get("/v1/vendors").json()["data"]
    state = client.get("/__fake__/state", headers=_headers()).json()["data"]

    assert state["counts"] == {"vendors": 10, "locations": 30, "offerings": 15,
                               "inquiries": 120, "quotes": 120, "orders": 0}
    names = {item["name"] for item in vendors}
    assert {"太子物業", "王子水電", "黑貓宅急便", "7-ELEVEN 交貨便", "康是美"} <= names
    assert not {"潔沛家事服務", "速修水電", "閃電到府維修"} & names
    locations = client.get("/v1/vendors/vendor-prince-electric/locations").json()["data"]
    assert len(locations) == 3
    assert all(item["postalCode"] in item["address"] and item["countyName"] in item["address"] for item in locations)

    before = deepcopy(vendors)
    client.post("/__fake__/reset", headers=_headers())
    after = client.get("/v1/vendors").json()["data"]
    assert before == after


def test_full_inquiry_quote_order_lifecycle_and_idempotency():
    client = _client()
    inquiry_headers = {"Idempotency-Key": "create-inquiry-once"}
    first = client.post("/v1/inquiries", headers=inquiry_headers, json=_new_inquiry())
    replay = client.post("/v1/inquiries", headers=inquiry_headers, json=_new_inquiry())
    assert first.status_code == 201
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert replay.json()["meta"]["idempotentReplay"] is True
    inquiry_id = first.json()["data"]["id"]

    quote = client.post(f"/v1/inquiries/{inquiry_id}/quotes", headers={"Idempotency-Key": "quote-once"}, json={
        "vendorId": "vendor-prince-electric", "validUntil": "2026-08-10",
        "items": [{"name": "燈具線路檢測與修繕", "quantity": 1, "unitPrice": 1500}],
    })
    assert quote.status_code == 201
    assert quote.json()["data"]["total"] == 1500
    quote_id = quote.json()["data"]["id"]

    order = client.post("/v1/orders", headers={"Idempotency-Key": "order-once"}, json={
        "inquiryId": inquiry_id, "quoteId": quote_id, "accountId": "user-001",
        "externalReference": "AIWAVE-DEMO-001",
    })
    assert order.status_code == 201
    order_id = order.json()["data"]["id"]
    completed = client.post(f"/v1/orders/{order_id}/events", headers={"Idempotency-Key": "complete-once"}, json={
        "type": "completed", "status": "completed", "note": "已完工並由住戶確認",
    })
    assert completed.status_code == 201
    assert completed.json()["data"]["status"] == "completed"
    assert completed.json()["data"]["version"] == 2


def test_control_plane_auth_fault_once_and_exact_reset():
    client = _client()
    assert client.get("/__fake__/state").status_code == 401
    injected = client.put("/__fake__/faults/next", headers=_headers(), json={
        "method": "GET", "path": "/v1/vendors", "status": 503, "detail": "廠商目錄維護中",
    })
    assert injected.status_code == 200
    failed = client.get("/v1/vendors")
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "INJECTED_FAULT"
    assert client.get("/v1/vendors").status_code == 200

    client.post("/v1/inquiries", headers={"Idempotency-Key": "mutation"}, json=_new_inquiry())
    reset = client.post("/__fake__/reset", headers=_headers()).json()["data"]
    assert reset["requestCount"] == 0
    assert reset["pendingFaults"] == []
    assert reset["counts"]["inquiries"] == 120


def test_control_plane_can_delay_one_successful_request_then_recovers():
    client = _client()
    client.put("/__fake__/faults/next", headers=_headers(), json={
        "method": "GET", "path": "/v1/vendors", "status": 200, "delay_ms": 30,
    })
    started = perf_counter()
    delayed = client.get("/v1/vendors")
    elapsed = perf_counter() - started

    assert delayed.status_code == 200
    assert elapsed >= 0.02
    assert client.get("/__fake__/state", headers=_headers()).json()["data"]["pendingFaults"] == []


def test_errors_are_traceable_and_money_is_integer():
    client = _client()
    response = client.get("/v1/vendors/not-found")
    assert response.status_code == 404
    assert response.headers["X-Trace-Id"] == response.json()["error"]["traceId"]
    offerings = client.get("/v1/offerings", params={"serviceId": "service-repair"}).json()["data"]
    assert offerings
    assert all(isinstance(item["basePrice"], int) for item in offerings)
