"""User-named sharing groups.

A Group is deliberately free of family/friend/community taxonomy. Community is a
separate domain in :mod:`core.communities`.
"""

from __future__ import annotations

import secrets
import sqlite3
import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from core.access import Role, SqliteAccessRepository, WorkspaceKind
from core.data.personas import PERSONAS

ROLE_LABELS = {"admin": "管理者", "member": "成員"}


class GroupError(ValueError):
    """The group operation is invalid or the group does not exist."""


class GroupPermissionError(GroupError):
    """The active account does not have permission for the group."""


class GroupRepository(Protocol):
    def list_for_member(self, account_id: str) -> list[dict]: ...
    def create(self, *, name: str, account_id: str, display_name: str, idempotency_key: str | None = ...) -> dict: ...
    def join(self, *, invite_code: str, account_id: str, display_name: str, idempotency_key: str | None = ...) -> dict: ...
    def rename(self, group_id: str, *, account_id: str, name: str, idempotency_key: str | None = ...) -> dict: ...
    def leave(self, group_id: str, *, account_id: str, idempotency_key: str | None = ...) -> dict: ...


class SqliteGroupRepository:
    def __init__(
        self,
        path: str | Path,
        *,
        now: Callable[[], datetime] | None = None,
        seed: bool = True,
        access: SqliteAccessRepository | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.access = access
        self._initialize()
        if seed:
            self._seed_demo_groups()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sharing_groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    invite_code TEXT NOT NULL UNIQUE,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sharing_group_memberships (
                    group_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','member')),
                    status TEXT NOT NULL CHECK(status IN ('active','left')),
                    joined_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(group_id, account_id),
                    FOREIGN KEY(group_id) REFERENCES sharing_groups(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS sharing_group_operations (
                    idempotency_key TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _timestamp(self) -> str:
        value = self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    @staticmethod
    def _validate_name(name: str) -> str:
        normalized = name.strip()
        if len(normalized) < 2 or len(normalized) > 40:
            raise GroupError("群組名稱需為 2–40 個字")
        return normalized

    @staticmethod
    def _operation_fingerprint(account_id: str, action: str, payload: dict) -> str:
        return hashlib.sha256(json.dumps(
            {"accountId": account_id, "action": action, "payload": payload},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()

    def _replay_operation(
        self, connection: sqlite3.Connection, *, idempotency_key: str | None,
        account_id: str, action: str, payload: dict,
    ) -> tuple[str | None, str, dict | None]:
        key = (idempotency_key or "").strip() or None
        fingerprint = self._operation_fingerprint(account_id, action, payload)
        if key is None:
            return None, fingerprint, None
        row = connection.execute(
            "SELECT account_id,action,fingerprint,result_json FROM sharing_group_operations WHERE idempotency_key=?",
            (key,),
        ).fetchone()
        if row is None:
            return key, fingerprint, None
        if row["account_id"] != account_id or row["action"] != action or row["fingerprint"] != fingerprint:
            raise GroupError("相同 Idempotency-Key 不可用於不同群組操作")
        result = json.loads(row["result_json"])
        result["idempotentReplay"] = True
        return key, fingerprint, result

    def _record_operation(
        self, connection: sqlite3.Connection, *, key: str | None, account_id: str,
        action: str, fingerprint: str, result: dict,
    ) -> None:
        if key is None:
            return
        connection.execute(
            """INSERT INTO sharing_group_operations
               (idempotency_key,account_id,action,fingerprint,result_json,created_at)
               VALUES (?,?,?,?,?,?)""",
            (key, account_id, action, fingerprint, json.dumps(result, ensure_ascii=False), self._timestamp()),
        )

    def _register_workspace(self, *, group_id: str, group_name: str, account_id: str, display_name: str) -> None:
        if self.access is None:
            return
        self.access.register_workspace_membership(
            account_id=account_id,
            display_name=display_name,
            workspace_id=f"workspace-group-{group_id}",
            kind=WorkspaceKind.GROUP,
            owner_ref=group_id,
            workspace_name=group_name,
            role=Role.MEMBER,
            membership_id=f"membership-group-{group_id}-{account_id}",
        )

    def _seed_demo_groups(self) -> None:
        xiaoyuan = PERSONAS[0]
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO sharing_groups
                   (id,name,invite_code,created_by,created_at,updated_at)
                   VALUES ('group-xiaoyuan-shared','小圓的生活群組','GROUP-7284',?,?,?)""",
                (xiaoyuan.id, timestamp, timestamp),
            )
            members = (
                (xiaoyuan.id, xiaoyuan.name, "admin"),
                ("demo-group-member", "阿哲", "member"),
            )
            for account_id, display_name, role in members:
                connection.execute(
                    """INSERT OR IGNORE INTO sharing_group_memberships
                       (group_id,account_id,display_name,role,status,joined_at,updated_at)
                       VALUES ('group-xiaoyuan-shared',?,?,?,'active',?,?)""",
                    (account_id, display_name, role, timestamp, timestamp),
                )
        self._register_workspace(
            group_id="group-xiaoyuan-shared",
            group_name="小圓的生活群組",
            account_id=xiaoyuan.id,
            display_name=xiaoyuan.name,
        )

    def _record(self, connection: sqlite3.Connection, group_id: str, account_id: str) -> dict:
        group = connection.execute("SELECT * FROM sharing_groups WHERE id=?", (group_id,)).fetchone()
        if group is None:
            raise GroupError("查無群組")
        membership = connection.execute(
            """SELECT role FROM sharing_group_memberships
               WHERE group_id=? AND account_id=? AND status='active'""",
            (group_id, account_id),
        ).fetchone()
        if membership is None:
            raise GroupPermissionError("你不是這個群組的成員")
        members = connection.execute(
            """SELECT account_id,display_name,role,joined_at FROM sharing_group_memberships
               WHERE group_id=? AND status='active'
               ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END,joined_at""",
            (group_id,),
        ).fetchall()
        return {
            "id": group["id"],
            "name": group["name"],
            "workspaceId": f"workspace-group-{group['id']}",
            "inviteCode": group["invite_code"],
            "myRole": membership["role"],
            "myRoleLabel": ROLE_LABELS[membership["role"]],
            "memberCount": len(members),
            "members": [
                {
                    "accountId": row["account_id"],
                    "displayName": row["display_name"],
                    "role": row["role"],
                    "roleLabel": ROLE_LABELS[row["role"]],
                    "joinedAt": row["joined_at"],
                }
                for row in members
            ],
            "createdAt": group["created_at"],
            "updatedAt": group["updated_at"],
        }

    def list_for_member(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT g.id FROM sharing_groups g
                   JOIN sharing_group_memberships m ON m.group_id=g.id
                   WHERE m.account_id=? AND m.status='active'
                   ORDER BY g.updated_at DESC,g.name""",
                (account_id,),
            ).fetchall()
            return [self._record(connection, row["id"], account_id) for row in rows]

    def create(
        self, *, name: str, account_id: str, display_name: str,
        idempotency_key: str | None = None,
    ) -> dict:
        normalized_name = self._validate_name(name)
        group_id = f"group-{uuid4().hex[:12]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            key, fingerprint, replay = self._replay_operation(
                connection, idempotency_key=idempotency_key, account_id=account_id,
                action="create", payload={"name": normalized_name, "displayName": display_name.strip() or "會員"},
            )
            if replay is not None:
                return replay
            for _ in range(10):
                invite_code = f"GROUP-{secrets.randbelow(9000) + 1000}"
                if connection.execute(
                    "SELECT 1 FROM sharing_groups WHERE invite_code=?", (invite_code,),
                ).fetchone() is None:
                    break
            else:  # pragma: no cover
                raise GroupError("暫時無法產生邀請碼，請稍後再試")
            connection.execute(
                """INSERT INTO sharing_groups
                   (id,name,invite_code,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?)""",
                (group_id, normalized_name, invite_code, account_id, timestamp, timestamp),
            )
            connection.execute(
                """INSERT INTO sharing_group_memberships
                   (group_id,account_id,display_name,role,status,joined_at,updated_at)
                   VALUES (?,?,?,'admin','active',?,?)""",
                (group_id, account_id, display_name.strip() or "會員", timestamp, timestamp),
            )
            record = self._record(connection, group_id, account_id)
            self._record_operation(
                connection, key=key, account_id=account_id, action="create",
                fingerprint=fingerprint, result=record,
            )
        self._register_workspace(
            group_id=group_id,
            group_name=normalized_name,
            account_id=account_id,
            display_name=display_name.strip() or "會員",
        )
        return record

    def join(
        self, *, invite_code: str, account_id: str, display_name: str,
        idempotency_key: str | None = None,
    ) -> dict:
        normalized = invite_code.strip().upper()
        timestamp = self._timestamp()
        with self._connect() as connection:
            key, fingerprint, replay = self._replay_operation(
                connection, idempotency_key=idempotency_key, account_id=account_id,
                action="join", payload={"inviteCode": normalized, "displayName": display_name.strip() or "會員"},
            )
            if replay is not None:
                return replay
            group = connection.execute(
                "SELECT id,name FROM sharing_groups WHERE invite_code=?", (normalized,),
            ).fetchone()
            if group is None:
                raise GroupError("邀請碼無效，請確認後再試")
            connection.execute(
                """INSERT INTO sharing_group_memberships
                   (group_id,account_id,display_name,role,status,joined_at,updated_at)
                   VALUES (?,?,?,'member','active',?,?)
                   ON CONFLICT(group_id,account_id) DO UPDATE SET
                     display_name=excluded.display_name,status='active',updated_at=excluded.updated_at""",
                (group["id"], account_id, display_name.strip() or "會員", timestamp, timestamp),
            )
            record = self._record(connection, group["id"], account_id)
            self._record_operation(
                connection, key=key, account_id=account_id, action="join",
                fingerprint=fingerprint, result=record,
            )
        self._register_workspace(
            group_id=group["id"],
            group_name=group["name"],
            account_id=account_id,
            display_name=display_name.strip() or "會員",
        )
        return record

    def rename(
        self, group_id: str, *, account_id: str, name: str,
        idempotency_key: str | None = None,
    ) -> dict:
        normalized = self._validate_name(name)
        with self._connect() as connection:
            key, fingerprint, replay = self._replay_operation(
                connection, idempotency_key=idempotency_key, account_id=account_id,
                action="rename", payload={"groupId": group_id, "name": normalized},
            )
            if replay is not None:
                return replay
            membership = connection.execute(
                """SELECT role FROM sharing_group_memberships
                   WHERE group_id=? AND account_id=? AND status='active'""",
                (group_id, account_id),
            ).fetchone()
            if membership is None:
                raise GroupPermissionError("你不是這個群組的成員")
            if membership["role"] != "admin":
                raise GroupPermissionError("只有群組管理者可以修改名稱")
            connection.execute(
                "UPDATE sharing_groups SET name=?,updated_at=? WHERE id=?",
                (normalized, self._timestamp(), group_id),
            )
            result = self._record(connection, group_id, account_id)
            self._record_operation(
                connection, key=key, account_id=account_id, action="rename",
                fingerprint=fingerprint, result=result,
            )
            return result

    def leave(
        self, group_id: str, *, account_id: str, idempotency_key: str | None = None,
    ) -> dict:
        with self._connect() as connection:
            key, fingerprint, replay = self._replay_operation(
                connection, idempotency_key=idempotency_key, account_id=account_id,
                action="leave", payload={"groupId": group_id},
            )
            if replay is not None:
                return replay
            membership = connection.execute(
                """SELECT role FROM sharing_group_memberships
                   WHERE group_id=? AND account_id=? AND status='active'""",
                (group_id, account_id),
            ).fetchone()
            if membership is None:
                raise GroupPermissionError("你不是這個群組的成員")
            count = connection.execute(
                """SELECT COUNT(*) total FROM sharing_group_memberships
                   WHERE group_id=? AND status='active'""",
                (group_id,),
            ).fetchone()["total"]
            if membership["role"] == "admin" and count > 1:
                raise GroupError("請先指派另一位管理者，再離開群組")
            connection.execute(
                """UPDATE sharing_group_memberships SET status='left',updated_at=?
                   WHERE group_id=? AND account_id=?""",
                (self._timestamp(), group_id, account_id),
            )
            if count == 1:
                connection.execute("DELETE FROM sharing_groups WHERE id=?", (group_id,))
                result = {"id": group_id, "deleted": True, "members": []}
            else:
                viewer = connection.execute(
                    """SELECT account_id FROM sharing_group_memberships
                       WHERE group_id=? AND status='active' ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END LIMIT 1""",
                    (group_id,),
                ).fetchone()["account_id"]
                result = self._record(connection, group_id, viewer)
            self._record_operation(
                connection, key=key, account_id=account_id, action="leave",
                fingerprint=fingerprint, result=result,
            )
        if self.access is not None:
            self.access.revoke_workspace_membership(
                account_id=account_id, workspace_id=f"workspace-group-{group_id}",
            )
        return result
