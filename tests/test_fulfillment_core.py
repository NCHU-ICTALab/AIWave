from __future__ import annotations

import pytest

from core.fulfillment import FulfillmentConflict, FulfillmentError, SqliteFulfillmentRepository


OWNER = {
    "demo_workspace_id": "demo-a",
    "workspace_id": "workspace-personal-a",
    "account_id": "a",
}


def test_booking_has_provider_slot_timeline_and_formal_reschedule(tmp_path):
    repository = SqliteFulfillmentRepository(tmp_path / "platform.sqlite3")
    booking = repository.create_booking(
        **OWNER,
        provider_id="provider-a", location_id="location-a", offering_id="offering-a",
        resource_id="staff-a", slot_id="slot-a",
        starts_at="2026-08-01T09:00:00+08:00", ends_at="2026-08-01T10:00:00+08:00",
        idempotency_key="booking-once",
    )
    confirmed = repository.transition_booking(
        booking["id"], demo_workspace_id="demo-a", provider_id="provider-a",
        expected_version=1, to_status="confirmed", actor_account_id="staff",
        idempotency_key="confirm-once",
    )
    request = repository.request_reschedule(
        booking["id"], **OWNER,
        slot_id="slot-b", starts_at="2026-08-02T14:00:00+08:00",
        ends_at="2026-08-02T15:00:00+08:00", reason="臨時有事",
        idempotency_key="reschedule-once",
    )
    reviewed = repository.review_reschedule(
        request["id"], demo_workspace_id="demo-a", provider_id="provider-a",
        actor_account_id="staff", accept=True, idempotency_key="accept-reschedule",
    )
    final = repository.get_booking(
        booking["id"], **OWNER,
    )

    assert confirmed["status"] == "confirmed"
    assert reviewed["status"] == "accepted"
    assert final["slotId"] == "slot-b"
    assert [event["type"] for event in final["events"]] == [
        "booking_created", "booking_confirmed", "booking_rescheduled",
    ]


def test_booking_provider_and_workspace_isolation(tmp_path):
    repository = SqliteFulfillmentRepository(tmp_path / "platform.sqlite3")
    booking = repository.create_booking(
        **OWNER,
        provider_id="provider-a", location_id="location-a", offering_id="offering-a",
        resource_id=None, slot_id="slot-a", starts_at="2026-08-01T09:00:00+08:00",
        ends_at="2026-08-01T10:00:00+08:00", idempotency_key="booking-once",
    )
    with pytest.raises(FulfillmentError, match="查無預約"):
        repository.get_booking(
            booking["id"], demo_workspace_id="demo-b", workspace_id="workspace-personal-b", account_id="b",
        )
    with pytest.raises(FulfillmentError, match="查無預約"):
        repository.transition_booking(
            booking["id"], demo_workspace_id="demo-a", provider_id="provider-b",
            expected_version=1, to_status="confirmed", actor_account_id="other-staff",
            idempotency_key="wrong-provider",
        )


def test_commerce_order_is_separate_aggregate_and_idempotent(tmp_path):
    repository = SqliteFulfillmentRepository(tmp_path / "platform.sqlite3")
    order = repository.create_order(
        **OWNER, provider_id="provider-shop",
        items=[{"offeringId": "sku-a", "name": "商品 A", "quantity": 2, "unitPrice": 100}],
        discount=20, idempotency_key="order-once",
    )
    replay = repository.create_order(
        **OWNER, provider_id="provider-shop",
        items=[{"offeringId": "sku-a", "name": "商品 A", "quantity": 2, "unitPrice": 100}],
        discount=20, idempotency_key="order-once",
    )
    assert order["total"] == 180
    assert replay["id"] == order["id"]
    assert replay["idempotentReplay"] is True
    with pytest.raises(FulfillmentConflict):
        repository.transition_order(
            order["id"], demo_workspace_id="demo-a", provider_id="provider-shop",
            expected_version=1, to_status="delivered", actor_account_id="staff",
            idempotency_key="skip-states",
        )

