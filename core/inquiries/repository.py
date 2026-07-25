"""諮詢單儲存與生命週期。

SQLite 是地端實作；介面刻意維持精簡，日後換 RDS/Postgres 不影響 Agent 與 HTTP 流程。

**狀態對齊官方 `mms_order_record.order_status` 的服務訂單語意**（見 02 資料模型）：
`pending_quote`(12 待報價) → `quoted`(13 已報價待同意) → `confirmed`(14 已同意) →
`completed`(80 已完成)。每次轉換都寫一筆 `inquiry_events`，所以進度是可追溯的。
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

PENDING_QUOTE = "pending_quote"
QUOTED = "quoted"
CONFIRMED = "confirmed"
COMPLETED = "completed"

#: 官方 order_status 對照，供介面與簡報說明用
OFFICIAL_STATUS = {
    PENDING_QUOTE: "12",
    QUOTED: "13",
    CONFIRMED: "14",
    COMPLETED: "80",
}

STATUS_LABEL = {
    PENDING_QUOTE: "待廠商報價",
    QUOTED: "待您確認報價",
    CONFIRMED: "已確認，等待服務",
    COMPLETED: "已完成",
}

#: 允許的狀態轉換；不在表內的一律拒絕，避免跳過確認直接完工
ALLOWED_TRANSITIONS = {
    PENDING_QUOTE: {QUOTED},
    QUOTED: {CONFIRMED},
    CONFIRMED: {COMPLETED},
    COMPLETED: set(),
}


class InquiryTransitionError(ValueError):
    """不合法的狀態轉換。"""


class InquiryRepository(Protocol):
    def create(self, *, form_id: int, feedback_content: dict, service_id: str | None = ..., summary: list | None = ...) -> dict: ...
    def get(self, inquiry_id: str) -> dict | None: ...
    def list_all(self) -> list[dict]: ...
    def list_by_status(self, status: str) -> list[dict]: ...
    def add_quote(self, inquiry_id: str, *, items: list[dict], vendor_name: str) -> dict: ...
    def confirm_quote(self, inquiry_id: str) -> dict: ...
    def complete(self, inquiry_id: str, *, note: str | None = ...) -> dict: ...


class SqliteInquiryRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    # ---- 基礎設施 ------------------------------------------------------

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
                    detail TEXT,
                    FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
                );
                """
            )
            # 生命週期欄位是後來加的；既有資料庫要能就地升級
            existing = {row["name"] for row in connection.execute("PRAGMA table_info(inquiries)")}
            for column, ddl in (
                ("service_id", "TEXT"),
                ("summary", "TEXT"),
                ("quote_items", "TEXT"),
                ("quote_amount", "INTEGER"),
                ("vendor_name", "TEXT"),
                ("quoted_at", "TEXT"),
                ("confirmed_at", "TEXT"),
                ("completed_at", "TEXT"),
            ):
                if column not in existing:
                    connection.execute(f"ALTER TABLE inquiries ADD COLUMN {column} {ddl}")
            if "detail" not in {row["name"] for row in connection.execute("PRAGMA table_info(inquiry_events)")}:
                connection.execute("ALTER TABLE inquiry_events ADD COLUMN detail TEXT")

    def _timestamp(self) -> str:
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.isoformat()

    def _record_event(self, connection: sqlite3.Connection, inquiry_id: str, event_type: str, detail: str | None = None) -> None:
        connection.execute(
            "INSERT INTO inquiry_events (inquiry_id, type, occurred_at, detail) VALUES (?, ?, ?, ?)",
            (inquiry_id, event_type, self._timestamp(), detail),
        )

    def _require_transition(self, connection: sqlite3.Connection, inquiry_id: str, target: str) -> str:
        row = connection.execute("SELECT status FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
        if row is None:
            raise InquiryTransitionError(f"查無諮詢單 {inquiry_id}")
        current = row["status"]
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InquiryTransitionError(
                f"諮詢單 {inquiry_id} 目前是「{STATUS_LABEL.get(current, current)}」，無法直接進到"
                f"「{STATUS_LABEL.get(target, target)}」"
            )
        return current

    # ---- 建立與讀取 ----------------------------------------------------

    def create(
        self,
        *,
        form_id: int,
        feedback_content: dict,
        service_id: str | None = None,
        summary: list | None = None,
    ) -> dict:
        created_at = self._now()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        timestamp = created_at.isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inquiries (id, form_id, service_id, status, feedback_content, summary, created_at)
                VALUES (NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form_id,
                    service_id,
                    PENDING_QUOTE,
                    json.dumps(feedback_content, ensure_ascii=False),
                    json.dumps(summary or [], ensure_ascii=False),
                    timestamp,
                ),
            )
            inquiry_id = f"INQ-{created_at:%Y%m%d}-{cursor.lastrowid:03d}"
            connection.execute("UPDATE inquiries SET id = ? WHERE seq = ?", (inquiry_id, cursor.lastrowid))
            self._record_event(connection, inquiry_id, "inquiry.created")
        record = self.get(inquiry_id)
        assert record is not None
        return record

    def _row_to_record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        events = connection.execute(
            "SELECT type, occurred_at, detail FROM inquiry_events WHERE inquiry_id = ? ORDER BY seq",
            (row["id"],),
        ).fetchall()
        keys = row.keys()
        return {
            "id": row["id"],
            "form_id": row["form_id"],
            "service_id": row["service_id"] if "service_id" in keys else None,
            "status": row["status"],
            "status_label": STATUS_LABEL.get(row["status"], row["status"]),
            "official_status": OFFICIAL_STATUS.get(row["status"]),
            "feedback_content": json.loads(row["feedback_content"]),
            "summary": json.loads(row["summary"]) if row["summary"] else [],
            "quote": (
                {
                    "items": json.loads(row["quote_items"]),
                    "amount": row["quote_amount"],
                    "vendorName": row["vendor_name"],
                    "quotedAt": row["quoted_at"],
                }
                if row["quote_items"] else None
            ),
            "created_at": row["created_at"],
            "confirmed_at": row["confirmed_at"] if "confirmed_at" in keys else None,
            "completed_at": row["completed_at"] if "completed_at" in keys else None,
            "events": [dict(event) for event in events],
        }

    def get(self, inquiry_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
            return None if row is None else self._row_to_record(connection, row)

    def list_all(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM inquiries ORDER BY seq DESC").fetchall()
            return [self._row_to_record(connection, row) for row in rows]

    def list_by_status(self, status: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM inquiries WHERE status = ? ORDER BY seq DESC", (status,)
            ).fetchall()
            return [self._row_to_record(connection, row) for row in rows]

    # ---- 生命週期 ------------------------------------------------------

    def add_quote(self, inquiry_id: str, *, items: list[dict], vendor_name: str) -> dict:
        """廠商開立報價（待報價 → 已報價待確認）。"""
        amount = sum(int(item.get("amount", 0)) for item in items)
        with self._connect() as connection:
            self._require_transition(connection, inquiry_id, QUOTED)
            connection.execute(
                """
                UPDATE inquiries
                   SET status = ?, quote_items = ?, quote_amount = ?, vendor_name = ?, quoted_at = ?
                 WHERE id = ?
                """,
                (QUOTED, json.dumps(items, ensure_ascii=False), amount, vendor_name, self._timestamp(), inquiry_id),
            )
            self._record_event(connection, inquiry_id, "quote.created", f"{vendor_name} NT${amount}")
        record = self.get(inquiry_id)
        assert record is not None
        return record

    def confirm_quote(self, inquiry_id: str) -> dict:
        """住戶同意報價（已報價 → 已確認）。"""
        with self._connect() as connection:
            self._require_transition(connection, inquiry_id, CONFIRMED)
            connection.execute(
                "UPDATE inquiries SET status = ?, confirmed_at = ? WHERE id = ?",
                (CONFIRMED, self._timestamp(), inquiry_id),
            )
            self._record_event(connection, inquiry_id, "quote.confirmed")
        record = self.get(inquiry_id)
        assert record is not None
        return record

    def complete(self, inquiry_id: str, *, note: str | None = None) -> dict:
        """廠商回報完工（已確認 → 已完成）。"""
        with self._connect() as connection:
            self._require_transition(connection, inquiry_id, COMPLETED)
            connection.execute(
                "UPDATE inquiries SET status = ?, completed_at = ? WHERE id = ?",
                (COMPLETED, self._timestamp(), inquiry_id),
            )
            self._record_event(connection, inquiry_id, "service.completed", note)
        record = self.get(inquiry_id)
        assert record is not None
        return record
