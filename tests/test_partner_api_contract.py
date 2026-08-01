from __future__ import annotations

from copy import deepcopy

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate_spec

from core.providers import (
    ExistingVendorAdapterConnector,
    ProviderConnectorError,
    StandardProviderConnector,
    WorkbenchProviderConnector,
)
from core.vendors import MockVendorClient
from fake_upstreams.partner_app import ALL_PARTNER_SCOPES, create_partner_fake_app
from fake_upstreams.vendor_app import create_fake_vendor_app

CONTROL_KEY = "partner-control-test"
API_KEY = "partner-secret-test"


def _client(*, scopes: frozenset[str] = ALL_PARTNER_SCOPES) -> TestClient:
    return TestClient(create_partner_fake_app(
        control_key=CONTROL_KEY,
        partner_keys={API_KEY: ("vendor-prince-electric", scopes)},
    ))


def auth(key: str = API_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def write_headers(key: str) -> dict[str, str]:
    return {**auth(), "Idempotency-Key": key}


def test_partner_openapi_is_valid_and_is_the_current_contract():
    with open("contracts/vendor-openapi.yaml", encoding="utf-8") as file:
        spec = yaml.safe_load(file)
    validate_spec(spec)
    assert spec["info"]["version"] == "2.0.0"
    assert "/partner/v1/catalog" in spec["paths"]
    assert "/partner/v1/bookings/{bookingId}" in spec["paths"]
    assert spec["components"]["securitySchemes"]["PartnerBearer"]["scheme"] == "bearer"


def test_partner_api_key_is_hashed_scoped_and_provider_bound():
    limited = _client(scopes=frozenset({"catalog:read"}))
    assert limited.get("/partner/v1/catalog", headers=auth()).status_code == 200
    assert limited.get("/partner/v1/bookings", headers=auth()).status_code == 403
    assert limited.get("/partner/v1/catalog").status_code == 401

    state = limited.get("/__fake__/state", headers={"X-Fake-Control-Key": CONTROL_KEY}).json()["data"]
    assert API_KEY not in state["apiKeyHashes"]
    assert all(len(value) == 64 for value in state["apiKeyHashes"])


def test_catalog_availability_booking_snapshot_and_exact_reset():
    client = _client()
    catalog = client.get("/partner/v1/catalog", headers=auth()).json()["data"]
    availability = client.get("/partner/v1/availability", headers=auth()).json()["data"]
    assert catalog["provider"]["name"] == "王子水電"
    assert availability

    payload = {
        "externalReference": "AIWAVE-BOOKING-1", "accountReference": "member-hash-a",
        "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
        "resourceId": catalog["resources"][0]["id"], "slotId": availability[0]["id"],
        "startsAt": availability[0]["startsAt"], "endsAt": availability[0]["endsAt"],
    }
    created = client.post(
        "/partner/v1/bookings", headers=write_headers("booking-create-once"), json=payload,
    )
    replay = client.post(
        "/partner/v1/bookings", headers=write_headers("booking-create-once"), json=payload,
    )
    assert created.status_code == 201
    assert replay.json()["data"]["id"] == created.json()["data"]["id"]
    assert replay.json()["meta"]["idempotentReplay"] is True
    conflict_payload = {**payload, "externalReference": "AIWAVE-BOOKING-DIFFERENT"}
    conflict = client.post(
        "/partner/v1/bookings", headers=write_headers("booking-create-once"), json=conflict_payload,
    )
    assert conflict.status_code == 422
    assert "不同請求內容" in conflict.json()["error"]["message"]
    snapshot = client.get("/partner/v1/snapshot", headers=auth()).json()["data"]
    assert snapshot["seedVersion"] == "partner-demo-v5"
    assert snapshot["counts"]["bookings"] == 1

    reset = client.post("/__fake__/reset", headers={"X-Fake-Control-Key": CONTROL_KEY}).json()["data"]
    assert reset["seedVersion"] == "partner-demo-v5"
    assert reset["snapshots"]["vendor-prince-electric"]["counts"]["bookings"] == 0


def test_after_commit_fault_reports_state_unknown_but_retry_is_safe():
    client = _client()
    catalog = client.get("/partner/v1/catalog", headers=auth()).json()["data"]
    slot = client.get("/partner/v1/availability", headers=auth()).json()["data"][0]
    payload = {
        "externalReference": "AIWAVE-UNKNOWN", "accountReference": "member-hash-a",
        "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
        "resourceId": catalog["resources"][0]["id"], "slotId": slot["id"],
        "startsAt": slot["startsAt"], "endsAt": slot["endsAt"],
    }
    client.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "POST", "path": "/partner/v1/bookings", "status": 504,
        "detail": "已寫入但回應逾時", "after_commit": True,
    })
    unknown = client.post(
        "/partner/v1/bookings", headers=write_headers("state-unknown-once"), json=payload,
    )
    assert unknown.status_code == 504
    assert unknown.json()["error"]["code"] == "STATE_UNKNOWN"
    assert len(client.get("/partner/v1/bookings", headers=auth()).json()["data"]) == 1
    retry = client.post(
        "/partner/v1/bookings", headers=write_headers("state-unknown-once"), json=payload,
    )
    assert retry.status_code == 201
    assert retry.json()["meta"]["idempotentReplay"] is True


