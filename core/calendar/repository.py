from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class CalendarError(ValueError):
    pass


class CalendarConflict(CalendarError):
    pass


SOURCE_TYPES = {"manual", "booking", "life_task", "reminder", "group", "community"}


class SqliteCalendarRepository:
    """Calendar projection; provider bookings remain controlled by reschedule workflow."""

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
        value = self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL CHECK(scope_type IN ('personal','group','community')),
                    scope_id TEXT NOT NULL,
                    source_type TEXT NOT NULL CHECK(source_type IN ('manual','booking','life_task','reminder','group','community')),
                    source_id TEXT NOT NULL,
                    series_parent_id TEXT,
                    title TEXT NOT NULL,
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    all_day INTEGER NOT NULL DEFAULT 0,
                    note TEXT,
                    recurrence_json TEXT,
                    status TEXT NOT NULL CHECK(status IN ('active','cancelled')),
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,source_type,source_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_calendar_owner
                    ON calendar_events(demo_workspace_id,workspace_id,account_id,starts_at);
                CREATE TABLE IF NOT EXISTS calendar_event_exceptions (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    occurrence_start TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('override','cancel')),
                    payload_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(event_id,occurrence_start,idempotency_key),
                    FOREIGN KEY(event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _validate_times(starts_at: str, ends_at: str) -> None:
        try:
            starts = datetime.fromisoformat(starts_at)
            ends = datetime.fromisoformat(ends_at)
        except ValueError as exc:
            raise CalendarError("行事曆時間必須是 ISO 8601") from exc
        if ends <= starts:
            raise CalendarError("行事曆結束時間必須晚於開始時間")

    @staticmethod
    def _validate_recurrence(recurrence: dict | None) -> dict | None:
        if recurrence is None:
            return None
        if recurrence.get("frequency") not in {"daily", "weekly", "monthly"}:
            raise CalendarError("週期只支援 daily、weekly、monthly")
        interval = int(recurrence.get("interval", 1))
        if interval < 1 or interval > 365:
            raise CalendarError("週期間隔不合法")
        return {**recurrence, "interval": interval}

    def _record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        exceptions = connection.execute(
            """SELECT occurrence_start,action,payload_json FROM calendar_event_exceptions
               WHERE event_id=? ORDER BY occurrence_start""",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"], "workspaceId": row["workspace_id"],
            "scope": {"type": row["scope_type"], "id": row["scope_id"]},
            "source": {"type": row["source_type"], "id": row["source_id"]},
            "seriesParentId": row["series_parent_id"], "title": row["title"],
            "startsAt": row["starts_at"], "endsAt": row["ends_at"],
            "allDay": bool(row["all_day"]), "note": row["note"],
            "recurrence": json.loads(row["recurrence_json"]) if row["recurrence_json"] else None,
            "status": row["status"],
            "exceptions": [
                {
                    "occurrenceStart": item["occurrence_start"], "action": item["action"],
                    "payload": json.loads(item["payload_json"]),
                }
                for item in exceptions
            ],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    def create_manual(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        scope_type: str,
        scope_id: str,
        title: str,
        starts_at: str,
        ends_at: str,
        all_day: bool,
        note: str | None,
        recurrence: dict | None,
        idempotency_key: str,
    ) -> dict:
        self._validate_times(starts_at, ends_at)
        recurrence = self._validate_recurrence(recurrence)
        if scope_type not in {"personal", "group", "community"}:
            raise CalendarError("行事曆 scope 不合法")
        event_id = f"calendar-{uuid4().hex[:16]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            existing = connection.execute(
                """SELECT * FROM calendar_events
                   WHERE demo_workspace_id=? AND source_type='manual' AND source_id=? AND idempotency_key=?""",
                (demo_workspace_id, account_id, idempotency_key),
            ).fetchone()
            if existing:
                result = self._record(connection, existing)
                result["idempotentReplay"] = True
                return result
            connection.execute(
                """INSERT INTO calendar_events
                   (id,demo_workspace_id,workspace_id,account_id,scope_type,scope_id,source_type,source_id,
                    title,starts_at,ends_at,all_day,note,recurrence_json,status,idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,'manual',?,?,?,?,?,?,?,'active',?,?,?)""",
                (
                    event_id, demo_workspace_id, workspace_id, account_id, scope_type, scope_id,
                    account_id, title, starts_at, ends_at, int(all_day), note,
                    json.dumps(recurrence, ensure_ascii=False) if recurrence else None,
                    idempotency_key, timestamp, timestamp,
                ),
            )
            row = connection.execute("SELECT * FROM calendar_events WHERE id=?", (event_id,)).fetchone()
            result = self._record(connection, row)
            result["idempotentReplay"] = False
            return result

    def upsert_projection(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        scope_type: str,
        scope_id: str,
        source_type: str,
        source_id: str,
        title: str,
        starts_at: str,
        ends_at: str,
        note: str | None,
    ) -> dict:
        if source_type not in SOURCE_TYPES - {"manual"}:
            raise CalendarError("未知的行事曆 projection 來源")
        self._validate_times(starts_at, ends_at)
        idempotency_key = f"projection:{source_type}:{source_id}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            existing = connection.execute(
                """SELECT * FROM calendar_events WHERE demo_workspace_id=? AND source_type=? AND source_id=?""",
                (demo_workspace_id, source_type, source_id),
            ).fetchone()
            if existing:
                connection.execute(
                    """UPDATE calendar_events SET workspace_id=?,account_id=?,scope_type=?,scope_id=?,
                       title=?,starts_at=?,ends_at=?,note=?,status='active',updated_at=? WHERE id=?""",
                    (
                        workspace_id, account_id, scope_type, scope_id, title,
                        starts_at, ends_at, note, timestamp, existing["id"],
                    ),
                )
                row = connection.execute("SELECT * FROM calendar_events WHERE id=?", (existing["id"],)).fetchone()
                return self._record(connection, row)
            event_id = f"calendar-{uuid4().hex[:16]}"
            connection.execute(
                """INSERT INTO calendar_events
                   (id,demo_workspace_id,workspace_id,account_id,scope_type,scope_id,source_type,source_id,
                    title,starts_at,ends_at,all_day,note,recurrence_json,status,idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,NULL,'active',?,?,?)""",
                (
                    event_id, demo_workspace_id, workspace_id, account_id, scope_type, scope_id,
                    source_type, source_id, title, starts_at, ends_at, note,
                    idempotency_key, timestamp, timestamp,
                ),
            )
            return self._record(connection, connection.execute("SELECT * FROM calendar_events WHERE id=?", (event_id,)).fetchone())

    def cancel_projection(
        self,
        *,
        demo_workspace_id: str,
        source_type: str,
        source_id: str,
        note: str | None = None,
    ) -> bool:
        """交易取消時同步取消 projection(Booking 是事實來源,行事曆只跟隨)。"""
        timestamp = self._timestamp()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE calendar_events SET status='cancelled',note=COALESCE(?,note),updated_at=?
                   WHERE demo_workspace_id=? AND source_type=? AND source_id=?""",
                (note, timestamp, demo_workspace_id, source_type, source_id),
            )
            return cursor.rowcount > 0

    def list_owned(
        self,
        *,
        demo_workspace_id: str,
        account_id: str,
        allowed_workspaces: tuple[str, ...],
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        if not allowed_workspaces:
            return []
        placeholders = ",".join("?" for _ in allowed_workspaces)
        clauses, values = [
            "demo_workspace_id=?", f"workspace_id IN ({placeholders})", "status='active'",
        ], [demo_workspace_id, *allowed_workspaces]
        if start:
            clauses.append("ends_at>=?")
            values.append(start)
        if end:
            clauses.append("starts_at<=?")
            values.append(end)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM calendar_events WHERE {' AND '.join(clauses)} ORDER BY starts_at,id",
                values,
            ).fetchall()
            return [self._record(connection, row) for row in rows]

    def change_manual_series(
        self,
        event_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        mode: str,
        occurrence_start: str | None,
        changes: dict,
        idempotency_key: str,
    ) -> dict:
        if mode not in {"this", "future", "all"}:
            raise CalendarError("週期修改範圍只接受 this、future、all")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM calendar_events
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (event_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise CalendarError("查無行事曆事件")
            if row["source_type"] != "manual":
                raise CalendarConflict("預約與系統事件不可直接拖曳或修改，請使用原服務的變更流程")
            if mode in {"this", "future"} and (not row["recurrence_json"] or not occurrence_start):
                raise CalendarError("單次或未來週期修改需要 occurrence_start")
            if mode == "this":
                connection.execute(
                    """INSERT OR IGNORE INTO calendar_event_exceptions
                       (id,event_id,occurrence_start,action,payload_json,idempotency_key,created_at)
                       VALUES (?,?,?,'override',?,?,?)""",
                    (
                        f"calendar-exception-{uuid4().hex[:12]}", event_id, occurrence_start,
                        json.dumps(changes, ensure_ascii=False), idempotency_key, self._timestamp(),
                    ),
                )
                return self._record(connection, row)
            allowed = {"title", "starts_at", "ends_at", "note", "recurrence"}
            if not set(changes) <= allowed:
                raise CalendarError("包含不可修改的行事曆欄位")
            if mode == "all":
                title = changes.get("title", row["title"])
                starts_at = changes.get("starts_at", row["starts_at"])
                ends_at = changes.get("ends_at", row["ends_at"])
                self._validate_times(starts_at, ends_at)
                recurrence = changes.get("recurrence")
                recurrence_json = row["recurrence_json"] if "recurrence" not in changes else (
                    json.dumps(self._validate_recurrence(recurrence), ensure_ascii=False) if recurrence else None
                )
                connection.execute(
                    """UPDATE calendar_events SET title=?,starts_at=?,ends_at=?,note=?,recurrence_json=?,updated_at=?
                       WHERE id=?""",
                    (title, starts_at, ends_at, changes.get("note", row["note"]), recurrence_json, self._timestamp(), event_id),
                )
                return self._record(connection, connection.execute("SELECT * FROM calendar_events WHERE id=?", (event_id,)).fetchone())

            # Future occurrences become a new series; the original series records a deterministic cutoff.
            recurrence = json.loads(row["recurrence_json"])
            recurrence["untilBefore"] = occurrence_start
            connection.execute(
                "UPDATE calendar_events SET recurrence_json=?,updated_at=? WHERE id=?",
                (json.dumps(recurrence, ensure_ascii=False), self._timestamp(), event_id),
            )
            new_starts = changes.get("starts_at", occurrence_start)
            original_duration = datetime.fromisoformat(row["ends_at"]) - datetime.fromisoformat(row["starts_at"])
            new_ends = changes.get("ends_at", (datetime.fromisoformat(new_starts) + original_duration).isoformat())
            self._validate_times(new_starts, new_ends)
            new_event_id = f"calendar-{uuid4().hex[:16]}"
            timestamp = self._timestamp()
            new_recurrence = self._validate_recurrence(changes.get("recurrence", json.loads(row["recurrence_json"])))
            if new_recurrence:
                new_recurrence.pop("untilBefore", None)
            connection.execute(
                """INSERT INTO calendar_events
                   (id,demo_workspace_id,workspace_id,account_id,scope_type,scope_id,source_type,source_id,
                    series_parent_id,title,starts_at,ends_at,all_day,note,recurrence_json,status,
                    idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?,?)""",
                (
                    new_event_id, row["demo_workspace_id"], row["workspace_id"], row["account_id"],
                    row["scope_type"], row["scope_id"], "manual", row["source_id"], event_id,
                    changes.get("title", row["title"]), new_starts, new_ends, row["all_day"],
                    changes.get("note", row["note"]), json.dumps(new_recurrence, ensure_ascii=False),
                    idempotency_key, timestamp, timestamp,
                ),
            )
            return self._record(connection, connection.execute("SELECT * FROM calendar_events WHERE id=?", (new_event_id,)).fetchone())

