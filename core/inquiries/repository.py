"""Persistent inquiry repository.

SQLite is the local implementation; the interface is intentionally small so AWS can
replace it with an RDS/Postgres adapter without changing Agent or HTTP workflows.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class InquiryRepository(Protocol):
    def create(self, *, form_id: int, feedback_content: dict) -> dict: ...
    def get(self, inquiry_id: str) -> dict | None: ...
    def list_all(self) -> list[dict]: ...


class SqliteInquiryRepository:
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
                CREATE TABLE IF NOT EXISTS inquiries (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE,
                    form_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    feedback_content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inquiry_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    inquiry_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
                );
                """
            )

    def create(self, *, form_id: int, feedback_content: dict) -> dict:
        created_at = self._now()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        timestamp = created_at.isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO inquiries (id, form_id, status, feedback_content, created_at) VALUES (NULL, ?, ?, ?, ?)",
                (form_id, "pending_quote", json.dumps(feedback_content, ensure_ascii=False), timestamp),
            )
            inquiry_id = f"INQ-{created_at:%Y%m%d}-{cursor.lastrowid:03d}"
            connection.execute("UPDATE inquiries SET id = ? WHERE seq = ?", (inquiry_id, cursor.lastrowid))
            connection.execute(
                "INSERT INTO inquiry_events (inquiry_id, type, occurred_at) VALUES (?, ?, ?)",
                (inquiry_id, "inquiry.created", timestamp),
            )
        record = self.get(inquiry_id)
        assert record is not None
        return record

    def get(self, inquiry_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
            if row is None:
                return None
            events = connection.execute(
                "SELECT type, occurred_at FROM inquiry_events WHERE inquiry_id = ? ORDER BY seq", (inquiry_id,)
            ).fetchall()
        return {
            "id": row["id"],
            "form_id": row["form_id"],
            "status": row["status"],
            "feedback_content": json.loads(row["feedback_content"]),
            "created_at": row["created_at"],
            "events": [dict(event) for event in events],
        }

    def list_all(self) -> list[dict]:
        with self._connect() as connection:
            ids = [row["id"] for row in connection.execute("SELECT id FROM inquiries ORDER BY seq DESC")]
        return [record for inquiry_id in ids if (record := self.get(inquiry_id)) is not None]