def test_standard_and_workbench_connectors_share_provider_contract(tmp_path):
    upstream = _client()
    standard = StandardProviderConnector(
        base_url="http://partner-fake", api_key=API_KEY, client=upstream,
    )
    catalog = standard.get_catalog()
    slots = standard.get_availability()
    booking = standard.create_booking({
        "externalReference": "AIWAVE-CONNECTOR", "accountReference": "member-hash-a",
        "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
        "resourceId": catalog["resources"][0]["id"], "slotId": slots[0]["id"],
        "startsAt": slots[0]["startsAt"], "endsAt": slots[0]["endsAt"],
    }, idempotency_key="connector-booking-once")
    assert standard.get_booking(booking["id"])["providerId"] == "vendor-prince-electric"

    workbench = WorkbenchProviderConnector(tmp_path / "workbench.sqlite3", provider_id="vendor-prince-electric")
    workbench.save_catalog(deepcopy(catalog))
    workbench.save_availability(deepcopy(slots))
    workbench_booking = workbench.create_booking({
        "externalReference": "WORKBENCH-1", "accountReference": "member-hash-b",
        "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
        "slotId": slots[0]["id"], "startsAt": slots[0]["startsAt"], "endsAt": slots[0]["endsAt"],
    }, idempotency_key="workbench-booking-once")
    assert workbench.get_booking(workbench_booking["id"])["status"] == "pending_provider"
    replay = workbench.create_booking({
        "externalReference": "WORKBENCH-1", "accountReference": "member-hash-b",
        "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
        "slotId": slots[0]["id"], "startsAt": slots[0]["startsAt"], "endsAt": slots[0]["endsAt"],
    }, idempotency_key="workbench-booking-once")
    assert replay["id"] == workbench_booking["id"]
    with pytest.raises(ProviderConnectorError, match="不同請求內容"):
        workbench.create_booking({
            "externalReference": "WORKBENCH-DIFFERENT", "accountReference": "member-hash-b",
            "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
            "slotId": slots[0]["id"], "startsAt": slots[0]["startsAt"], "endsAt": slots[0]["endsAt"],
        }, idempotency_key="workbench-booking-once")
    assert workbench.snapshot()["counts"]["bookings"] == 1


def test_adapter_connector_maps_legacy_http_to_provider_contract():
    legacy_http = TestClient(create_fake_vendor_app(control_key="legacy-adapter-control"))
    connector = ExistingVendorAdapterConnector(
        MockVendorClient(base_url="http://legacy-vendor", client=legacy_http),
        provider_id="vendor-prince-electric",
    )

    catalog = connector.get_catalog()
    slots = connector.get_availability(serviceId="service-repair")

    assert connector.connector_mode == "adapter"
    assert catalog["provider"]["name"] == "王子水電"
    assert catalog["seedVersion"] == "legacy-vendor-adapter-v1"
    assert slots
    assert connector.snapshot()["providerId"] == "vendor-prince-electric"


def test_standard_connector_exposes_state_unknown_and_contract_drift():
    upstream = _client()
    connector = StandardProviderConnector(base_url="http://partner-fake", api_key=API_KEY, client=upstream)
    catalog = connector.get_catalog()
    slot = connector.get_availability()[0]
    payload = {
        "externalReference": "AIWAVE-UNKNOWN-CONNECTOR", "accountReference": "member",
        "offeringId": catalog["offerings"][0]["id"], "locationId": catalog["locations"][0]["id"],
        "slotId": slot["id"], "startsAt": slot["startsAt"], "endsAt": slot["endsAt"],
    }
    upstream.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "POST", "path": "/partner/v1/bookings", "status": 504,
        "detail": "狀態未知", "after_commit": True,
    })
    with pytest.raises(ProviderConnectorError) as caught:
        connector.create_booking(payload, idempotency_key="unknown-connector")
    assert caught.value.state_unknown is True

    upstream.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "GET", "path": "/partner/v1/catalog", "status": 200,
        "body": {"unexpected": "contract drift"},
    })
    with pytest.raises(ProviderConnectorError, match="OpenAPI"):
        connector.get_catalog()
