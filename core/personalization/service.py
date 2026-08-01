"""可撤回的個人化回饋、補貨建議與提醒。

官方訂單只提供行為證據；競賽用點數／優惠券帳本明確標示為 seed。AI、HTTP 與 MCP
都只呼叫這個服務，不直接改推薦狀態。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from core.data.official_orders import orders_for
from core.services.pricing import calculate_quote


class SqlitePersonalizationRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    account_id TEXT NOT NULL,
                    recommendation_id TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, recommendation_id)
                );
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    cadence_days INTEGER NOT NULL,
                    next_due_on TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL
                );
                """
            )

    def _timestamp(self) -> str:
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.isoformat()

    def set_feedback(self, account_id: str, recommendation_id: str, *, active: bool) -> dict:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO recommendation_feedback (account_id, recommendation_id, active, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account_id, recommendation_id) DO UPDATE SET
                    active = excluded.active, updated_at = excluded.updated_at
                """,
                (account_id, recommendation_id, int(active), self._timestamp()),
            )
        return {"recommendationId": recommendation_id, "active": active, "signal": "soft_preference"}

    def is_suppressed(self, account_id: str, recommendation_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT active FROM recommendation_feedback WHERE account_id = ? AND recommendation_id = ?",
                (account_id, recommendation_id),
            ).fetchone()
        return bool(row and row["active"])

    def create_reminder(
        self, account_id: str, *, item_name: str, cadence_days: int, next_due_on: str
    ) -> dict:
        if cadence_days < 1 or cadence_days > 365:
            raise ValueError("補貨週期須介於 1–365 天")
        date.fromisoformat(next_due_on)
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO reminders
                   (account_id, item_name, cadence_days, next_due_on, status, created_at)
                   VALUES (?, ?, ?, ?, 'active', ?)""",
                (account_id, item_name.strip(), cadence_days, next_due_on, self._timestamp()),
            )
            reminder_id = cursor.lastrowid
        return self.get_reminder(reminder_id)

    def get_reminder(self, reminder_id: int) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        assert row is not None
        return {
            "id": row["id"],
            "itemName": row["item_name"],
            "cadenceDays": row["cadence_days"],
            "nextDueOn": row["next_due_on"],
            "status": row["status"],
            "createdAt": row["created_at"],
        }

    def list_reminders(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM reminders WHERE account_id = ? AND status = 'active' ORDER BY next_due_on, id",
                (account_id,),
            ).fetchall()
        return [self.get_reminder(row["id"]) for row in rows]


class PersonalizationService:
    RECOMMENDATION_ID = "restock-monthly"

    def __init__(self, repository: SqlitePersonalizationRepository, *, today: date) -> None:
        self.repository = repository
        self.today = today

    def restock_plan(self, account_id: str, *, openpoint_balance: int = 0) -> dict:
        history = orders_for(account_id)
        shopping = [order for order in history if order.catalog_service_id == "service-shopping"]
        evidence_orders = (shopping or history)[-3:]
        quote = calculate_quote(
            "service-shopping",
            {
                "bundle": "restock", "coupon": "apply",
                "points": "50" if openpoint_balance >= 50 else "0",
                "payment": "icash-pay",
            },
        ).to_dict()
        return {
            "recommendation": {
                "id": self.RECOMMENDATION_ID,
                "title": "月初日用品補貨",
                "serviceId": "service-shopping",
                "reasonText": (
                    f"依你的 {len(shopping)} 筆商城購物紀錄整理補貨時機。"
                    if shopping
                    else "依你的跨服務紀錄提供可調整的月初補貨建議。"
                ),
                "suppressed": self.repository.is_suppressed(account_id, self.RECOMMENDATION_ID),
            },
            "wallet": {
                "openpointBalance": openpoint_balance,
                "coupon": {"id": "seed-restock-70", "label": "日用品滿額折 NT$70", "amount": 70},
                "payment": "icash Pay",
                "dataSource": "demo_points_ledger",
            },
            "bestOffer": {
                "baseAmount": quote["baseAmount"],
                "finalAmount": quote["finalAmount"],
                "savedAmount": quote["baseAmount"] - quote["finalAmount"],
                "applied": quote["ruleSummary"],
                "computedBy": "deterministic_rules",
            },
            "evidence": [
                {
                    "recordId": order.record_id,
                    "orderNo": order.order_no,
                    "serviceName": order.service_name,
                    "occurredOn": order.order_time.date().isoformat() if order.order_time else None,
                }
                for order in evidence_orders
            ],
            "source": "official_orders+demo_points_ledger+competition_seed_coupon",
        }

    def feedback(self, account_id: str, recommendation_id: str, action: str) -> dict:
        if action not in {"dismiss", "undo"}:
            raise ValueError("推薦回饋只能是 dismiss 或 undo")
        return self.repository.set_feedback(account_id, recommendation_id, active=action == "dismiss")

    def is_suppressed(self, account_id: str, recommendation_id: str) -> bool:
        return self.repository.is_suppressed(account_id, recommendation_id)

    def create_reminder(self, account_id: str, *, item_name: str, cadence_days: int, next_due_on: str) -> dict:
        if not item_name.strip():
            raise ValueError("請填寫要提醒補貨的品項")
        return self.repository.create_reminder(
            account_id, item_name=item_name, cadence_days=cadence_days, next_due_on=next_due_on
        )

    def list_reminders(self, account_id: str) -> list[dict]:
        return self.repository.list_reminders(account_id)
