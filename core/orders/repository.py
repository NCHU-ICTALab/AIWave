"""平台自有訂單 repository；正式品牌 API 可在此邊界後接 Adapter。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path


class SqliteOrderRepository:
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
                CREATE TABLE IF NOT EXISTS platform_orders (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE,
                    account_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    answers TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    pricing TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS platform_order_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail TEXT
                );
                """
            )

    def create(self, *, account_id: str, service_id: str, answers: dict, pricing: dict) -> dict:
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        timestamp = moment.isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO platform_orders
                   (id, account_id, service_id, status, answers, amount, pricing, created_at)
                   VALUES (NULL, ?, ?, 'created', ?, ?, ?, ?)""",
                (
                    account_id,
                    service_id,
                    json.dumps(answers, ensure_ascii=False),
                    int(pricing["finalAmount"]),
                    json.dumps(pricing, ensure_ascii=False),
                    timestamp,
                ),
            )
            order_id = f"ORD-{moment:%Y%m%d}-{cursor.lastrowid:03d}"
            connection.execute("UPDATE platform_orders SET id = ? WHERE seq = ?", (order_id, cursor.lastrowid))
            connection.execute(
                "INSERT INTO platform_order_events (order_id, type, occurred_at, detail) VALUES (?, 'order.created', ?, ?)",
                (order_id, timestamp, f"NT${pricing['finalAmount']}"),
            )
        record = self.get(order_id)
        assert record is not None
        return record

    def _record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        events = connection.execute(
            "SELECT type, occurred_at, detail FROM platform_order_events WHERE order_id = ? ORDER BY seq",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"],
            "accountId": row["account_id"],
            "serviceId": row["service_id"],
            "status": row["status"],
            "statusLabel": "已建立，等待門市備貨" if row["status"] == "created" else row["status"],
            "officialStatus": "10",
            "amount": row["amount"],
            "answers": json.loads(row["answers"]),
            "pricing": json.loads(row["pricing"]),
            "pricingSource": "deterministic_rules",
            "createdAt": row["created_at"],
            "events": [dict(event) for event in events],
        }

    def get(self, order_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM platform_orders WHERE id = ?", (order_id,)).fetchone()
            return None if row is None else self._record(connection, row)

    def list_for_account(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM platform_orders WHERE account_id = ? ORDER BY seq DESC", (account_id,)
            ).fetchall()
            return [self._record(connection, row) for row in rows]
