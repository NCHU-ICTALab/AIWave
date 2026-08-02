"""Agent 對話的持久化(SQLite)。

spec 15 §4.1:獨立 AI 頁與側欄共享同一段對話與草稿;來回切換、重新整理不遺失。
所以對話不是行程記憶體,而是與 TaskDraft 同等級的持久資料,依 workspace 隔離。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

TAIPEI = timezone(timedelta(hours=8))


class AgentSessionError(ValueError):
    pass


class SqliteAgentSessionStore:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(TAIPEI))
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '新對話',
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active','waiting_confirmation','task_created','archived')),
                    summary TEXT NOT NULL DEFAULT '',
                    active_task_package_id TEXT,
                    pending_grant_id TEXT,
                    archived_at TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_agent_sessions_owner
                    ON agent_sessions(demo_workspace_id,workspace_id,account_id,updated_at);
                """
            )
            # M8 databases already exist in demo workspaces.  Keep the migration
            # additive so a reset or a long-running process never drops a chat.
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(agent_sessions)")
            }
            migrations = {
                "title": "ALTER TABLE agent_sessions ADD COLUMN title TEXT NOT NULL DEFAULT '新對話'",
                "status": "ALTER TABLE agent_sessions ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
                "summary": "ALTER TABLE agent_sessions ADD COLUMN summary TEXT NOT NULL DEFAULT ''",
                "active_task_package_id": "ALTER TABLE agent_sessions ADD COLUMN active_task_package_id TEXT",
                "pending_grant_id": "ALTER TABLE agent_sessions ADD COLUMN pending_grant_id TEXT",
                "archived_at": "ALTER TABLE agent_sessions ADD COLUMN archived_at TEXT",
                "version": "ALTER TABLE agent_sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
            }
            for name, statement in migrations.items():
                if name not in columns:
                    connection.execute(statement)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _timestamp(self) -> str:
        return self._now().astimezone(TAIPEI).isoformat()

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> dict:
        state = json.loads(row["state_json"])
        return {
            "id": row["id"],
            **state,
            "title": row["title"],
            "status": row["status"],
            "summary": row["summary"],
            "activeTaskPackageId": row["active_task_package_id"],
            "activeTaskPackageVersion": state.get("activeTaskPackageVersion"),
            "pendingGrantId": row["pending_grant_id"],
            "archivedAt": row["archived_at"],
            "version": row["version"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def create(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        title: str = "新對話",
    ) -> dict:
        title = title.strip() or "新對話"
        if len(title) > 120:
            raise AgentSessionError("對話名稱不可超過 120 字")
        session_id = f"agent-{uuid4().hex[:12]}"
        state = {
            "messages": [], "subtasks": [], "awaiting": None, "grantId": None,
            "lastTurn": None,
        }
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO agent_sessions
                   (id,demo_workspace_id,workspace_id,account_id,state_json,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (session_id, demo_workspace_id, workspace_id, account_id,
                 json.dumps(state, ensure_ascii=False), timestamp, timestamp),
            )
        return {
            "id": session_id, **state, "title": title, "status": "active", "summary": "",
            "activeTaskPackageId": None, "pendingGrantId": None, "archivedAt": None,
            "activeTaskPackageVersion": None,
            "version": 1, "createdAt": timestamp, "updatedAt": timestamp,
        }

    def get(self, session_id: str, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM agent_sessions
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (session_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
        if row is None:
            raise AgentSessionError("查無此對話,請重新開始")
        return self._row_to_session(row)

    def latest(self, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM agent_sessions
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?
                     AND status != 'archived'
                   ORDER BY updated_at DESC LIMIT 1""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """List sessions in one owner scope; archived chats are opt-in."""

        limit = max(1, min(int(limit), 200))
        query = """SELECT * FROM agent_sessions
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?"""
        params: list[object] = [demo_workspace_id, workspace_id, account_id]
        if not include_archived:
            query += " AND status != 'archived'"
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_session(row) for row in rows]

    def save(
        self,
        session: dict,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        expected_version: int | None = None,
    ) -> dict:
        state = {key: value for key, value in session.items()
                 if key not in {
                     "id", "createdAt", "updatedAt", "title", "status", "summary",
                     "activeTaskPackageId", "pendingGrantId", "archivedAt", "version",
                 }}
        current_version = int(expected_version or session.get("version") or 1)
        timestamp = self._timestamp()
        with self._connect() as connection:
            updated = connection.execute(
                """UPDATE agent_sessions
                   SET state_json=?, title=?, status=?, summary=?, active_task_package_id=?,
                       pending_grant_id=?, archived_at=?, updated_at=?, version=version+1
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?
                     AND version=?""",
                (
                    json.dumps(state, ensure_ascii=False), session.get("title") or "新對話",
                    session.get("status") or "active", session.get("summary") or "",
                    session.get("activeTaskPackageId"), session.get("pendingGrantId"),
                    session.get("archivedAt"), timestamp, session["id"], demo_workspace_id,
                    workspace_id, account_id, current_version,
                ),
            )
            if updated.rowcount == 0:
                exists = connection.execute(
                    """SELECT 1 FROM agent_sessions
                       WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                    (session["id"], demo_workspace_id, workspace_id, account_id),
                ).fetchone()
                if exists:
                    raise AgentSessionError("對話版本衝突,請重新載入後再試")
                raise AgentSessionError("查無此對話,無法儲存")
        session["version"] = current_version + 1
        session["updatedAt"] = timestamp
        return session

    def _change_status(
        self,
        session_id: str,
        *,
        status: str,
        expected_version: int,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict:
        session = self.get(
            session_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, account_id=account_id,
        )
        if session["version"] != expected_version:
            raise AgentSessionError("對話版本衝突,請重新載入後再試")
        session["status"] = status
        session["archivedAt"] = self._timestamp() if status == "archived" else None
        return self.save(session, demo_workspace_id=demo_workspace_id,
                         workspace_id=workspace_id, account_id=account_id,
                         expected_version=expected_version)

    def rename(
        self,
        session_id: str,
        *,
        title: str,
        expected_version: int,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict:
        title = title.strip()
        if not title:
            raise AgentSessionError("對話名稱不可為空")
        if len(title) > 120:
            raise AgentSessionError("對話名稱不可超過 120 字")
        session = self.get(session_id, demo_workspace_id=demo_workspace_id,
                           workspace_id=workspace_id, account_id=account_id)
        if session["version"] != expected_version:
            raise AgentSessionError("對話版本衝突,請重新載入後再試")
        session["title"] = title
        return self.save(session, demo_workspace_id=demo_workspace_id,
                         workspace_id=workspace_id, account_id=account_id,
                         expected_version=expected_version)

    def archive(self, session_id: str, *, expected_version: int, **owner: str) -> dict:
        return self._change_status(session_id, status="archived", expected_version=expected_version, **owner)

    def restore(self, session_id: str, *, expected_version: int, **owner: str) -> dict:
        return self._change_status(session_id, status="active", expected_version=expected_version, **owner)

    def clear(self, account_id: str | None = None) -> None:
        """demo reset 用:清空(或清某帳號的)Agent 對話。"""
        with self._connect() as connection:
            if account_id:
                connection.execute("DELETE FROM agent_sessions WHERE account_id=?", (account_id,))
            else:
                connection.execute("DELETE FROM agent_sessions")

    def to_public(self, session: dict) -> dict[str, Any]:
        """給前端的形狀:訊息、子任務、Session lifecycle metadata。"""
        return {
            "id": session["id"],
            "title": session.get("title") or "新對話",
            "status": session.get("status") or "active",
            "summary": session.get("summary") or "",
            "messages": session["messages"],
            "subtasks": session["subtasks"],
            "awaiting": session["awaiting"],
            "grantId": session.get("grantId"),
            "activeTaskPackageId": session.get("activeTaskPackageId"),
            "activeTaskPackageVersion": session.get("activeTaskPackageVersion"),
            "pendingGrantId": session.get("pendingGrantId") or session.get("grantId"),
            "archivedAt": session.get("archivedAt"),
            "version": session.get("version", 1),
            "createdAt": session.get("createdAt"),
            "updatedAt": session.get("updatedAt"),
            "lastTurn": session.get("lastTurn"),
        }

    def to_list_item(self, session: dict) -> dict[str, Any]:
        public = self.to_public(session)
        public.pop("messages", None)
        public.pop("subtasks", None)
        return public
