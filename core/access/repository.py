from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from core.data.personas import PERSONAS

from .models import AccessError, AccessForbidden, Principal, Role, WorkspaceKind


SEED_VERSION = "platform-demo-v2"
FIXED_DEMO_KEYS = {
    "aiwave": "membership-member-xiaoyuan",
    "aiwave-chen": f"membership-member-{PERSONAS[1].id}",
    "aiwave-vivian": f"membership-member-{PERSONAS[2].id}",
    "aiwave-new": "membership-member-new",
    "aiwave-partner": "membership-partner-prince-electric",
    "aiwave-partner-duskin": "membership-partner-duskin",
    "aiwave-partner-21plus": "membership-partner-21plus",
    "aiwave-partner-smile": "membership-partner-smile",
    "aiwave-partner-blackcat": "membership-partner-blackcat",
    "aiwave-partner-cosmed": "membership-partner-cosmed",
    "aiwave-partner-711shop": "membership-partner-711shop",
    "aiwave-partner-resort": "membership-partner-resort",
    "aiwave-partner-foodomo": "membership-partner-foodomo",
    "aiwave-partner-711c2c": "membership-partner-711c2c",
    "aiwave-partner-iopenmall": "membership-partner-iopenmall",
    "aiwave-partner-ibonticket": "membership-partner-ibonticket",
    "aiwave-manager": "membership-manager-sunshine",
    "aiwave-admin": "membership-platform-operator",
}


