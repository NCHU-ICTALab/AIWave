from __future__ import annotations

from datetime import datetime, timezone

from core.proactive_care import CarePreferences, evaluate_delivery
from core.proactive_care import ProactiveCareService


DEMO_CANDIDATE = {
    "kind": "life_preparation",
    "evidence": {"source": "competition_demo_event"},
}


def test_care_policy_separates_transaction_counter_and_blocks_unknown_sources() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    transaction = evaluate_delivery(
        {"kind": "transaction", "evidence": {"source": "internal"}},
        preferences=CarePreferences(), now=now,
    )
    assert transaction.allowed is True
    assert transaction.reason == "transaction_counter_is_separate"

    unknown = evaluate_delivery(
        {"kind": "life_preparation", "evidence": {"source": "purchase_inference"}},
        preferences=CarePreferences(), now=now,
    )
    assert unknown.to_dict()["reason"] == "source_not_allowlisted"


def test_care_policy_applies_category_override_and_frequency_window() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    preferences = CarePreferences(
        mode="balanced", category_overrides={"life_preparation": "low"},
    )
    recent = [{"kind": "life_preparation", "deliveredAt": "2026-07-20T12:00:00+00:00"}]
    decision = evaluate_delivery(
        DEMO_CANDIDATE, preferences=preferences, now=now, recent_deliveries=recent,
    )
    assert decision.allowed is False
    assert decision.reason == "frequency_limit"


def test_care_policy_blocks_non_in_app_delivery_during_quiet_hours() -> None:
    now = datetime(2026, 8, 1, 23, 0, tzinfo=timezone.utc)
    decision = evaluate_delivery(
        DEMO_CANDIDATE,
        preferences=CarePreferences(channel="push"),
        now=now,
    )
    assert decision.allowed is False
    assert decision.reason == "quiet_hours"
    assert decision.next_eligible_at


def test_care_service_applies_policy_before_delivery_and_reads_without_side_effect(tmp_path) -> None:
    now = datetime(2026, 8, 1, 23, tzinfo=timezone.utc)
    service = ProactiveCareService(tmp_path / "policy.sqlite3", now=lambda: now)
    owner = {
        "demo_workspace_id": "demo-default",
        "workspace_id": "workspace-personal-demo-member",
        "account_id": "demo-member",
    }
    service.generate_candidates(**owner)
    assert service.list_messages(**owner) == []
    assert service.deliver(**owner, preferences=CarePreferences(channel="push")) == []
    assert service.list_messages(**owner) == []
    assert service.deliver(**owner, preferences=CarePreferences(channel="in_app"))
    message = service.list_messages(**owner)[0]
    assert service.act(message["id"], **owner, action="snooze")["state"] == "snoozed"
    assert service.list_messages(**owner) == []
