"""社區團購：管委會開團、住戶跟團、到期結單。

**社區是範圍不是角色**（ADR-0003）：同一檔活動，住戶看到的是「可以跟團」，
管委會看到的是「誰跟了、要不要結單」——資料只有一份。

狀態：`open`（收單中）→ `closed`（已結單，產出給廠商的彙總）→ `fulfilled`（已到貨）。

註：[ADR-0001](../../docs/adr/0001-groupbuy-per-household-orders.md) 決定每筆跟團最終
要對應一筆官方 `order_type 07` 訂單。訂單模型尚未建立，因此目前先以 `group_buy_joins`
記錄；待訂單模型落地時，這裡是唯一需要改寫的地方。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

OPEN = "open"
CLOSED = "closed"
FULFILLED = "fulfilled"

STATUS_LABEL = {OPEN: "收單中", CLOSED: "已結單", FULFILLED: "已到貨"}

ALLOWED_TRANSITIONS = {OPEN: {CLOSED}, CLOSED: {FULFILLED}, FULFILLED: set()}


class GroupBuyError(ValueError):
    """團購操作錯誤（如對已結單的活動跟團）。"""


class GroupBuyRepository(Protocol):
    def create_campaign(self, **kwargs) -> dict: ...
    def list_campaigns(self, *, status: str | None = ...) -> list[dict]: ...
    def get_campaign(self, campaign_id: int) -> dict | None: ...
    def join(self, campaign_id: int, *, account_id: str, display_name: str, quantity: int) -> dict: ...
    def close_campaign(self, campaign_id: int) -> dict: ...


class SqliteGroupBuyRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS group_buy_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    unit_price INTEGER NOT NULL,
                    unit TEXT NOT NULL DEFAULT '份',
                    min_quantity INTEGER NOT NULL DEFAULT 1,
                    close_time TEXT,
                    pickup TEXT,
                    status TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS group_buy_joins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    account_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    joined_at TEXT NOT NULL,
                    FOREIGN KEY (campaign_id) REFERENCES group_buy_campaigns(id)
                );
                """
            )

    def _timestamp(self) -> str:
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.isoformat()

    # ---- 讀取 ----------------------------------------------------------

    def _campaign_record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        joins = connection.execute(
            "SELECT account_id, display_name, quantity, joined_at FROM group_buy_joins WHERE campaign_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        total_quantity = sum(join["quantity"] for join in joins)
        return {
            "id": row["id"],
            "title": row["title"],
            "itemName": row["item_name"],
            "unitPrice": row["unit_price"],
            "unit": row["unit"],
            "minQuantity": row["min_quantity"],
            "closeTime": row["close_time"],
            "pickup": row["pickup"],
            "status": row["status"],
            "statusLabel": STATUS_LABEL.get(row["status"], row["status"]),
            "createdAt": row["created_at"],
            "closedAt": row["closed_at"],
            "householdCount": len({join["account_id"] for join in joins}),
            "totalQuantity": total_quantity,
            "totalAmount": total_quantity * row["unit_price"],
            "reachedMinimum": total_quantity >= row["min_quantity"],
            "joins": [dict(join) for join in joins],
        }

    def list_campaigns(self, *, status: str | None = None) -> list[dict]:
        with self._connect() as connection:
            query = "SELECT * FROM group_buy_campaigns"
            params: tuple = ()
            if status:
                query += " WHERE status = ?"
                params = (status,)
            query += " ORDER BY id DESC"
            rows = connection.execute(query, params).fetchall()
            return [self._campaign_record(connection, row) for row in rows]

    def get_campaign(self, campaign_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM group_buy_campaigns WHERE id = ?", (campaign_id,)).fetchone()
            return None if row is None else self._campaign_record(connection, row)

    # ---- 寫入 ----------------------------------------------------------

    def create_campaign(
        self,
        *,
        title: str,
        item_name: str,
        unit_price: int,
        unit: str = "份",
        min_quantity: int = 1,
        close_time: str | None = None,
        pickup: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO group_buy_campaigns
                    (title, item_name, unit_price, unit, min_quantity, close_time, pickup, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, item_name, unit_price, unit, min_quantity, close_time, pickup, OPEN, created_by, self._timestamp()),
            )
            campaign_id = int(cursor.lastrowid)
        record = self.get_campaign(campaign_id)
        assert record is not None
        return record

    def join(self, campaign_id: int, *, account_id: str, display_name: str, quantity: int) -> dict:
        """住戶跟團；同一帳號重複跟團就更新數量，而不是產生兩筆。"""
        if quantity < 1:
            raise GroupBuyError("數量至少 1")
        with self._connect() as connection:
            row = connection.execute("SELECT status FROM group_buy_campaigns WHERE id = ?", (campaign_id,)).fetchone()
            if row is None:
                raise GroupBuyError(f"查無團購活動 {campaign_id}")
            if row["status"] != OPEN:
                raise GroupBuyError(f"這檔團購已「{STATUS_LABEL.get(row['status'], row['status'])}」，無法再跟團")
            existing = connection.execute(
                "SELECT id FROM group_buy_joins WHERE campaign_id = ? AND account_id = ?",
                (campaign_id, account_id),
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE group_buy_joins SET quantity = ?, joined_at = ? WHERE id = ?",
                    (quantity, self._timestamp(), existing["id"]),
                )
            else:
                connection.execute(
                    "INSERT INTO group_buy_joins (campaign_id, account_id, display_name, quantity, joined_at) VALUES (?, ?, ?, ?, ?)",
                    (campaign_id, account_id, display_name, quantity, self._timestamp()),
                )
        record = self.get_campaign(campaign_id)
        assert record is not None
        return record

    def close_campaign(self, campaign_id: int) -> dict:
        """結單：停止收單，產出給廠商的採購彙總。"""
        with self._connect() as connection:
            row = connection.execute("SELECT status FROM group_buy_campaigns WHERE id = ?", (campaign_id,)).fetchone()
            if row is None:
                raise GroupBuyError(f"查無團購活動 {campaign_id}")
            if CLOSED not in ALLOWED_TRANSITIONS.get(row["status"], set()):
                raise GroupBuyError(f"這檔團購已「{STATUS_LABEL.get(row['status'], row['status'])}」，無法重複結單")
            connection.execute(
                "UPDATE group_buy_campaigns SET status = ?, closed_at = ? WHERE id = ?",
                (CLOSED, self._timestamp(), campaign_id),
            )
        record = self.get_campaign(campaign_id)
        assert record is not None
        return record