def _key_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SqliteAccessRepository:
    """Authority for authenticated principals and explicit workspace selection.

    Raw bearer keys are never stored. A credential is bound to exactly one active
    RoleMembership; switching workspace issues another opaque, expiring session.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        now: Callable[[], datetime] | None = None,
        seed: bool = True,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()
        if seed:
            self.seed_demo()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    persona_id TEXT,
                    status TEXT NOT NULL CHECK(status IN ('active','disabled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('personal','group','community','provider','platform')),
                    owner_ref TEXT NOT NULL,
                    name TEXT NOT NULL,
                    demo_workspace_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','archived')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(kind, owner_ref, demo_workspace_id)
                );
                CREATE TABLE IF NOT EXISTS role_memberships (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('member','partner_staff','community_manager','platform_operator')),
                    status TEXT NOT NULL CHECK(status IN ('active','pending','revoked')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(account_id, workspace_id, role),
                    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS api_credentials (
                    id TEXT PRIMARY KEY,
                    membership_id TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    expires_at TEXT,
                    revoked_at TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    FOREIGN KEY(membership_id) REFERENCES role_memberships(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS demo_workspaces (
                    id TEXT PRIMARY KEY,
                    seed_version TEXT NOT NULL,
                    owner_account_id TEXT NOT NULL,
                    reset_version INTEGER NOT NULL DEFAULT 0,
                    last_reset_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(owner_account_id) REFERENCES accounts(id) ON DELETE CASCADE
                );
                """
            )

    def _upsert_account(self, connection: sqlite3.Connection, account_id: str, name: str, persona_id: str | None = None) -> None:
        timestamp = self._timestamp()
        connection.execute(
            """INSERT INTO accounts(id,display_name,persona_id,status,created_at,updated_at)
               VALUES (?,?,?,'active',?,?)
               ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,
                 persona_id=excluded.persona_id,status='active',updated_at=excluded.updated_at""",
            (account_id, name, persona_id, timestamp, timestamp),
        )

    def _upsert_workspace(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        kind: WorkspaceKind,
        owner_ref: str,
        name: str,
        demo_workspace_id: str,
    ) -> None:
        timestamp = self._timestamp()
        connection.execute(
            """INSERT INTO workspaces(id,kind,owner_ref,name,demo_workspace_id,status,created_at,updated_at)
               VALUES (?,?,?,?,?,'active',?,?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                 demo_workspace_id=excluded.demo_workspace_id,status='active',updated_at=excluded.updated_at""",
            (workspace_id, kind.value, owner_ref, name, demo_workspace_id, timestamp, timestamp),
        )

    def _upsert_membership(
        self,
        connection: sqlite3.Connection,
        *,
        membership_id: str,
        account_id: str,
        workspace_id: str,
        role: Role,
    ) -> None:
        timestamp = self._timestamp()
        connection.execute(
            """INSERT INTO role_memberships(id,account_id,workspace_id,role,status,created_at,updated_at)
               VALUES (?,?,?,?,'active',?,?)
               ON CONFLICT(id) DO UPDATE SET status='active',updated_at=excluded.updated_at""",
            (membership_id, account_id, workspace_id, role.value, timestamp, timestamp),
        )

    def _upsert_credential(
        self,
        connection: sqlite3.Connection,
        *,
        credential_id: str,
        membership_id: str,
        raw_key: str,
        label: str,
        scopes: tuple[str, ...],
    ) -> None:
        timestamp = self._timestamp()
        connection.execute(
            """INSERT INTO api_credentials
               (id,membership_id,key_hash,label,scopes_json,expires_at,revoked_at,created_at)
               VALUES (?,?,?,?,?,NULL,NULL,?)
               ON CONFLICT(id) DO UPDATE SET membership_id=excluded.membership_id,
                 key_hash=excluded.key_hash,label=excluded.label,scopes_json=excluded.scopes_json,
                 expires_at=NULL,revoked_at=NULL""",
            (credential_id, membership_id, _key_hash(raw_key), label, json.dumps(scopes), timestamp),
        )

    def seed_demo(self) -> None:
        """Create fixed, isolated personas and role workspaces idempotently."""
        xiaoyuan = PERSONAS[0]
        with self._connect() as connection:
            for persona in PERSONAS:
                self._upsert_account(connection, persona.id, persona.name, persona.id)
                demo_id = "demo-default"
                self._upsert_workspace(
                    connection,
                    workspace_id=f"workspace-personal-{persona.id}",
                    kind=WorkspaceKind.PERSONAL,
                    owner_ref=persona.id,
                    name=f"{persona.name}的個人空間",
                    demo_workspace_id=demo_id,
                )
                self._upsert_membership(
                    connection,
                    membership_id=(
                        "membership-member-xiaoyuan"
                        if persona.id == xiaoyuan.id
                        else f"membership-member-{persona.id}"
                    ),
                    account_id=persona.id,
                    workspace_id=f"workspace-personal-{persona.id}",
                    role=Role.MEMBER,
                )
            connection.execute(
                """INSERT OR IGNORE INTO demo_workspaces
                   (id,seed_version,owner_account_id,created_at) VALUES (?,?,?,?)""",
                ("demo-default", SEED_VERSION, xiaoyuan.id, self._timestamp()),
            )

            self._upsert_account(connection, "demo-new-member", "新使用者", "demo-new-member")
            self._upsert_workspace(
                connection,
                workspace_id="workspace-personal-demo-new-member",
                kind=WorkspaceKind.PERSONAL,
                owner_ref="demo-new-member",
                name="新使用者的個人空間",
                demo_workspace_id="demo-default",
            )
            self._upsert_membership(
                connection,
                membership_id="membership-member-new",
                account_id="demo-new-member",
                workspace_id="workspace-personal-demo-new-member",
                role=Role.MEMBER,
            )

            # Stable aliases make the four public demo keys independent of long persona IDs.
            self._upsert_account(connection, "demo-partner-prince-electric", "王子水電人員")
            self._upsert_workspace(
                connection,
                workspace_id="workspace-provider-prince-electric",
                kind=WorkspaceKind.PROVIDER,
                owner_ref="vendor-prince-electric",
                name="王子水電工作空間",
                demo_workspace_id="demo-default",
            )
            self._upsert_membership(
                connection,
                membership_id="membership-partner-prince-electric",
                account_id="demo-partner-prince-electric",
                workspace_id="workspace-provider-prince-electric",
                role=Role.PARTNER_STAFF,
            )
            self._upsert_account(connection, "demo-community-manager", "陽光社區管理者")
            # M4:六大場景的合作方工作空間(品牌沿用核准 allowlist;fun 為可替換示範)
            for suffix, vendor_id, staff_name in (
                ("duskin", "vendor-duskin", "DUSKIN 樂清人員"),
                ("21plus", "vendor-21plus", "21PLUS 餐廳人員"),
                ("smile", "vendor-smile", "速邁樂加油站人員"),
                ("blackcat", "vendor-blackcat", "黑貓宅急便人員"),
                ("cosmed", "vendor-cosmed", "康是美人員"),
                ("711shop", "vendor-711-shop", "7-ELEVEN 線上購物中心人員"),
                ("resort", "vendor-uni-resort", "統一渡假村人員"),
                ("foodomo", "vendor-foodomo", "foodomo 人員"),
                ("711c2c", "vendor-711-c2c", "7-ELEVEN 交貨便人員"),
                ("iopenmall", "vendor-iopenmall", "iOPEN Mall 人員"),
                ("ibonticket", "vendor-ibon-ticket", "ibon 售票人員"),
            ):
                self._upsert_account(connection, f"demo-partner-{suffix}", staff_name)
                self._upsert_workspace(
                    connection,
                    workspace_id=f"workspace-provider-{suffix}",
                    kind=WorkspaceKind.PROVIDER,
                    owner_ref=vendor_id,
                    name=f"{staff_name.removesuffix('人員')}工作空間",
                    demo_workspace_id="demo-default",
                )
                self._upsert_membership(
                    connection,
                    membership_id=f"membership-partner-{suffix}",
                    account_id=f"demo-partner-{suffix}",
                    workspace_id=f"workspace-provider-{suffix}",
                    role=Role.PARTNER_STAFF,
                )
            self._upsert_workspace(
                connection,
                workspace_id="workspace-community-sunshine",
                kind=WorkspaceKind.COMMUNITY,
                owner_ref="community-sunshine",
                name="陽光社區",
                demo_workspace_id="demo-default",
            )
            self._upsert_membership(
                connection,
                membership_id="membership-manager-sunshine",
                account_id="demo-community-manager",
                workspace_id="workspace-community-sunshine",
                role=Role.COMMUNITY_MANAGER,
            )
            self._upsert_account(connection, "demo-platform-operator", "AIWave 平台營運者")
            self._upsert_workspace(
                connection,
                workspace_id="workspace-platform-demo",
                kind=WorkspaceKind.PLATFORM,
                owner_ref="platform-demo",
                name="AIWave Demo 管理空間",
                demo_workspace_id="demo-default",
            )
            self._upsert_membership(
                connection,
                membership_id="membership-platform-operator",
                account_id="demo-platform-operator",
                workspace_id="workspace-platform-demo",
                role=Role.PLATFORM_OPERATOR,
            )
            fixed = {
                "aiwave": ("membership-member-xiaoyuan", ("personal:read", "personal:write", "platform:read")),
                "aiwave-chen": (f"membership-member-{PERSONAS[1].id}", ("personal:read", "personal:write", "platform:read")),
                "aiwave-vivian": (f"membership-member-{PERSONAS[2].id}", ("personal:read", "personal:write", "platform:read")),
                "aiwave-new": ("membership-member-new", ("personal:read", "personal:write", "platform:read")),
                "aiwave-partner": ("membership-partner-prince-electric", ("partner:read", "partner:write")),
                "aiwave-partner-duskin": ("membership-partner-duskin", ("partner:read", "partner:write")),
                "aiwave-partner-21plus": ("membership-partner-21plus", ("partner:read", "partner:write")),
                "aiwave-partner-smile": ("membership-partner-smile", ("partner:read", "partner:write")),
                "aiwave-partner-blackcat": ("membership-partner-blackcat", ("partner:read", "partner:write")),
                "aiwave-partner-cosmed": ("membership-partner-cosmed", ("partner:read", "partner:write")),
                "aiwave-partner-711shop": ("membership-partner-711shop", ("partner:read", "partner:write")),
                "aiwave-partner-resort": ("membership-partner-resort", ("partner:read", "partner:write")),
                "aiwave-partner-foodomo": ("membership-partner-foodomo", ("partner:read", "partner:write")),
                "aiwave-partner-711c2c": ("membership-partner-711c2c", ("partner:read", "partner:write")),
                "aiwave-partner-iopenmall": ("membership-partner-iopenmall", ("partner:read", "partner:write")),
                "aiwave-partner-ibonticket": ("membership-partner-ibonticket", ("partner:read", "partner:write")),
                "aiwave-manager": ("membership-manager-sunshine", ("community:read", "community:write")),
                "aiwave-admin": ("membership-platform-operator", ("platform:*", "demo:reset", "demo:switch")),
            }
            for raw_key, (membership_id, scopes) in fixed.items():
                self._upsert_credential(
                    connection,
                    credential_id=f"credential-{raw_key}",
                    membership_id=membership_id,
                    raw_key=raw_key,
                    label=f"固定 Demo credential：{raw_key}",
                    scopes=scopes,
                )

    def _principal_from_row(self, row: sqlite3.Row) -> Principal:
        return Principal(
            account_id=row["account_id"],
            display_name=row["display_name"],
            membership_id=row["membership_id"],
            role=Role(row["role"]),
            workspace_id=row["workspace_id"],
            workspace_kind=WorkspaceKind(row["workspace_kind"]),
            owner_ref=row["owner_ref"],
            demo_workspace_id=row["demo_workspace_id"],
            scopes=frozenset(json.loads(row["scopes_json"])),
            credential_id=row["credential_id"],
        )

    def resolve_bearer(self, raw_key: str) -> Principal:
        if not raw_key.strip():
            raise AccessError("缺少存取憑證")
        now = self._timestamp()
        with self._connect() as connection:
            row = connection.execute(
                """SELECT c.id credential_id,c.membership_id,c.scopes_json,c.expires_at,
                          a.id account_id,a.display_name,a.status account_status,
                          m.role,m.status membership_status,w.id workspace_id,w.kind workspace_kind,
                          w.owner_ref,w.demo_workspace_id,w.status workspace_status
                   FROM api_credentials c
                   JOIN role_memberships m ON m.id=c.membership_id
                   JOIN accounts a ON a.id=m.account_id
                   JOIN workspaces w ON w.id=m.workspace_id
                   WHERE c.key_hash=? AND c.revoked_at IS NULL""",
                (_key_hash(raw_key),),
            ).fetchone()
            if row is None:
                raise AccessError("存取憑證無效")
            if row["expires_at"] and row["expires_at"] <= now:
                raise AccessError("存取憑證已過期")
            if row["account_status"] != "active" or row["membership_status"] != "active" or row["workspace_status"] != "active":
                raise AccessForbidden("帳號、角色或工作空間已停用")
            connection.execute("UPDATE api_credentials SET last_used_at=? WHERE id=?", (now, row["credential_id"]))
            return self._principal_from_row(row)

    def list_memberships(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT m.id membership_id,m.role,m.status,w.id workspace_id,w.kind,w.owner_ref,w.name,
                          w.demo_workspace_id
                   FROM role_memberships m JOIN workspaces w ON w.id=m.workspace_id
                   WHERE m.account_id=? AND m.status='active' AND w.status='active'
                   ORDER BY w.kind,w.name""",
                (account_id,),
            ).fetchall()
            return [
                {
                    "membershipId": row["membership_id"],
                    "role": row["role"],
                    "workspace": {
                        "id": row["workspace_id"], "kind": row["kind"],
                        "ownerRef": row["owner_ref"], "name": row["name"],
                    },
                    "demoWorkspaceId": row["demo_workspace_id"],
                }
                for row in rows
            ]

    def describe_membership(self, membership_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT m.id membership_id,m.account_id,m.role,a.display_name,
                          w.id workspace_id,w.kind,w.owner_ref,w.name,w.demo_workspace_id
                   FROM role_memberships m
                   JOIN accounts a ON a.id=m.account_id
                   JOIN workspaces w ON w.id=m.workspace_id
                   WHERE m.id=? AND m.status='active' AND a.status='active' AND w.status='active'""",
                (membership_id,),
            ).fetchone()
            if row is None:
                raise AccessError("查無可用的角色工作空間")
            return {
                "membershipId": row["membership_id"],
                "accountId": row["account_id"],
                "displayName": row["display_name"],
                "role": row["role"],
                "demoWorkspaceId": row["demo_workspace_id"],
                "workspace": {
                    "id": row["workspace_id"], "kind": row["kind"],
                    "ownerRef": row["owner_ref"], "name": row["name"],
                },
            }

    def issue_session(
        self,
        *,
        actor: Principal,
        membership_id: str,
        ttl: timedelta = timedelta(hours=8),
    ) -> tuple[str, Principal]:
        """Switch only to one of the actor's memberships.

        Platform operators with ``demo:switch`` may switch to fixed demo memberships,
        but cannot create an arbitrary account or workspace through this method.
        """
        with self._connect() as connection:
            target = connection.execute(
                """SELECT account_id FROM role_memberships WHERE id=? AND status='active'""",
                (membership_id,),
            ).fetchone()
            if target is None:
                raise AccessError("查無可切換的角色工作空間")
            same_account = target["account_id"] == actor.account_id
            fixed_demo_target = membership_id in set(FIXED_DEMO_KEYS.values())
            if not same_account and not ("demo:switch" in actor.scopes and fixed_demo_target):
                raise AccessForbidden("不可切換到其他帳號的工作空間")
            raw_key = secrets.token_urlsafe(32)
            credential_id = f"session-{uuid4().hex}"
            expires = self._now()
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            scopes_by_role = {
                Role.MEMBER.value: ("personal:read", "personal:write", "platform:read"),
                Role.PARTNER_STAFF.value: ("partner:read", "partner:write"),
                Role.COMMUNITY_MANAGER.value: ("community:read", "community:write"),
                Role.PLATFORM_OPERATOR.value: ("platform:*", "demo:reset", "demo:switch"),
            }
            role_row = connection.execute("SELECT role FROM role_memberships WHERE id=?", (membership_id,)).fetchone()
            connection.execute(
                """INSERT INTO api_credentials
                   (id,membership_id,key_hash,label,scopes_json,expires_at,revoked_at,created_at)
                   VALUES (?,?,?,?,?,?,NULL,?)""",
                (
                    credential_id, membership_id, _key_hash(raw_key), "Web workspace session",
                    json.dumps(scopes_by_role[role_row["role"]]),
                    (expires + ttl).isoformat(), self._timestamp(),
                ),
            )
        return raw_key, self.resolve_bearer(raw_key)

    def register_workspace_membership(
        self,
        *,
        account_id: str,
        display_name: str,
        workspace_id: str,
        kind: WorkspaceKind,
        owner_ref: str,
        workspace_name: str,
        role: Role = Role.MEMBER,
        membership_id: str | None = None,
        demo_workspace_id: str | None = None,
    ) -> str:
        membership_id = membership_id or f"membership-{uuid4().hex}"
        with self._connect() as connection:
            self._upsert_account(connection, account_id, display_name)
            self._upsert_workspace(
                connection,
                workspace_id=workspace_id,
                kind=kind,
                owner_ref=owner_ref,
                name=workspace_name,
                demo_workspace_id=demo_workspace_id or f"demo-{account_id}",
            )
            existing = connection.execute(
                """SELECT id FROM role_memberships
                   WHERE account_id=? AND workspace_id=? AND role=?""",
                (account_id, workspace_id, role.value),
            ).fetchone()
            if existing is not None:
                membership_id = existing["id"]
            self._upsert_membership(
                connection,
                membership_id=membership_id,
                account_id=account_id,
                workspace_id=workspace_id,
                role=role,
            )
        return membership_id

    def revoke_workspace_membership(self, *, account_id: str, workspace_id: str) -> None:
        """Revoke every active role for one account/workspace and its sessions."""
        timestamp = self._timestamp()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id FROM role_memberships
                   WHERE account_id=? AND workspace_id=? AND status='active'""",
                (account_id, workspace_id),
            ).fetchall()
            membership_ids = [row["id"] for row in rows]
            if not membership_ids:
                return
            placeholders = ",".join("?" for _ in membership_ids)
            connection.execute(
                f"UPDATE api_credentials SET revoked_at=? WHERE membership_id IN ({placeholders})",
                [timestamp, *membership_ids],
            )
            connection.execute(
                f"UPDATE role_memberships SET status='revoked',updated_at=? WHERE id IN ({placeholders})",
                [timestamp, *membership_ids],
            )
            remaining = connection.execute(
                "SELECT 1 FROM role_memberships WHERE workspace_id=? AND status='active' LIMIT 1",
                (workspace_id,),
            ).fetchone()
            if remaining is None:
                connection.execute(
                    "UPDATE workspaces SET status='archived',updated_at=? WHERE id=?",
                    (timestamp, workspace_id),
                )

    def mark_demo_reset(self, demo_workspace_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT seed_version,reset_version FROM demo_workspaces WHERE id=?",
                (demo_workspace_id,),
            ).fetchone()
            if row is None:
                raise AccessError("查無 DemoWorkspace")
            reset_at = self._timestamp()
            next_version = int(row["reset_version"]) + 1
            connection.execute(
                "UPDATE demo_workspaces SET reset_version=?,last_reset_at=?,seed_version=? WHERE id=?",
                (next_version, reset_at, SEED_VERSION, demo_workspace_id),
            )
            return {
                "id": demo_workspace_id,
                "seedVersion": SEED_VERSION,
                "resetVersion": next_version,
                "lastResetAt": reset_at,
            }
