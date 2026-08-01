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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_agent_sessions_owner
                    ON agent_sessions(demo_workspace_id,workspace_id,account_id,updated_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _timestamp(self) -> str:
        return self._now().astimezone(TAIPEI).isoformat()

    def create(self, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict:
        session_id = f"agent-{uuid4().hex[:12]}"
        state = {"messages": [], "subtasks": [], "awaiting": None, "grantId": None}
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO agent_sessions
                   (id,demo_workspace_id,workspace_id,account_id,state_json,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (session_id, demo_workspace_id, workspace_id, account_id,
                 json.dumps(state, ensure_ascii=False), timestamp, timestamp),
            )
        return {"id": session_id, **state, "createdAt": timestamp, "updatedAt": timestamp}

    def get(self, session_id: str, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM agent_sessions
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (session_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
        if row is None:
            raise AgentSessionError("查無此對話,請重新開始")
        state = json.loads(row["state_json"])
        return {"id": row["id"], **state, "createdAt": row["created_at"], "updatedAt": row["updated_at"]}

    def latest(self, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM agent_sessions
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?
                   ORDER BY updated_at DESC LIMIT 1""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchone()
        if row is None:
            return None
        state = json.loads(row["state_json"])
        return {"id": row["id"], **state, "createdAt": row["created_at"], "updatedAt": row["updated_at"]}

    def save(self, session: dict, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> None:
        state = {key: value for key, value in session.items()
                 if key not in {"id", "createdAt", "updatedAt"}}
        with self._connect() as connection:
            updated = connection.execute(
                """UPDATE agent_sessions SET state_json=?, updated_at=?
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (json.dumps(state, ensure_ascii=False), self._timestamp(),
                 session["id"], demo_workspace_id, workspace_id, account_id),
            )
            if updated.rowcount == 0:
                raise AgentSessionError("查無此對話,無法儲存")

    def clear(self, account_id: str | None = None) -> None:
        """demo reset 用:清空(或清某帳號的)Agent 對話。"""
        with self._connect() as connection:
            if account_id:
                connection.execute("DELETE FROM agent_sessions WHERE account_id=?", (account_id,))
            else:
                connection.execute("DELETE FROM agent_sessions")

    def to_public(self, session: dict) -> dict[str, Any]:
        """給前端的形狀:訊息、子任務、目前等待的互動。"""
        return {
            "id": session["id"],
            "messages": session["messages"],
            "subtasks": session["subtasks"],
            "awaiting": session["awaiting"],
            "grantId": session.get("grantId"),
            "updatedAt": session.get("updatedAt"),
        }
