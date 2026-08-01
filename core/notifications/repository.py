from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, time, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo


class NotificationError(ValueError):
    pass


class SqliteNotificationRepository:
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
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL CHECK(scope_type IN ('personal','group','community')),
                    scope_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    deep_link TEXT NOT NULL,
                    subject_type TEXT,
                    subject_id TEXT,
                    read_at TEXT,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,account_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_notifications_owner
                    ON notifications(demo_workspace_id,workspace_id,account_id,created_at);
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    account_id TEXT PRIMARY KEY,
                    quiet_start TEXT,
                    quiet_end TEXT,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Taipei',
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "scope": {"type": row["scope_type"], "id": row["scope_id"]},
            "category": row["category"], "title": row["title"], "body": row["body"],
            "deepLink": row["deep_link"], "subjectType": row["subject_type"],
            "subjectId": row["subject_id"], "readAt": row["read_at"],
            "createdAt": row["created_at"],
        }

    def publish(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        scope_type: str,
        scope_id: str,
        category: str,
        title: str,
        body: str,
        deep_link: str,
        idempotency_key: str,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> dict:
        if scope_type not in {"personal", "group", "community"}:
            raise NotificationError("通知 scope 不合法")
        if not deep_link.startswith("/"):
            raise NotificationError("通知 deep link 必須是站內絕對路徑")
        notification_id = f"notification-{uuid4().hex[:16]}"
        with self._connect() as connection:
            existing = connection.execute(
                """SELECT * FROM notifications
                   WHERE demo_workspace_id=? AND account_id=? AND idempotency_key=?""",
                (demo_workspace_id, account_id, idempotency_key),
            ).fetchone()
            if existing:
                result = self._record(existing)
                result["idempotentReplay"] = True
                return result
            connection.execute(
                """INSERT INTO notifications
                   (id,demo_workspace_id,workspace_id,account_id,scope_type,scope_id,category,title,body,
                    deep_link,subject_type,subject_id,idempotency_key,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    notification_id, demo_workspace_id, workspace_id, account_id,
                    scope_type, scope_id, category, title, body, deep_link,
                    subject_type, subject_id, idempotency_key, self._timestamp(),
                ),
            )
            row = connection.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()
            result = self._record(row)
            result["idempotentReplay"] = False
            return result

    def list_owned(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        unread_only: bool = False,
    ) -> dict:
        unread_clause = " AND read_at IS NULL" if unread_only else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM notifications
                    WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?{unread_clause}
                    ORDER BY created_at DESC,id DESC""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
            return {
                "unreadCount": sum(row["read_at"] is None for row in rows),
                "items": [self._record(row) for row in rows],
                "quietHoursActive": self.quiet_hours_active(account_id),
            }

    def mark_read(
        self,
        notification_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM notifications
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (notification_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise NotificationError("查無通知")
            if row["read_at"] is None:
                connection.execute(
                    "UPDATE notifications SET read_at=? WHERE id=?", (self._timestamp(), notification_id),
                )
            return self._record(connection.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone())

    def set_quiet_hours(self, account_id: str, *, start: str | None, end: str | None, timezone_name: str = "Asia/Taipei") -> dict:
        if (start is None) != (end is None):
            raise NotificationError("安靜時段的開始與結束必須一起設定")
        try:
            if start:
                time.fromisoformat(start)
                time.fromisoformat(end or "")
            ZoneInfo(timezone_name)
        except (ValueError, KeyError) as exc:
            raise NotificationError("安靜時段或時區格式不合法") from exc
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO notification_preferences(account_id,quiet_start,quiet_end,timezone,updated_at)
                   VALUES (?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET
                     quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end,
                     timezone=excluded.timezone,updated_at=excluded.updated_at""",
                (account_id, start, end, timezone_name, self._timestamp()),
            )
        return {"quietStart": start, "quietEnd": end, "timezone": timezone_name}

    def quiet_hours_active(self, account_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT quiet_start,quiet_end,timezone FROM notification_preferences WHERE account_id=?",
                (account_id,),
            ).fetchone()
        if row is None or row["quiet_start"] is None:
            return False
        local = self._moment().astimezone(ZoneInfo(row["timezone"])).time().replace(tzinfo=None)
        start, end = time.fromisoformat(row["quiet_start"]), time.fromisoformat(row["quiet_end"])
        return start <= local < end if start < end else local >= start or local < end

