from __future__ import annotations

import secrets
import sqlite3
import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from core.access import Role, SqliteAccessRepository, WorkspaceKind
from core.data.personas import PERSONAS


class CommunityError(ValueError):
    pass


class CommunityPermissionError(CommunityError):
    pass


class SqliteCommunityRepository:
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
            self._seed()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS communities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','archived')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS community_memberships (
                    community_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('resident','manager')),
                    status TEXT NOT NULL CHECK(status IN ('active','left')),
                    is_default INTEGER NOT NULL DEFAULT 0,
                    joined_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(community_id,account_id),
                    FOREIGN KEY(community_id) REFERENCES communities(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS community_join_requests (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    note TEXT,
                    status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','cancelled')),
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(community_id) REFERENCES communities(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_community_join
                    ON community_join_requests(community_id,account_id) WHERE status='pending';
                CREATE TABLE IF NOT EXISTS community_invites (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    created_by TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    max_uses INTEGER NOT NULL,
                    used_count INTEGER NOT NULL DEFAULT 0,
                    revoked_at TEXT,
                    idempotency_key TEXT,
                    idempotency_fingerprint TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(community_id) REFERENCES communities(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS community_invite_joins (
                    idempotency_key TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    invite_code TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    community_id TEXT NOT NULL,
                    community_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS community_announcements (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    published_by TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE,
                    FOREIGN KEY(community_id) REFERENCES communities(id) ON DELETE CASCADE
                );
                """
            )
            invite_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(community_invites)")
            }
            for column in ("idempotency_key", "idempotency_fingerprint"):
                if column not in invite_columns:
                    connection.execute(f"ALTER TABLE community_invites ADD COLUMN {column} TEXT")
            connection.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_community_invite_idempotency
                   ON community_invites(idempotency_key) WHERE idempotency_key IS NOT NULL"""
            )

    def _register_workspace(
        self,
        *,
        community_id: str,
        community_name: str,
        account_id: str,
        display_name: str,
        domain_role: str,
    ) -> None:
        if self.access is None:
            return
        self.access.register_workspace_membership(
            account_id=account_id,
            display_name=display_name,
            workspace_id=f"workspace-community-{community_id.removeprefix('community-')}",
            kind=WorkspaceKind.COMMUNITY,
            owner_ref=community_id,
            workspace_name=community_name,
            role=Role.COMMUNITY_MANAGER if domain_role == "manager" else Role.MEMBER,
            membership_id=f"membership-community-{community_id}-{account_id}",
        )

    def _seed(self) -> None:
        timestamp = self._timestamp()
        xiaoyuan, chen, vivian = PERSONAS
        communities = (
            ("community-sunshine", "陽光社區", "臺中市西屯區臺灣大道三段99號"),
            ("community-greenfield", "綠園社區", "臺中市西屯區福星路168號"),
        )
        memberships = (
            ("community-sunshine", xiaoyuan.id, xiaoyuan.name, "resident", 1),
            ("community-sunshine", chen.id, chen.name, "resident", 1),
            ("community-sunshine", vivian.id, vivian.name, "resident", 1),
            # 主要展示住戶。他不是官方訂單推導出來的 persona，但社區是「範圍」不是
            # 「身分」（ADR-0003）——住戶端的社區頁一載入就會讀公告，沒有這筆
            # membership 就會拿到 403，畫面顯示成「請確認後端服務是否啟動」。
            ("community-sunshine", "household-wang-xiaoming", "王小明", "resident", 1),
            ("community-sunshine", "demo-community-manager", "陽光社區管理者", "manager", 0),
            ("community-greenfield", xiaoyuan.id, xiaoyuan.name, "resident", 0),
        )
        with self._connect() as connection:
            for community_id, name, address in communities:
                connection.execute(
                    """INSERT OR IGNORE INTO communities
                       (id,name,address,status,created_at,updated_at) VALUES (?,?,?,'active',?,?)""",
                    (community_id, name, address, timestamp, timestamp),
                )
            for community_id, account_id, display_name, role, is_default in memberships:
                connection.execute(
                    """INSERT OR IGNORE INTO community_memberships
                       (community_id,account_id,display_name,role,status,is_default,joined_at,updated_at)
                       VALUES (?,?,?,?,'active',?,?,?)""",
                    (community_id, account_id, display_name, role, is_default, timestamp, timestamp),
                )
        by_id = {community_id: name for community_id, name, _ in communities}
        for community_id, account_id, display_name, role, _ in memberships:
            self._register_workspace(
                community_id=community_id,
                community_name=by_id[community_id],
                account_id=account_id,
                display_name=display_name,
                domain_role=role,
            )

    def _require_manager(self, connection: sqlite3.Connection, community_id: str, account_id: str) -> None:
        row = connection.execute(
            """SELECT 1 FROM community_memberships WHERE community_id=? AND account_id=?
               AND role='manager' AND status='active'""",
            (community_id, account_id),
        ).fetchone()
        if row is None:
            raise CommunityPermissionError("只有此社區管理者可以執行這項操作")

    def _community(self, connection: sqlite3.Connection, community_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM communities WHERE id=? AND status='active'", (community_id,),
        ).fetchone()
        if row is None:
            raise CommunityError("查無社區")
        return row

    def list_available(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT c.*,m.role,m.status membership_status,m.is_default
                   FROM communities c LEFT JOIN community_memberships m
                     ON m.community_id=c.id AND m.account_id=? AND m.status='active'
                   WHERE c.status='active' ORDER BY c.name""",
                (account_id,),
            ).fetchall()
            pending = {
                row["community_id"]
                for row in connection.execute(
                    "SELECT community_id FROM community_join_requests WHERE account_id=? AND status='pending'",
                    (account_id,),
                ).fetchall()
            }
            return [
                {
                    "id": row["id"], "name": row["name"], "address": row["address"],
                    "workspaceId": f"workspace-community-{row['id'].removeprefix('community-')}",
                    "membership": None if row["role"] is None else {
                        "role": row["role"], "status": row["membership_status"],
                        "isDefault": bool(row["is_default"]),
                    },
                    "joinRequestPending": row["id"] in pending,
                }
                for row in rows
            ]

    def request_join(
        self,
        community_id: str,
        *,
        account_id: str,
        display_name: str,
        note: str | None = None,
        idempotency_key: str,
    ) -> dict:
        if not idempotency_key.strip():
            raise CommunityError("缺少 Idempotency-Key")
        request_id = f"community-request-{uuid4().hex[:12]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            community = self._community(connection, community_id)
            active = connection.execute(
                """SELECT 1 FROM community_memberships
                   WHERE community_id=? AND account_id=? AND status='active'""",
                (community_id, account_id),
            ).fetchone()
            if active:
                raise CommunityError("你已經是這個社區的成員")
            existing = connection.execute(
                """SELECT * FROM community_join_requests
                   WHERE community_id=? AND account_id=? AND status='pending'""",
                (community_id, account_id),
            ).fetchone()
            if existing:
                return {"id": existing["id"], "status": existing["status"], "idempotentReplay": True}
            connection.execute(
                """INSERT INTO community_join_requests
                   (id,community_id,account_id,display_name,note,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,'pending',?,?)""",
                (request_id, community_id, account_id, display_name, note, timestamp, timestamp),
            )
            return {
                "id": request_id, "communityId": community_id, "communityName": community["name"],
                "status": "pending", "idempotentReplay": False,
            }

    def list_requests(self, community_id: str, *, manager_account_id: str) -> list[dict]:
        with self._connect() as connection:
            self._require_manager(connection, community_id, manager_account_id)
            rows = connection.execute(
                """SELECT id,account_id,display_name,note,status,created_at
                   FROM community_join_requests WHERE community_id=? ORDER BY created_at""",
                (community_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def review_request(
        self,
        request_id: str,
        *,
        manager_account_id: str,
        approve: bool,
        idempotency_key: str,
    ) -> dict:
        if not idempotency_key.strip():
            raise CommunityError("缺少 Idempotency-Key")
        timestamp = self._timestamp()
        register: tuple[str, str, str, str] | None = None
        with self._connect() as connection:
            request = connection.execute(
                "SELECT * FROM community_join_requests WHERE id=?", (request_id,),
            ).fetchone()
            if request is None:
                raise CommunityError("查無加入申請")
            self._require_manager(connection, request["community_id"], manager_account_id)
            desired = "approved" if approve else "rejected"
            if request["status"] != "pending":
                if request["status"] != desired:
                    raise CommunityError("此申請已處理，不能改成另一個結果")
                return {"id": request_id, "status": desired, "idempotentReplay": True}
            connection.execute(
                """UPDATE community_join_requests SET status=?,reviewed_by=?,reviewed_at=?,updated_at=?
                   WHERE id=?""",
                (desired, manager_account_id, timestamp, timestamp, request_id),
            )
            if approve:
                has_default = connection.execute(
                    """SELECT 1 FROM community_memberships
                       WHERE account_id=? AND status='active' AND is_default=1""",
                    (request["account_id"],),
                ).fetchone()
                connection.execute(
                    """INSERT INTO community_memberships
                       (community_id,account_id,display_name,role,status,is_default,joined_at,updated_at)
                       VALUES (?,?,?,'resident','active',?,?,?)
                       ON CONFLICT(community_id,account_id) DO UPDATE SET
                         display_name=excluded.display_name,role='resident',status='active',updated_at=excluded.updated_at""",
                    (
                        request["community_id"], request["account_id"], request["display_name"],
                        0 if has_default else 1, timestamp, timestamp,
                    ),
                )
                community = self._community(connection, request["community_id"])
                register = (community["id"], community["name"], request["account_id"], request["display_name"])
        if register:
            self._register_workspace(
                community_id=register[0], community_name=register[1],
                account_id=register[2], display_name=register[3], domain_role="resident",
            )
        return {"id": request_id, "status": desired, "idempotentReplay": False}

    def create_invite(
        self,
        community_id: str,
        *,
        manager_account_id: str,
        max_uses: int = 1,
        valid_days: int = 7,
        idempotency_key: str | None = None,
    ) -> dict:
        if max_uses < 1 or max_uses > 100:
            raise CommunityError("邀請使用次數需為 1–100")
        normalized_key = (idempotency_key or "").strip() or None
        fingerprint = hashlib.sha256(
            f"{community_id}|{manager_account_id}|{max_uses}|{valid_days}".encode()
        ).hexdigest()
        with self._connect() as connection:
            self._require_manager(connection, community_id, manager_account_id)
            self._community(connection, community_id)
            if normalized_key:
                existing = connection.execute(
                    "SELECT * FROM community_invites WHERE idempotency_key=?", (normalized_key,),
                ).fetchone()
                if existing:
                    if existing["idempotency_fingerprint"] != fingerprint:
                        raise CommunityError("相同 Idempotency-Key 不可用於不同社區邀請")
                    return {
                        "id": existing["id"], "communityId": existing["community_id"],
                        "code": existing["code"], "expiresAt": existing["expires_at"],
                        "maxUses": existing["max_uses"], "idempotentReplay": True,
                    }
            for _ in range(10):
                code = f"COMM-{secrets.randbelow(900000) + 100000}"
                if connection.execute("SELECT 1 FROM community_invites WHERE code=?", (code,)).fetchone() is None:
                    break
            else:  # pragma: no cover
                raise CommunityError("暫時無法建立邀請碼")
            invite_id = f"community-invite-{uuid4().hex[:12]}"
            expires_at = (self._moment() + timedelta(days=valid_days)).isoformat()
            connection.execute(
                """INSERT INTO community_invites
                   (id,community_id,code,created_by,expires_at,max_uses,created_at,
                    idempotency_key,idempotency_fingerprint)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    invite_id, community_id, code, manager_account_id, expires_at, max_uses,
                    self._timestamp(), normalized_key, fingerprint if normalized_key else None,
                ),
            )
            return {"id": invite_id, "communityId": community_id, "code": code, "expiresAt": expires_at, "maxUses": max_uses}

    def join_with_invite(
        self, *, code: str, account_id: str, display_name: str,
        idempotency_key: str | None = None,
    ) -> dict:
        register: tuple[str, str] | None = None
        normalized_code = code.strip().upper()
        normalized_key = (idempotency_key or "").strip() or None
        fingerprint = hashlib.sha256(
            f"{normalized_code}|{account_id}|{display_name.strip()}".encode()
        ).hexdigest()
        with self._connect() as connection:
            if normalized_key:
                replay = connection.execute(
                    "SELECT * FROM community_invite_joins WHERE idempotency_key=?", (normalized_key,),
                ).fetchone()
                if replay:
                    if replay["fingerprint"] != fingerprint:
                        raise CommunityError("相同 Idempotency-Key 不可用於不同社區加入操作")
                    return {
                        "communityId": replay["community_id"],
                        "communityName": replay["community_name"],
                        "status": "active", "idempotentReplay": True,
                    }
            invite = connection.execute(
                "SELECT * FROM community_invites WHERE code=?", (normalized_code,),
            ).fetchone()
            if invite is None or invite["revoked_at"] is not None:
                raise CommunityError("社區邀請碼無效")
            existing_membership = connection.execute(
                """SELECT 1 FROM community_memberships
                   WHERE community_id=? AND account_id=? AND status='active'""",
                (invite["community_id"], account_id),
            ).fetchone()
            if existing_membership:
                community = self._community(connection, invite["community_id"])
                if normalized_key:
                    connection.execute(
                        """INSERT INTO community_invite_joins
                           (idempotency_key,account_id,invite_code,fingerprint,community_id,community_name,created_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (
                            normalized_key, account_id, normalized_code, fingerprint,
                            community["id"], community["name"], self._timestamp(),
                        ),
                    )
                return {
                    "communityId": community["id"], "communityName": community["name"],
                    "status": "active", "idempotentReplay": True,
                }
            if invite["expires_at"] <= self._timestamp() or invite["used_count"] >= invite["max_uses"]:
                raise CommunityError("社區邀請碼已過期或已達使用上限")
            community = self._community(connection, invite["community_id"])
            has_default = connection.execute(
                "SELECT 1 FROM community_memberships WHERE account_id=? AND status='active' AND is_default=1",
                (account_id,),
            ).fetchone()
            timestamp = self._timestamp()
            connection.execute(
                """INSERT INTO community_memberships
                   (community_id,account_id,display_name,role,status,is_default,joined_at,updated_at)
                   VALUES (?,?,?,'resident','active',?,?,?)
                   ON CONFLICT(community_id,account_id) DO UPDATE SET
                     display_name=excluded.display_name,status='active',updated_at=excluded.updated_at""",
                (community["id"], account_id, display_name, 0 if has_default else 1, timestamp, timestamp),
            )
            connection.execute("UPDATE community_invites SET used_count=used_count+1 WHERE id=?", (invite["id"],))
            register = (community["id"], community["name"])
            if normalized_key:
                connection.execute(
                    """INSERT INTO community_invite_joins
                       (idempotency_key,account_id,invite_code,fingerprint,community_id,community_name,created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        normalized_key, account_id, normalized_code, fingerprint,
                        community["id"], community["name"], timestamp,
                    ),
                )
        self._register_workspace(
            community_id=register[0], community_name=register[1], account_id=account_id,
            display_name=display_name, domain_role="resident",
        )
        return {"communityId": register[0], "communityName": register[1], "status": "active"}

    def list_announcements(self, community_id: str, *, account_id: str) -> list[dict]:
        """公告:社區成員(住戶或管理者)可讀。"""
        with self._connect() as connection:
            self._community(connection, community_id)
            member = connection.execute(
                """SELECT 1 FROM community_memberships WHERE community_id=? AND account_id=?
                   AND status='active'""",
                (community_id, account_id),
            ).fetchone()
            if member is None:
                raise CommunityPermissionError("只有社區成員可以查看公告")
            rows = connection.execute(
                """SELECT * FROM community_announcements WHERE community_id=?
                   ORDER BY published_at DESC, id DESC""",
                (community_id,),
            ).fetchall()
            return [{
                "id": row["id"], "communityId": row["community_id"],
                "title": row["title"], "body": row["body"],
                "publishedBy": row["published_by"], "publishedAt": row["published_at"],
            } for row in rows]

    def publish_announcement(
        self, community_id: str, *,
        manager_account_id: str, title: str, body: str, idempotency_key: str,
    ) -> dict:
        """發布公告:僅該社區管理者;同 Idempotency-Key 回放同一則。"""
        title = title.strip()
        body = body.strip()
        if not title or not body:
            raise CommunityError("公告標題與內容不可空白")
        with self._connect() as connection:
            self._community(connection, community_id)
            self._require_manager(connection, community_id, manager_account_id)
            existing = connection.execute(
                "SELECT * FROM community_announcements WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["community_id"] != community_id or existing["title"] != title:
                    raise CommunityError("同一 Idempotency-Key 不可用於不同請求內容")
                return {
                    "id": existing["id"], "communityId": existing["community_id"],
                    "title": existing["title"], "body": existing["body"],
                    "publishedBy": existing["published_by"], "publishedAt": existing["published_at"],
                    "idempotentReplay": True,
                }
            announcement_id = f"announcement-{uuid4().hex[:12]}"
            timestamp = self._timestamp()
            connection.execute(
                """INSERT INTO community_announcements
                   (id,community_id,title,body,published_by,published_at,idempotency_key)
                   VALUES (?,?,?,?,?,?,?)""",
                (announcement_id, community_id, title, body, manager_account_id, timestamp, idempotency_key),
            )
            return {
                "id": announcement_id, "communityId": community_id,
                "title": title, "body": body,
                "publishedBy": manager_account_id, "publishedAt": timestamp,
            }

    def set_default(self, community_id: str, *, account_id: str) -> dict:
        with self._connect() as connection:
            membership = connection.execute(
                """SELECT 1 FROM community_memberships
                   WHERE community_id=? AND account_id=? AND status='active'""",
                (community_id, account_id),
            ).fetchone()
            if membership is None:
                raise CommunityPermissionError("你不是這個社區的成員")
            connection.execute("UPDATE community_memberships SET is_default=0 WHERE account_id=?", (account_id,))
            connection.execute(
                "UPDATE community_memberships SET is_default=1,updated_at=? WHERE community_id=? AND account_id=?",
                (self._timestamp(), community_id, account_id),
            )
            return {"communityId": community_id, "isDefault": True}
