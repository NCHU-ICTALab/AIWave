from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.points import PointsError, SqlitePointsLedger


class DemoPaymentError(ValueError):
    pass


class SqliteDemoPaymentAdapter:
    """A resettable payment simulator that never accepts or stores card data."""

    def __init__(
        self,
        path: str | Path,
        *,
        points: SqlitePointsLedger,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.points = points
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _timestamp(self) -> str:
        value = self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS demo_payments (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    currency TEXT NOT NULL CHECK(currency='TWD'),
                    amount INTEGER NOT NULL CHECK(amount>=0),
                    points_redeemed INTEGER NOT NULL CHECK(points_redeemed>=0),
                    refunded_amount INTEGER NOT NULL DEFAULT 0 CHECK(refunded_amount>=0),
                    refunded_points INTEGER NOT NULL DEFAULT 0 CHECK(refunded_points>=0),
                    status TEXT NOT NULL CHECK(status IN ('pending','succeeded','failed','cancelled','partially_refunded','refunded')),
                    failure_code TEXT,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS demo_payment_events (
                    id TEXT PRIMARY KEY,
                    payment_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    points INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(payment_id,idempotency_key),
                    FOREIGN KEY(payment_id) REFERENCES demo_payments(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "label": "Demo 支付（未連接真實金流）",
            "demoWorkspaceId": row["demo_workspace_id"], "workspaceId": row["workspace_id"],
            "accountId": row["account_id"], "subjectType": row["subject_type"],
            "subjectId": row["subject_id"], "currency": row["currency"],
            "amount": row["amount"], "pointsRedeemed": row["points_redeemed"],
            "refundedAmount": row["refunded_amount"], "refundedPoints": row["refunded_points"],
            "status": row["status"], "failureCode": row["failure_code"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    def get_owned(
        self,
        payment_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM demo_payments
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (payment_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise DemoPaymentError("查無 Demo 支付")
            return self._record(row)

    def list_by_subject(
        self,
        *,
        demo_workspace_id: str,
        subject_type: str,
        subject_id: str,
    ) -> list[dict]:
        """取消/退款流程用:找出某筆交易主體的所有 Demo 支付。"""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM demo_payments
                   WHERE demo_workspace_id=? AND subject_type=? AND subject_id=?
                   ORDER BY created_at,id""",
                (demo_workspace_id, subject_type, subject_id),
            ).fetchall()
            return [self._record(row) for row in rows]

    def get_in_demo(self, payment_id: str, *, demo_workspace_id: str) -> dict:
        """Operator lookup bounded to one isolated DemoWorkspace.

        The owner is derived from the persisted payment.  An admin endpoint must not
        guess a fixed persona or accept owner identifiers supplied by the caller.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM demo_payments WHERE id=? AND demo_workspace_id=?",
                (payment_id, demo_workspace_id),
            ).fetchone()
            if row is None:
                raise DemoPaymentError("查無 Demo 支付")
            return self._record(row)

    def create(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        subject_type: str,
        subject_id: str,
        amount: int,
        points_redeemed: int,
        outcome: str,
        idempotency_key: str,
    ) -> dict:
        if amount < 0 or points_redeemed < 0 or points_redeemed > amount:
            raise DemoPaymentError("支付或點數折抵金額不合法")
        if outcome not in {"pending", "success", "failure"}:
            raise DemoPaymentError("Demo outcome 只接受 pending、success 或 failure")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM demo_payments WHERE demo_workspace_id=? AND idempotency_key=?",
                (demo_workspace_id, idempotency_key),
            ).fetchone()
            if existing:
                result = self._record(existing)
                result["idempotentReplay"] = True
                return result
        if outcome == "success" and points_redeemed:
            try:
                self.points.post(
                    demo_workspace_id=demo_workspace_id, workspace_id=workspace_id, account_id=account_id,
                    entry_type="redeem", amount=-points_redeemed,
                    description=f"Demo 支付折抵：{subject_id}", reference_type=subject_type,
                    reference_id=subject_id, idempotency_key=f"payment:{idempotency_key}:redeem",
                )
            except PointsError as exc:
                raise DemoPaymentError(str(exc)) from exc
        status = {"pending": "pending", "success": "succeeded", "failure": "failed"}[outcome]
        payment_id = f"payment-{uuid4().hex[:16]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO demo_payments
                   (id,demo_workspace_id,workspace_id,account_id,subject_type,subject_id,currency,amount,
                    points_redeemed,status,failure_code,idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,'TWD',?,?,?,?,?,?,?)""",
                (
                    payment_id, demo_workspace_id, workspace_id, account_id, subject_type, subject_id,
                    amount, points_redeemed, status,
                    "DEMO_DECLINED" if outcome == "failure" else None,
                    idempotency_key, timestamp, timestamp,
                ),
            )
            connection.execute(
                """INSERT INTO demo_payment_events
                   (id,payment_id,event_type,amount,points,idempotency_key,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (f"payment-event-{uuid4().hex[:12]}", payment_id, status, amount, points_redeemed, f"{idempotency_key}:event", timestamp),
            )
            row = connection.execute("SELECT * FROM demo_payments WHERE id=?", (payment_id,)).fetchone()
            result = self._record(row)
            result["idempotentReplay"] = False
            return result

    def cancel(
        self,
        payment_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        idempotency_key: str,
    ) -> dict:
        payment = self.get_owned(
            payment_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, account_id=account_id,
        )
        if payment["status"] == "cancelled":
            return {**payment, "idempotentReplay": True}
        if payment["status"] != "pending":
            raise DemoPaymentError("只有等待中的 Demo 支付可以取消")
        with self._connect() as connection:
            connection.execute(
                "UPDATE demo_payments SET status='cancelled',updated_at=? WHERE id=?",
                (self._timestamp(), payment_id),
            )
            row = connection.execute("SELECT * FROM demo_payments WHERE id=?", (payment_id,)).fetchone()
            return {**self._record(row), "idempotentReplay": False}

    def refund(
        self,
        payment_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        amount: int,
        points: int,
        idempotency_key: str,
    ) -> dict:
        payment = self.get_owned(
            payment_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, account_id=account_id,
        )
        if payment["status"] not in {"succeeded", "partially_refunded"}:
            raise DemoPaymentError("此 Demo 支付不可退款")
        remaining_amount = payment["amount"] - payment["refundedAmount"]
        remaining_points = payment["pointsRedeemed"] - payment["refundedPoints"]
        if amount < 0 or points < 0 or amount > remaining_amount or points > remaining_points:
            raise DemoPaymentError("退款或點數退回超過可退範圍")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM demo_payment_events WHERE payment_id=? AND idempotency_key=?",
                (payment_id, idempotency_key),
            ).fetchone()
            if existing:
                return {**self.get_owned(
                    payment_id, demo_workspace_id=demo_workspace_id,
                    workspace_id=workspace_id, account_id=account_id,
                ), "idempotentReplay": True}
        if points:
            self.points.post(
                demo_workspace_id=demo_workspace_id, workspace_id=workspace_id, account_id=account_id,
                entry_type="refund", amount=points, description=f"Demo 支付退款：{payment_id}",
                reference_type="payment", reference_id=payment_id,
                idempotency_key=f"refund:{idempotency_key}:points",
            )
        new_refunded_amount = payment["refundedAmount"] + amount
        new_refunded_points = payment["refundedPoints"] + points
        status = "refunded" if (
            new_refunded_amount == payment["amount"] and new_refunded_points == payment["pointsRedeemed"]
        ) else "partially_refunded"
        with self._connect() as connection:
            connection.execute(
                """UPDATE demo_payments SET refunded_amount=?,refunded_points=?,status=?,updated_at=? WHERE id=?""",
                (new_refunded_amount, new_refunded_points, status, self._timestamp(), payment_id),
            )
            connection.execute(
                """INSERT INTO demo_payment_events
                   (id,payment_id,event_type,amount,points,idempotency_key,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    f"payment-event-{uuid4().hex[:12]}", payment_id, "refund",
                    amount, points, idempotency_key, self._timestamp(),
                ),
            )
            row = connection.execute("SELECT * FROM demo_payments WHERE id=?", (payment_id,)).fetchone()
            return {**self._record(row), "idempotentReplay": False}
