from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from core.providers import StandardProviderConnector
from fake_upstreams.partner_app import create_partner_fake_app


class UnusedLlm:
    def complete(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("platform core routes must not call an LLM")


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def write_headers(key: str, idempotency_key: str) -> dict[str, str]:
    return {**bearer(key), "Idempotency-Key": idempotency_key}


def test_task_draft_api_is_manual_agent_shared_and_principal_scoped(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))
    created = client.post(
        "/api/v1/platform/task-drafts",
        headers=write_headers("aiwave", "draft-api-once"),
        json={"domain_type": "booking", "values": {"date": "2026-08-01"}, "source": "agent"},
    )
    assert created.status_code == 200
    draft = created.json()["data"]
    edited = client.patch(
        f"/api/v1/platform/task-drafts/{draft['id']}",
        headers=bearer("aiwave"),
        json={"expected_version": 1, "values": {"date": "2026-08-02"}, "source": "user"},
    )
    assert edited.json()["data"]["provenance"]["date"] == "user"
    assert client.get(
        f"/api/v1/platform/task-drafts/{draft['id']}", headers=bearer("aiwave-partner"),
    ).status_code == 403


def test_booking_partner_member_timeline_notification_calendar_and_reschedule(tmp_path):
    upstream = TestClient(create_partner_fake_app(
        control_key="platform-core-control",
        partner_keys={"platform-partner-key": (
            "vendor-prince-electric",
            frozenset({
                "catalog:read", "availability:read", "bookings:read",
                "bookings:write", "snapshot:read",
            }),
        )},
    ))
    connector = StandardProviderConnector(
        base_url="http://partner-fake", api_key="platform-partner-key", client=upstream,
    )
    client = TestClient(create_app(
        demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm,
        provider_connector=connector,
    ))
    catalog = client.get(
        "/api/v1/platform/provider/catalog", headers=bearer("aiwave"),
    ).json()["data"]
    slot = client.get(
        "/api/v1/platform/provider/availability", headers=bearer("aiwave"),
    ).json()["data"][0]
    booking_response = client.post(
        "/api/v1/platform/bookings",
        headers=write_headers("aiwave", "booking-api-once"),
        json={
            "provider_id": catalog["provider"]["id"], "location_id": slot["locationId"],
            "offering_id": slot["offeringId"], "resource_id": slot["resourceId"],
            "slot_id": slot["id"], "starts_at": slot["startsAt"], "ends_at": slot["endsAt"],
        },
    )
    assert booking_response.status_code == 200
    booking = booking_response.json()["data"]
    assert booking["status"] == "pending_provider"
    assert len(client.get("/api/v1/platform/bookings", headers=bearer("aiwave-partner")).json()["data"]) == 1
    assert client.get("/api/v1/platform/bookings", headers=bearer("aiwave-manager")).status_code == 403

    confirmed = client.post(
        f"/api/v1/platform/bookings/{booking['id']}/transition",
        headers=write_headers("aiwave-partner", "confirm-api-once"),
        json={"expected_version": 1, "status": "confirmed"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"
    assert len(client.get("/api/v1/platform/calendar/events", headers=bearer("aiwave")).json()["data"]) == 1
    notifications = client.get("/api/v1/platform/notifications", headers=bearer("aiwave")).json()["data"]
    assert notifications["unreadCount"] == 2

    requested = client.post(
        f"/api/v1/platform/bookings/{booking['id']}/reschedule-requests",
        headers=write_headers("aiwave", "reschedule-api-once"),
        json={
            "slot_id": "slot-b", "starts_at": "2026-08-02T14:00:00+08:00",
            "ends_at": "2026-08-02T15:00:00+08:00", "reason": "需要改成下午",
        },
    )
    request_id = requested.json()["data"]["id"]
    reviewed = client.post(
        f"/api/v1/platform/booking-reschedule-requests/{request_id}/review",
        headers=write_headers("aiwave-partner", "review-reschedule-api"),
        json={"accept": True},
    )
    assert reviewed.status_code == 200
    current = client.get(
        f"/api/v1/platform/bookings/{booking['id']}", headers=bearer("aiwave"),
    ).json()["data"]
    assert current["slotId"] == "slot-b"


def test_points_payment_and_order_api_are_idempotent_and_isolated(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))
    assert client.get("/api/v1/platform/points", headers=bearer("aiwave")).json()["data"]["balance"] == 180
    assert client.get("/api/v1/platform/points", headers=bearer("aiwave-partner")).status_code == 403

    order_response = client.post(
        "/api/v1/platform/commerce-orders",
        headers=write_headers("aiwave", "order-api-once"),
        json={
            "provider_id": "vendor-prince-electric", "discount": 20,
            "items": [{"offering_id": "item-a", "name": "Demo 商品", "quantity": 2, "unit_price": 100}],
        },
    )
    order = order_response.json()["data"]
    assert order["total"] == 180
    replay = client.post(
        "/api/v1/platform/commerce-orders",
        headers=write_headers("aiwave", "order-api-once"),
        json={
            "provider_id": "vendor-prince-electric", "discount": 20,
            "items": [{"offering_id": "item-a", "name": "Demo 商品", "quantity": 2, "unit_price": 100}],
        },
    )
    assert replay.json()["data"]["id"] == order["id"]

    payment = client.post(
        "/api/v1/platform/payments",
        headers=write_headers("aiwave", "payment-api-once"),
        json={
            "subject_type": "commerce_order", "subject_id": order["id"],
            "amount": 180, "points_redeemed": 80, "outcome": "success",
        },
    )
    assert payment.status_code == 200
    assert payment.json()["data"]["status"] == "succeeded"
    assert client.get("/api/v1/platform/points", headers=bearer("aiwave")).json()["data"]["balance"] == 100


def test_partner_state_unknown_is_recoverable_with_the_same_idempotency_key(tmp_path):
    control_key = "platform-state-unknown-control"
    api_key = "platform-state-unknown-partner"
    scopes = frozenset({
        "catalog:read", "availability:read", "bookings:read",
        "bookings:write", "snapshot:read",
    })
    upstream = TestClient(create_partner_fake_app(
        control_key=control_key,
        partner_keys={api_key: ("vendor-prince-electric", scopes)},
    ))
    connector = StandardProviderConnector(
        base_url="http://partner-fake", api_key=api_key, client=upstream,
    )
    client = TestClient(create_app(
        demo_db_path=tmp_path / "state-unknown.sqlite3", llm_factory=UnusedLlm,
        provider_connector=connector,
    ))
    catalog = client.get(
        "/api/v1/platform/provider/catalog", headers=bearer("aiwave"),
    ).json()["data"]
    slot = client.get(
        "/api/v1/platform/provider/availability", headers=bearer("aiwave"),
    ).json()["data"][0]
    body = {
        "provider_id": catalog["provider"]["id"], "location_id": slot["locationId"],
        "offering_id": slot["offeringId"], "resource_id": slot["resourceId"],
        "slot_id": slot["id"], "starts_at": slot["startsAt"], "ends_at": slot["endsAt"],
    }
    upstream.put(
        "/__fake__/faults/next", headers={"X-Fake-Control-Key": control_key},
        json={
            "method": "POST", "path": "/partner/v1/bookings", "status": 504,
            "detail": "建立完成但回應逾時", "after_commit": True,
        },
    )
    first = client.post(
        "/api/v1/platform/bookings",
        headers=write_headers("aiwave", "platform-create-state-unknown"), json=body,
    )
    assert first.status_code == 503
    detail = first.json()["detail"]
    assert detail["stateUnknown"] is True and detail["bookingId"]

    replay = client.post(
        "/api/v1/platform/bookings",
        headers=write_headers("aiwave", "platform-create-state-unknown"), json=body,
    )
    assert replay.status_code == 200
    booking = replay.json()["data"]
    assert booking["providerSync"]["syncStatus"] == "synced"
    assert len(client.get(
        "/api/v1/platform/bookings", headers=bearer("aiwave"),
    ).json()["data"]) == 1

    upstream.put(
        "/__fake__/faults/next", headers={"X-Fake-Control-Key": control_key},
        json={
            "method": "PATCH", "path": f"/partner/v1/bookings/{booking['providerSync']['externalBookingId']}",
            "status": 504, "detail": "狀態已更新但回應逾時", "after_commit": True,
        },
    )
    transition_headers = write_headers("aiwave-partner", "platform-transition-state-unknown")
    unknown_transition = client.post(
        f"/api/v1/platform/bookings/{booking['id']}/transition",
        headers=transition_headers, json={"expected_version": 1, "status": "confirmed"},
    )
    assert unknown_transition.status_code == 503
    recovered = client.post(
        f"/api/v1/platform/bookings/{booking['id']}/transition",
        headers=transition_headers, json={"expected_version": 1, "status": "confirmed"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["data"]["status"] == "confirmed"


def test_admin_refund_derives_owner_inside_the_same_demo_workspace(tmp_path):
    client = TestClient(create_app(
        demo_db_path=tmp_path / "admin-refund.sqlite3", llm_factory=UnusedLlm,
    ))
    # M4:付款主體必須是呼叫者自己的真實交易(IDOR 防護),先建立訂單
    order = client.post(
        "/api/v1/platform/commerce-orders",
        headers=write_headers("aiwave-vivian", "vivian-order"),
        json={
            "provider_id": "vendor-711-shop",
            "items": [{"offering_id": "off-711-shop-preorder-rice", "name": "良食米",
                       "quantity": 1, "unit_price": 120}],
        },
    ).json()["data"]
    payment = client.post(
        "/api/v1/platform/payments",
        headers=write_headers("aiwave-vivian", "vivian-payment"),
        json={
            "subject_type": "commerce_order", "subject_id": order["id"],
            "amount": 120, "points_redeemed": 20, "outcome": "success",
        },
    ).json()["data"]
    for step, status in enumerate(("accepted", "preparing", "shipped", "delivered"), start=1):
        transitioned = client.post(
            f"/api/v1/platform/commerce-orders/{order['id']}/transition",
            headers=write_headers("aiwave-partner-711shop", f"vivian-order-step-{step}"),
            json={"expected_version": order["version"], "status": status},
        )
        assert transitioned.status_code == 200, transitioned.text
        order = transitioned.json()["data"]
    assert order["status"] == "delivered"
    refunded = client.post(
        f"/api/v1/platform/payments/{payment['id']}/refund",
        headers=write_headers("aiwave-admin", "admin-refund-vivian"),
        json={"amount": 120, "points": 20},
    )
    assert refunded.status_code == 200
    assert refunded.json()["data"]["status"] == "refunded"
    assert refunded.json()["data"]["outcome"]["outcome"]["status"] == "reversed"
    assert client.get(
        "/api/v1/platform/points", headers=bearer("aiwave-vivian"),
    ).json()["data"]["balance"] == 180
