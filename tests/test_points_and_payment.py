from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.payments import DemoPaymentError, SqliteDemoPaymentAdapter
from core.points import SqlitePointsLedger


OWNER = {"demo_workspace_id": "demo-a", "workspace_id": "workspace-a", "account_id": "a"}


def test_points_ledger_is_single_idempotent_source_with_expiry(tmp_path):
    ledger = SqlitePointsLedger(
        tmp_path / "platform.sqlite3",
        now=lambda: datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    earned = ledger.post(
        **OWNER, entry_type="earn", amount=200, description="Demo 消費回饋",
        reference_type="order", reference_id="order-a", idempotency_key="earn-once",
        expires_at="2026-08-01T00:00:00+00:00",
    )
    replay = ledger.post(
        **OWNER, entry_type="earn", amount=200, description="Demo 消費回饋",
        reference_type="order", reference_id="order-a", idempotency_key="earn-once",
    )
    assert replay["id"] == earned["id"]
    assert ledger.balance(**OWNER) == 200
    expired = ledger.expire_due(**OWNER)
    assert expired[0]["amount"] == -200
    assert ledger.list_entries(**OWNER)["balance"] == 0
    assert "非正式" in ledger.list_entries(**OWNER)["label"]


def test_demo_payment_success_failure_cancel_and_refund_reverse_points(tmp_path):
    path = tmp_path / "platform.sqlite3"
    ledger = SqlitePointsLedger(path)
    payment = SqliteDemoPaymentAdapter(path, points=ledger)
    ledger.post(
        **OWNER, entry_type="earn", amount=500, description="Demo 初始點數",
        reference_type="seed", reference_id="seed", idempotency_key="seed-points",
    )

    succeeded = payment.create(
        **OWNER, subject_type="commerce_order", subject_id="order-a",
        amount=1000, points_redeemed=200, outcome="success", idempotency_key="pay-success",
    )
    failed = payment.create(
        **OWNER, subject_type="commerce_order", subject_id="order-b",
        amount=300, points_redeemed=0, outcome="failure", idempotency_key="pay-failure",
    )
    pending = payment.create(
        **OWNER, subject_type="booking", subject_id="booking-a",
        amount=500, points_redeemed=0, outcome="pending", idempotency_key="pay-pending",
    )
    cancelled = payment.cancel(pending["id"], **OWNER, idempotency_key="cancel-once")
    refunded = payment.refund(
        succeeded["id"], **OWNER, amount=1000, points=200, idempotency_key="refund-once",
    )

    assert succeeded["status"] == "succeeded"
    assert failed["status"] == "failed"
    assert cancelled["status"] == "cancelled"
    assert refunded["status"] == "refunded"
    assert ledger.balance(**OWNER) == 500
    assert "Demo 支付" in refunded["label"]
    with pytest.raises(DemoPaymentError):
        payment.cancel(succeeded["id"], **OWNER, idempotency_key="bad-cancel")

