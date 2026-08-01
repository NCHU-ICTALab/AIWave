"""ExecutionGrant(spec 15 §4.2):會產生交易前,使用者核准的有範圍授權。

內容至少包含:服務商、時間範圍、預算/點數上限、到期時間。
Agent 送單前必須 consume 一個涵蓋該筆交易的已核准 Grant;
超出範圍或已過期 → 擋下,回到「等待你確認」。持久化於 SQLite,完全確定性。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

TAIPEI = timezone(timedelta(hours=8))


class GrantError(ValueError):
    """授權不存在、未核准、過期或超出範圍。訊息可直接顯示給使用者。"""


class SqliteGrantRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(TAIPEI))
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS execution_grants (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    session_id TEXT,
                    provider_ids_json TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    budget_limit INTEGER NOT NULL CHECK(budget_limit>=0),
                    points_limit INTEGER NOT NULL CHECK(points_limit>=0),
                    budget_spent INTEGER NOT NULL DEFAULT 0,
                    points_spent INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL CHECK(status IN ('proposed','approved','revoked','expired')),
                    expires_at TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_grants_owner
                    ON execution_grants(demo_workspace_id,workspace_id,account_id,created_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _timestamp(self) -> str:
        return self._now().astimezone(TAIPEI).isoformat()

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "sessionId": row["session_id"],
            "providerIds": json.loads(row["provider_ids_json"]),
            "windowStart": row["window_start"],
            "windowEnd": row["window_end"],
            "budgetLimit": row["budget_limit"],
            "pointsLimit": row["points_limit"],
            "budgetSpent": row["budget_spent"],
            "pointsSpent": row["points_spent"],
            "status": row["status"],
            "expiresAt": row["expires_at"],
            "summary": row["summary"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    # ── 生命週期 ─────────────────────────────────

    def propose(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        session_id: str | None,
        provider_ids: list[str],
        window_start: str,
        window_end: str,
        budget_limit: int,
        points_limit: int,
        summary: str,
        ttl_minutes: int = 30,
    ) -> dict:
        if not provider_ids:
            raise GrantError("授權必須指定至少一個服務商")
        if budget_limit < 0 or points_limit < 0:
            raise GrantError("預算與點數上限不可為負")
        grant_id = f"grant-{uuid4().hex[:12]}"
        timestamp = self._timestamp()
        expires = (self._now().astimezone(TAIPEI) + timedelta(minutes=ttl_minutes)).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO execution_grants
                   (id,demo_workspace_id,workspace_id,account_id,session_id,provider_ids_json,
                    window_start,window_end,budget_limit,points_limit,status,expires_at,summary,
                    created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,'proposed',?,?,?,?)""",
                (
                    grant_id, demo_workspace_id, workspace_id, account_id, session_id,
                    json.dumps(provider_ids, ensure_ascii=False),
                    window_start, window_end, budget_limit, points_limit,
                    expires, summary, timestamp, timestamp,
                ),
            )
        return self.get(grant_id, demo_workspace_id=demo_workspace_id,
                        workspace_id=workspace_id, account_id=account_id)

    def get(self, grant_id: str, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM execution_grants
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (grant_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise GrantError("查無此授權")
            return self._record(row)

    def approve(self, grant_id: str, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict:
        record = self.get(grant_id, demo_workspace_id=demo_workspace_id,
                          workspace_id=workspace_id, account_id=account_id)
        if record["status"] != "proposed":
            raise GrantError(f"授權狀態為 {record['status']},不可核准")
        if record["expiresAt"] < self._timestamp():
            self._set_status(grant_id, "expired")
            raise GrantError("授權已過期,請重新確認")
        self._set_status(grant_id, "approved")
        return self.get(grant_id, demo_workspace_id=demo_workspace_id,
                        workspace_id=workspace_id, account_id=account_id)

    def revoke(self, grant_id: str, *, demo_workspace_id: str, workspace_id: str, account_id: str) -> dict:
        self.get(grant_id, demo_workspace_id=demo_workspace_id,
                 workspace_id=workspace_id, account_id=account_id)
        self._set_status(grant_id, "revoked")
        return self.get(grant_id, demo_workspace_id=demo_workspace_id,
                        workspace_id=workspace_id, account_id=account_id)

    def _set_status(self, grant_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE execution_grants SET status=?, updated_at=? WHERE id=?",
                (status, self._timestamp(), grant_id),
            )

    # ── 執行時裁決 ────────────────────────────────

    def authorize_spend(
        self,
        grant_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        provider_id: str,
        starts_at: str | None,
        amount: int,
        points: int,
    ) -> dict:
        """在送單前裁決:不在範圍/超上限/過期 → GrantError(訊息給使用者看)。
        通過即累計消耗;同一 Grant 可涵蓋多筆子任務直到額度用完。"""
        record = self.get(grant_id, demo_workspace_id=demo_workspace_id,
                          workspace_id=workspace_id, account_id=account_id)
        if record["status"] != "approved":
            raise GrantError("這筆交易尚未獲得你的授權,請先核准")
        if record["expiresAt"] < self._timestamp():
            self._set_status(grant_id, "expired")
            raise GrantError("授權已過期,請重新核准後再執行")
        if provider_id not in record["providerIds"]:
            raise GrantError("此服務商不在你核准的範圍內,請重新確認")
        if starts_at is not None and not (
            record["windowStart"][:10] <= starts_at[:10] <= record["windowEnd"][:10]
        ):
            raise GrantError("預約時間不在你核准的時間範圍內,請重新確認")
        if record["budgetSpent"] + amount > record["budgetLimit"]:
            raise GrantError(
                f"這筆金額會超過你核准的預算上限 NT${record['budgetLimit']},請重新確認"
            )
        if record["pointsSpent"] + points > record["pointsLimit"]:
            raise GrantError("點數折抵超過你核准的上限,請重新確認")
        with self._connect() as connection:
            connection.execute(
                """UPDATE execution_grants
                   SET budget_spent=budget_spent+?, points_spent=points_spent+?, updated_at=?
                   WHERE id=?""",
                (amount, points, self._timestamp(), grant_id),
            )
        return self.get(grant_id, demo_workspace_id=demo_workspace_id,
                        workspace_id=workspace_id, account_id=account_id)

    def reset(self, *, demo_workspace_id: str | None = None) -> None:
        with self._connect() as connection:
            if demo_workspace_id:
                connection.execute(
                    "DELETE FROM execution_grants WHERE demo_workspace_id=?", (demo_workspace_id,),
                )
            else:
                connection.execute("DELETE FROM execution_grants")
