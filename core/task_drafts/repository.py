from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SOURCE_PRIORITY = {
    "provider_default": 0,
    "profile": 1,
    "agent": 2,
    "user": 3,
}


class DraftError(ValueError):
    pass


class DraftConflict(DraftError):
    pass


class SqliteTaskDraftRepository:
    """Persistent hand-off seam shared by manual UI and Agent.

    Values carry per-field provenance. Lower-priority writers cannot silently
    replace a user's edit, and every mutation uses optimistic concurrency.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
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
                CREATE TABLE IF NOT EXISTS task_drafts (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    domain_type TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('drafting','ready','confirmed','abandoned')),
                    values_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_task_drafts_owner
                    ON task_drafts(demo_workspace_id,workspace_id,account_id,updated_at);
                """
            )
            # M4:submit 產出的正式交易識別碼(既有資料庫以 ALTER 補欄位)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(task_drafts)")}
            if "result_subject_type" not in columns:
                connection.execute("ALTER TABLE task_drafts ADD COLUMN result_subject_type TEXT")
            if "result_subject_id" not in columns:
                connection.execute("ALTER TABLE task_drafts ADD COLUMN result_subject_id TEXT")

    @staticmethod
    def _record(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "demoWorkspaceId": row["demo_workspace_id"],
            "workspaceId": row["workspace_id"],
            "accountId": row["account_id"],
            "domainType": row["domain_type"],
            "status": row["status"],
            "values": json.loads(row["values_json"]),
            "provenance": json.loads(row["provenance_json"]),
            "version": row["version"],
            "resultSubjectType": row["result_subject_type"] if "result_subject_type" in row.keys() else None,
            "resultSubjectId": row["result_subject_id"] if "result_subject_id" in row.keys() else None,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def create(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        domain_type: str,
        values: Mapping[str, object] | None = None,
        source: str,
        idempotency_key: str,
    ) -> dict:
        if source not in SOURCE_PRIORITY:
            raise DraftError("未知的草稿資料來源")
        if not domain_type.strip() or not idempotency_key.strip():
            raise DraftError("domain_type 與 Idempotency-Key 不可空白")
        timestamp = self._timestamp()
        values_dict = dict(values or {})
        provenance = {key: source for key in values_dict}
        draft_id = f"draft-{uuid4().hex[:16]}"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM task_drafts WHERE demo_workspace_id=? AND idempotency_key=?",
                (demo_workspace_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                record["idempotentReplay"] = True
                return record
            connection.execute(
                """INSERT INTO task_drafts
                   (id,demo_workspace_id,workspace_id,account_id,domain_type,status,
                    values_json,provenance_json,version,idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,'drafting',?,?,1,?,?,?)""",
                (
                    draft_id, demo_workspace_id, workspace_id, account_id, domain_type,
                    json.dumps(values_dict, ensure_ascii=False),
                    json.dumps(provenance, ensure_ascii=False),
                    idempotency_key, timestamp, timestamp,
                ),
            )
            row = connection.execute("SELECT * FROM task_drafts WHERE id=?", (draft_id,)).fetchone()
            record = self._record(row)
            record["idempotentReplay"] = False
            return record

    def require_owned(
        self,
        draft_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM task_drafts
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (draft_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise DraftError("查無草稿")
            return self._record(row)

    def list_owned(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM task_drafts
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?
                   ORDER BY updated_at DESC""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
            return [self._record(row) for row in rows]

    def update_fields(
        self,
        draft_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        expected_version: int,
        values: Mapping[str, object],
        source: str,
    ) -> dict:
        if source not in SOURCE_PRIORITY:
            raise DraftError("未知的草稿資料來源")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM task_drafts
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (draft_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise DraftError("查無草稿")
            if row["status"] not in {"drafting", "ready"}:
                raise DraftConflict("此草稿已確認或放棄，不能直接修改")
            if row["version"] != expected_version:
                raise DraftConflict("草稿版本已更新，請重新載入後再修改")
            current_values = json.loads(row["values_json"])
            provenance = json.loads(row["provenance_json"])
            ignored: list[str] = []
            for key, value in values.items():
                prior_source = provenance.get(key)
                if prior_source and SOURCE_PRIORITY[prior_source] > SOURCE_PRIORITY[source]:
                    ignored.append(key)
                    continue
                current_values[key] = value
                provenance[key] = source
            next_version = expected_version + 1
            connection.execute(
                """UPDATE task_drafts SET values_json=?,provenance_json=?,version=?,updated_at=?
                   WHERE id=?""",
                (
                    json.dumps(current_values, ensure_ascii=False),
                    json.dumps(provenance, ensure_ascii=False),
                    next_version, self._timestamp(), draft_id,
                ),
            )
            updated = connection.execute("SELECT * FROM task_drafts WHERE id=?", (draft_id,)).fetchone()
            record = self._record(updated)
            record["ignoredFields"] = ignored
            return record

    def transition(
        self,
        draft_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        expected_version: int,
        status: str,
    ) -> dict:
        allowed = {
            "drafting": {"ready", "abandoned"},
            "ready": {"drafting", "confirmed", "abandoned"},
        }
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM task_drafts
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (draft_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise DraftError("查無草稿")
            if row["version"] != expected_version:
                raise DraftConflict("草稿版本已更新，請重新載入後再操作")
            if status not in allowed.get(row["status"], set()):
                raise DraftConflict(f"草稿不可由 {row['status']} 變更為 {status}")
            connection.execute(
                "UPDATE task_drafts SET status=?,version=version+1,updated_at=? WHERE id=?",
                (status, self._timestamp(), draft_id),
            )
            return self._record(connection.execute("SELECT * FROM task_drafts WHERE id=?", (draft_id,)).fetchone())

    def record_result(
        self,
        draft_id: str,
        *,
        demo_workspace_id: str,
        subject_type: str,
        subject_id: str,
    ) -> dict:
        """submit 成功後把草稿標記為 confirmed 並記下產出的交易識別碼(冪等)。"""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_drafts WHERE id=? AND demo_workspace_id=?",
                (draft_id, demo_workspace_id),
            ).fetchone()
            if row is None:
                raise DraftError("查無草稿")
            if row["result_subject_id"] and row["result_subject_id"] != subject_id:
                raise DraftConflict("此草稿已產生另一筆交易")
            connection.execute(
                """UPDATE task_drafts SET status='confirmed',result_subject_type=?,result_subject_id=?,
                     version=version+1,updated_at=? WHERE id=? AND result_subject_id IS NULL""",
                (subject_type, subject_id, self._timestamp(), draft_id),
            )
            return self._record(connection.execute("SELECT * FROM task_drafts WHERE id=?", (draft_id,)).fetchone())

