from __future__ import annotations

import pytest

from core.outcomes import SqliteOutcomeProjectionService
from core.points import SqlitePointsLedger


OWNER = {
    "demo_workspace_id": "demo-default",
    "workspace_id": "workspace-personal-demo-member",
    "account_id": "demo-member",
}


def _stack(tmp_path):
    points = SqlitePointsLedger(tmp_path / "outcomes.sqlite3")
    points.post(
        **OWNER, entry_type="earn", amount=180, description="seed",
        reference_type="seed", reference_id="demo", idempotency_key="seed-1",
    )
    service = SqliteOutcomeProjectionService(tmp_path / "outcomes.sqlite3", points=points)
    return service, points


def test_completion_is_once_only_and_member_projection_hides_provider_fee(tmp_path) -> None:
    service, points = _stack(tmp_path)
    result = service.project_status(
        owner=OWNER, subject_type="commerce_order", subject_id="order-1", provider_id="provider-a",
        status="delivered", event_id="status-event-1", amount=2000, summary="物品已送達",
        package_id="package-1",
    )
    assert result["outcome"]["status"] == "completed"
    assert result["achievementUnlocked"] is True
    assert result["rewards"][0]["amount"] == 20
    assert points.balance(**OWNER) == 200

    replay = service.project_status(
        owner=OWNER, subject_type="commerce_order", subject_id="order-1", provider_id="provider-a",
        status="delivered", event_id="status-event-2", amount=2000,
    )
    assert replay["idempotentReplay"] is True
    assert len(service.list_achievements(owner=OWNER)) == 1
    member = service.member_projection(owner=OWNER)
    assert "fees" not in member
    settlement = service.provider_settlement(demo_workspace_id="demo-default", provider_id="provider-a")
    assert settlement["fees"][0]["amount"] == 100
    assert settlement["officialRate"] is False


def test_cancel_after_completion_creates_compensating_reward_and_fee_entries(tmp_path) -> None:
    service, points = _stack(tmp_path)
    service.project_status(
        owner=OWNER, subject_type="booking", subject_id="booking-1", provider_id="provider-a",
        status="completed", event_id="status-event-1", amount=1000,
    )
    reversed_result = service.project_status(
        owner=OWNER, subject_type="booking", subject_id="booking-1", provider_id="provider-a",
        status="cancelled", event_id="status-event-cancelled",
    )
    assert reversed_result["outcome"]["status"] == "reversed"
    assert points.balance(**OWNER) == 180
    rewards = service.list_rewards(owner=OWNER)
    assert {row["kind"] for row in rewards} == {"grant", "reversal"}
    fees = service.provider_settlement(demo_workspace_id="demo-default", provider_id="provider-a")["fees"]
    assert {row["kind"] for row in fees} == {"charge", "reversal"}

    replay = service.project_status(
        owner=OWNER, subject_type="booking", subject_id="booking-1", provider_id="provider-a",
        status="cancelled", event_id="status-event-cancelled-again",
    )
    assert replay["idempotentReplay"] is True


def test_refund_is_a_reversal_state(tmp_path) -> None:
    service, points = _stack(tmp_path)
    service.project_status(
        owner=OWNER, subject_type="commerce_order", subject_id="order-refund", provider_id="provider-a",
        status="delivered", event_id="status-event-delivered", amount=1000,
    )
    reversed_result = service.project_status(
        owner=OWNER, subject_type="commerce_order", subject_id="order-refund", provider_id="provider-a",
        status="refunded", event_id="payment-refund-1",
    )
    assert reversed_result["outcome"]["status"] == "reversed"
    assert points.balance(**OWNER) == 180


def test_non_completion_does_not_create_outcome_or_reward(tmp_path) -> None:
    service, _ = _stack(tmp_path)
    ignored = service.project_status(
        owner=OWNER, subject_type="booking", subject_id="booking-pending", provider_id="provider-a",
        status="confirmed", event_id="status-event-1", amount=1000,
    )
    assert ignored["status"] == "ignored"
    assert service.member_projection(owner=OWNER)["outcomes"] == []
