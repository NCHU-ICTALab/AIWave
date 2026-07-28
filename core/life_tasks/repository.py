"""跨服務生活任務的 SQLite 聚合根。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LifeTaskRepositoryError(RuntimeError):
    pass


class SqliteLifeTaskRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _timestamp(self) -> str:
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.isoformat()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS life_tasks (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE,
                    account_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    utterance TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scheduled_date TEXT,
                    address_json TEXT,
                    scope TEXT,
                    points_json TEXT,
                    version INTEGER NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS life_task_items (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL,
                    task_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    need_summary TEXT NOT NULL,
                    vendor_id TEXT,
                    vendor_name TEXT,
                    base_price INTEGER,
                    slot TEXT,
                    candidates_json TEXT NOT NULL DEFAULT '[]',
                    external_inquiry_id TEXT,
                    external_order_id TEXT,
                    status TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES life_tasks(id)
                );
                CREATE INDEX IF NOT EXISTS idx_life_tasks_account ON life_tasks(account_id, seq DESC);
                CREATE INDEX IF NOT EXISTS idx_life_task_items_task ON life_task_items(task_id, seq);
                """
            )

    def create_draft(
        self, *, account_id: str, display_name: str, utterance: str,
        scheduled_date: str | None, items: list[dict[str, str]],
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO life_tasks
                   (id, account_id, display_name, utterance, status, scheduled_date,
                    address_json, scope, points_json, version, last_error, created_at, updated_at)
                   VALUES (NULL, ?, ?, ?, 'needs_details', ?, NULL, NULL, NULL, 1, NULL, ?, ?)""",
                (account_id, display_name, utterance, scheduled_date, timestamp, timestamp),
            )
            task_id = f"TASK-{self._now():%Y%m%d}-{cursor.lastrowid:03d}"
            connection.execute("UPDATE life_tasks SET id = ? WHERE seq = ?", (task_id, cursor.lastrowid))
            for index, item in enumerate(items, start=1):
                connection.execute(
                    """INSERT INTO life_task_items
                       (id, task_id, service_id, title, need_summary, status)
                       VALUES (?, ?, ?, ?, ?, 'draft')""",
                    (f"{task_id}-ITEM-{index}", task_id, item["serviceId"], item["title"], item["needSummary"]),
                )
        task = self.get(task_id)
        assert task is not None
        return task

    def find_open(self, *, account_id: str, utterance: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM life_tasks
                   WHERE account_id = ? AND utterance = ? AND status IN ('needs_details', 'ready')
                   ORDER BY seq DESC LIMIT 1""",
                (account_id, utterance),
            ).fetchone()
            return None if row is None else self._record(connection, row)

    @staticmethod
    def _decode(raw: str | None, fallback: Any = None) -> Any:
        return fallback if raw is None else json.loads(raw)

    def _record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        items = connection.execute(
            "SELECT * FROM life_task_items WHERE task_id = ? ORDER BY seq", (row["id"],),
        ).fetchall()
        return {
            "id": row["id"], "accountId": row["account_id"], "displayName": row["display_name"],
            "utterance": row["utterance"], "status": row["status"],
            "scheduledDate": row["scheduled_date"],
            "address": self._decode(row["address_json"]), "scope": row["scope"],
            "points": self._decode(row["points_json"]), "version": row["version"],
            "lastError": row["last_error"], "createdAt": row["created_at"], "updatedAt": row["updated_at"],
            "items": [{
                "id": item["id"], "serviceId": item["service_id"], "title": item["title"],
                "needSummary": item["need_summary"], "vendorId": item["vendor_id"],
                "vendorName": item["vendor_name"], "basePrice": item["base_price"],
                "slot": item["slot"], "candidates": self._decode(item["candidates_json"], []),
                "externalInquiryId": item["external_inquiry_id"],
                "externalOrderId": item["external_order_id"], "status": item["status"],
            } for item in items],
        }

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM life_tasks WHERE id = ?", (task_id,)).fetchone()
            return None if row is None else self._record(connection, row)

    def list_for_account(self, account_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM life_tasks WHERE account_id = ? ORDER BY seq DESC", (account_id,),
            ).fetchall()
            return [self._record(connection, row) for row in rows]

    def configure(
        self, task_id: str, *, expected_version: int, scheduled_date: str, address: dict[str, Any],
        scope: str, points: dict[str, Any], items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE life_tasks SET status = 'ready', scheduled_date = ?, address_json = ?,
                   scope = ?, points_json = ?, version = version + 1, last_error = NULL, updated_at = ?
                   WHERE id = ? AND version = ? AND status IN ('needs_details', 'ready')""",
                (scheduled_date, json.dumps(address, ensure_ascii=False), scope,
                 json.dumps(points, ensure_ascii=False), timestamp, task_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise LifeTaskRepositoryError("生活任務已被更新，請重新整理後再確認")
            for item in items:
                connection.execute(
                    """UPDATE life_task_items SET vendor_id = ?, vendor_name = ?, base_price = ?,
                       slot = ?, candidates_json = ?, status = 'ready' WHERE id = ? AND task_id = ?""",
                    (item["vendorId"], item["vendorName"], int(item["basePrice"]), item["slot"],
                     json.dumps(item["candidates"], ensure_ascii=False), item["id"], task_id),
                )
        task = self.get(task_id)
        assert task is not None
        return task

    def set_task_status(
        self, task_id: str, status: str, *, expected_version: int | None = None, error: str | None = None,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        where = "id = ?" if expected_version is None else "id = ? AND version = ?"
        values: list[Any] = [status, error, timestamp, task_id]
        if expected_version is not None:
            values.append(expected_version)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE life_tasks SET status = ?, last_error = ?, version = version + 1, updated_at = ? WHERE {where}",
                values,
            )
            if cursor.rowcount != 1:
                raise LifeTaskRepositoryError("生活任務已被更新，請重新整理後再確認")
        task = self.get(task_id)
        assert task is not None
        return task

    def set_external_inquiry(self, item_id: str, inquiry_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE life_task_items SET external_inquiry_id = ?, status = 'submitted' WHERE id = ?",
                (inquiry_id, item_id),
            )

    def set_external_order(self, item_id: str, order_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE life_task_items SET external_order_id = ?, status = 'ordered' WHERE id = ?",
                (order_id, item_id),
            )
