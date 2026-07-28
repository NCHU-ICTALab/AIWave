"""平台自有客服工單與事件 repository。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class SupportError(ValueError):
    """客服工單不存在、重複或狀態轉換不合法。"""


class SupportRepository(Protocol):
    def create(self, **fields) -> dict: ...
    def get(self, ticket_id: str) -> dict | None: ...
    def list_for_account(self, account_id: str) -> list[dict]: ...
    def list_queue(self) -> list[dict]: ...
    def transition(self, ticket_id: str, *, target: str, actor: str, note: str | None = None) -> dict: ...


STATUS_LABELS = {
    "open": "等待客服處理",
    "in_progress": "客服處理中",
    "resolved": "已處理完成",
}
ALLOWED_TRANSITIONS = {
    "open": {"in_progress"},
    "in_progress": {"resolved"},
    "resolved": set(),
}


class SqliteSupportRepository:
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
                CREATE TABLE IF NOT EXISTS support_tickets (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE,
                    account_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    category_label TEXT NOT NULL,
                    issue_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    recommended_route TEXT NOT NULL,
                    sla_hours INTEGER NOT NULL,
                    due_at TEXT NOT NULL,
                    subject_snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS support_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets(id)
                );
                CREATE INDEX IF NOT EXISTS idx_support_account ON support_tickets(account_id, seq DESC);
                CREATE INDEX IF NOT EXISTS idx_support_subject ON support_tickets(subject_id, status);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_support_one_active_subject
                    ON support_tickets(account_id, subject_id)
                    WHERE status IN ('open', 'in_progress');
                """
            )

    def _moment(self) -> datetime:
        moment = self._now()
        return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)

    def _event(
        self,
        connection: sqlite3.Connection,
        ticket_id: str,
        event_type: str,
        actor: str,
        detail: str | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO support_events (ticket_id, type, actor, occurred_at, detail) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, event_type, actor, self._moment().isoformat(), detail),
        )

    def create(
        self,
        *,
        account_id: str,
        subject_type: str,
        subject_id: str,
        category: str,
        category_label: str,
        issue_text: str,
        priority: str,
        recommended_route: str,
        sla_hours: int,
        due_at: str,
        subject_snapshot: dict,
    ) -> dict:
        moment = self._moment()
        timestamp = moment.isoformat()
        with self._connect() as connection:
            duplicate = connection.execute(
                "SELECT id FROM support_tickets WHERE account_id = ? AND subject_id = ? AND status IN ('open', 'in_progress')",
                (account_id, subject_id),
            ).fetchone()
            if duplicate:
                raise SupportError(f"這筆訂單已有處理中的客服工單 {duplicate['id']}")
            try:
                cursor = connection.execute(
                    """INSERT INTO support_tickets
                       (id, account_id, subject_type, subject_id, category, category_label, issue_text,
                        status, priority, recommended_route, sla_hours, due_at, subject_snapshot, created_at, updated_at)
                       VALUES (NULL, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        account_id, subject_type, subject_id, category, category_label, issue_text,
                        priority, recommended_route, sla_hours, due_at,
                        json.dumps(subject_snapshot, ensure_ascii=False), timestamp, timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise SupportError("這筆訂單已有處理中的客服工單") from exc
            ticket_id = f"SUP-{moment:%Y%m%d}-{cursor.lastrowid:03d}"
            connection.execute("UPDATE support_tickets SET id = ? WHERE seq = ?", (ticket_id, cursor.lastrowid))
            self._event(connection, ticket_id, "support.created", "住戶", issue_text)
        record = self.get(ticket_id)
        assert record is not None
        return record

    def _record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        events = connection.execute(
            "SELECT type, actor, occurred_at, detail FROM support_events WHERE ticket_id = ? ORDER BY seq",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"],
            "accountId": row["account_id"],
            "subjectType": row["subject_type"],
            "subjectId": row["subject_id"],
            "category": row["category"],
            "categoryLabel": row["category_label"],
            "issueText": row["issue_text"],
            "status": row["status"],
            "statusLabel": STATUS_LABELS[row["status"]],
            "priority": row["priority"],
            "recommendedRoute": row["recommended_route"],
            "slaHours": row["sla_hours"],
            "dueAt": row["due_at"],
            "subject": json.loads(row["subject_snapshot"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "asOf": self._moment().isoformat(),
            "events": [dict(event) for event in events],
        }

    def get(self, ticket_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
            return None if row is None else self._record(connection, row)

    def list_for_account(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM support_tickets WHERE account_id = ? ORDER BY seq DESC", (account_id,)
            ).fetchall()
            return [self._record(connection, row) for row in rows]

    def list_queue(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM support_tickets
                   WHERE status IN ('open', 'in_progress')
                   ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, seq"""
            ).fetchall()
            return [self._record(connection, row) for row in rows]

    def transition(self, ticket_id: str, *, target: str, actor: str, note: str | None = None) -> dict:
        actor_name = actor.strip()
        if not actor_name:
            raise SupportError("處理人員不可空白")
        if target == "resolved" and not (note or "").strip():
            raise SupportError("完成工單前請填寫處理結果")
        with self._connect() as connection:
            row = connection.execute("SELECT status FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise SupportError(f"查無客服工單 {ticket_id}")
            current = row["status"]
            if target not in ALLOWED_TRANSITIONS.get(current, set()):
                raise SupportError(f"工單目前是「{STATUS_LABELS.get(current, current)}」，無法轉為「{STATUS_LABELS.get(target, target)}」")
            timestamp = self._moment().isoformat()
            updated = connection.execute(
                "UPDATE support_tickets SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                (target, timestamp, ticket_id, current),
            )
            if updated.rowcount != 1:
                raise SupportError("工單狀態剛被其他人更新，請重新載入後再試")
            self._event(connection, ticket_id, f"support.{target}", actor_name, (note or "").strip() or None)
        record = self.get(ticket_id)
        assert record is not None
        return record
