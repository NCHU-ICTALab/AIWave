from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class PointsError(ValueError):
    pass


ENTRY_TYPES = {"earn", "redeem", "refund", "reversal", "expiry", "adjustment"}


class SqlitePointsLedger:
    """Single source of truth for the explicitly labelled Demo points wallet."""

    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _moment(self) -> datetime:
        value = self._now()
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    def _timestamp(self) -> str:
        return self._moment().isoformat()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS points_ledger (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    entry_type TEXT NOT NULL CHECK(entry_type IN ('earn','redeem','refund','reversal','expiry','adjustment')),
                    amount INTEGER NOT NULL CHECK(amount != 0),
                    description TEXT NOT NULL,
                    reference_type TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    expires_at TEXT,
                    reverses_entry_id TEXT,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_points_owner
                    ON points_ledger(demo_workspace_id,workspace_id,account_id,created_at);
                """
            )

    @staticmethod
    def _entry(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "type": row["entry_type"], "amount": row["amount"],
            "description": row["description"], "referenceType": row["reference_type"],
            "referenceId": row["reference_id"], "expiresAt": row["expires_at"],
            "reversesEntryId": row["reverses_entry_id"], "createdAt": row["created_at"],
        }

    def balance(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT COALESCE(SUM(amount),0) balance FROM points_ledger
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            return int(row["balance"])

    def list_entries(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM points_ledger
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?
                   ORDER BY created_at DESC,id DESC""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
            return {
                "label": "Demo OPENPOINT 情境帳本（非正式即時帳戶）",
                "balance": sum(int(row["amount"]) for row in rows),
                "entries": [self._entry(row) for row in rows],
            }

    def post(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        entry_type: str,
        amount: int,
        description: str,
        reference_type: str,
        reference_id: str,
        idempotency_key: str,
        expires_at: str | None = None,
        reverses_entry_id: str | None = None,
    ) -> dict:
        if entry_type not in ENTRY_TYPES:
            raise PointsError("未知的點數異動類型")
        if amount == 0 or not idempotency_key.strip():
            raise PointsError("點數異動金額與 Idempotency-Key 不可空白")
        if entry_type in {"earn", "refund"} and amount < 0:
            raise PointsError("取得或退回點數必須為正數")
        if entry_type in {"redeem", "expiry"} and amount > 0:
            raise PointsError("折抵或到期點數必須為負數")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM points_ledger WHERE demo_workspace_id=? AND idempotency_key=?",
                (demo_workspace_id, idempotency_key),
            ).fetchone()
            if existing:
                result = self._entry(existing)
                result["idempotentReplay"] = True
                return result
            balance = connection.execute(
                """SELECT COALESCE(SUM(amount),0) balance FROM points_ledger
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchone()["balance"]
            if int(balance) + amount < 0:
                raise PointsError("可用 Demo 點數不足")
            entry_id = f"points-{uuid4().hex[:16]}"
            connection.execute(
                """INSERT INTO points_ledger
                   (id,demo_workspace_id,workspace_id,account_id,entry_type,amount,description,
                    reference_type,reference_id,expires_at,reverses_entry_id,idempotency_key,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    entry_id, demo_workspace_id, workspace_id, account_id, entry_type, amount,
                    description, reference_type, reference_id, expires_at, reverses_entry_id,
                    idempotency_key, self._timestamp(),
                ),
            )
            row = connection.execute("SELECT * FROM points_ledger WHERE id=?", (entry_id,)).fetchone()
            result = self._entry(row)
            result["idempotentReplay"] = False
            return result

    def expire_due(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> list[dict]:
        now = self._timestamp()
        with self._connect() as connection:
            due = connection.execute(
                """SELECT * FROM points_ledger earn
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?
                     AND entry_type='earn' AND expires_at IS NOT NULL AND expires_at<=?
                     AND NOT EXISTS (
                       SELECT 1 FROM points_ledger expired
                       WHERE expired.demo_workspace_id=earn.demo_workspace_id
                         AND expired.reverses_entry_id=earn.id AND expired.entry_type='expiry'
                     ) ORDER BY expires_at,created_at""",
                (demo_workspace_id, workspace_id, account_id, now),
            ).fetchall()
        results = []
        for row in due:
            available = self.balance(
                demo_workspace_id=demo_workspace_id, workspace_id=workspace_id, account_id=account_id,
            )
            amount = min(int(row["amount"]), available)
            if amount <= 0:
                break
            results.append(self.post(
                demo_workspace_id=demo_workspace_id, workspace_id=workspace_id, account_id=account_id,
                entry_type="expiry", amount=-amount,
                description=f"{row['description']}到期", reference_type="points_entry",
                reference_id=row["id"], reverses_entry_id=row["id"],
                idempotency_key=f"expire:{row['id']}",
            ))
        return results

