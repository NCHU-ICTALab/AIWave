"""Editable LifeTaskPackage aggregate for v4 orchestration.

The package is a draft/projection around existing TaskDrafts.  It never
creates a booking or order by itself.  Provider and slot changes are accepted
only when they select a deterministic option already supplied by the Catalog
projection, so an LLM or an arbitrary client cannot overwrite authoritative
price/provider facts.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


class TaskPackageError(ValueError):
    pass


class TaskPackageConflict(TaskPackageError):
    pass


PackageItemOperation = Literal["update", "pause", "resume", "remove", "replace_provider"]
ITEM_STATES = {"selected", "paused", "removed", "executing", "submitted", "succeeded", "failed"}
TERMINAL_PACKAGE_STATES = {"completed", "cancelled"}


class SqliteTaskPackageService:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

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
                CREATE TABLE IF NOT EXISTS v4_life_task_packages (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    beneficiary_json TEXT NOT NULL,
                    service_location_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('draft','awaiting_confirmation','executing','partial_failure','completed','cancelled')),
                    grant_id TEXT,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,workspace_id,account_id,source_type,source_id)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_task_packages_owner
                    ON v4_life_task_packages(demo_workspace_id,workspace_id,account_id,updated_at);
                CREATE TABLE IF NOT EXISTS v4_life_task_package_items (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    task_draft_id TEXT,
                    source_subtask_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    offering_id TEXT NOT NULL,
                    offering_name TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK(amount>=0),
                    points INTEGER NOT NULL CHECK(points>=0),
                    starts_at TEXT,
                    ends_at TEXT,
                    status TEXT NOT NULL CHECK(status IN ('selected','paused','removed','executing','submitted','succeeded','failed')),
                    details_json TEXT NOT NULL,
                    last_error TEXT,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(package_id) REFERENCES v4_life_task_packages(id) ON DELETE CASCADE,
                    UNIQUE(package_id,source_subtask_id)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_task_package_items_package
                    ON v4_life_task_package_items(package_id,position);
                CREATE TABLE IF NOT EXISTS v4_task_package_item_events (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    event_key TEXT NOT NULL,
                    result_status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(package_id,item_id,event_key),
                    FOREIGN KEY(package_id) REFERENCES v4_life_task_packages(id) ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES v4_life_task_package_items(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _decode(raw: str | None, fallback: Any) -> Any:
        if raw is None:
            return fallback
        value = json.loads(raw)
        return value

    @staticmethod
    def _owner_clause() -> str:
        return "demo_workspace_id=? AND workspace_id=? AND account_id=?"

    def _owner_values(self, owner: Mapping[str, str]) -> tuple[str, str, str]:
        return owner["demo_workspace_id"], owner["workspace_id"], owner["account_id"]

    def _record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        items = connection.execute(
            "SELECT * FROM v4_life_task_package_items WHERE package_id=? ORDER BY position,id",
            (row["id"],),
        ).fetchall()
        item_records = [self._item_record(item) for item in items]
        active = [item for item in item_records if item["status"] not in {"paused", "removed"}]
        selected = [item for item in active if item["status"] not in {"failed"}]
        providers = sorted({item["providerId"] for item in active})
        return {
            "id": row["id"], "demoWorkspaceId": row["demo_workspace_id"],
            "workspaceId": row["workspace_id"], "accountId": row["account_id"],
            "source": {"type": row["source_type"], "id": row["source_id"]},
            "beneficiary": self._decode(row["beneficiary_json"], {}),
            "serviceLocation": self._decode(row["service_location_json"], {}),
            "status": row["status"], "grantId": row["grant_id"], "version": row["version"],
            "totalAmount": sum(int(item["amount"]) for item in selected),
            "totalPoints": sum(int(item["points"]) for item in selected),
            "providerIds": providers,
            "selectedItemIds": [item["id"] for item in active if item["status"] == "selected"],
            "taskDraftRefs": [item["taskDraftId"] for item in item_records if item["taskDraftId"]],
            "items": item_records,
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _item_record(row: sqlite3.Row) -> dict[str, Any]:
        details = json.loads(row["details_json"])
        return {
            "id": row["id"], "position": row["position"], "taskDraftId": row["task_draft_id"],
            "sourceSubtaskId": row["source_subtask_id"], "providerId": row["provider_id"],
            "providerName": row["provider_name"], "offeringId": row["offering_id"],
            "offeringName": row["offering_name"], "amount": row["amount"], "points": row["points"],
            "startsAt": row["starts_at"], "endsAt": row["ends_at"], "status": row["status"],
            "details": details, "lastError": row["last_error"], "version": row["version"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    def create_from_subtasks(
        self,
        *,
        owner: Mapping[str, str],
        source_type: str,
        source_id: str,
        subtasks: list[Mapping[str, Any]],
        beneficiary: Mapping[str, Any] | None = None,
        service_location: Mapping[str, Any] | None = None,
        grant_id: str | None = None,
    ) -> dict[str, Any]:
        if not source_type.strip() or not source_id.strip():
            raise TaskPackageError("任務包來源不可空白")
        ready = [item for item in subtasks if item.get("status") == "ready" and item.get("selected")]
        if not ready:
            raise TaskPackageError("任務包至少需要一個已選方案")
        timestamp = self._timestamp()
        owner_values = self._owner_values(owner)
        with self._connect() as connection:
            existing = connection.execute(
                f"""SELECT * FROM v4_life_task_packages WHERE {self._owner_clause()}
                   AND source_type=? AND source_id=?""",
                (*owner_values, source_type, source_id),
            ).fetchone()
            if existing is not None:
                return self._record(connection, existing)
            package_id = f"package-{uuid4().hex[:16]}"
            status = "awaiting_confirmation" if grant_id else "draft"
            connection.execute(
                """INSERT INTO v4_life_task_packages
                   (id,demo_workspace_id,workspace_id,account_id,source_type,source_id,
                    beneficiary_json,service_location_json,status,grant_id,version,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (
                    package_id, *owner_values, source_type, source_id,
                    json.dumps(dict(beneficiary or {}), ensure_ascii=False),
                    json.dumps(dict(service_location or {}), ensure_ascii=False),
                    status, grant_id, timestamp, timestamp,
                ),
            )
            for position, subtask in enumerate(ready, start=1):
                selected = dict(subtask["selected"])
                quote = dict(subtask.get("quote") or {})
                slot = dict(selected.get("slot") or {})
                options = [dict(option) for option in (subtask.get("proposals") or [])]
                details = {
                    "source": "agent_catalog_selection",
                    "proposalOptions": options,
                    "selectedOptionId": selected.get("id"),
                    "selectedSlotId": slot.get("id"),
                    "domain": subtask.get("domain"),
                    "goal": subtask.get("goal"),
                }
                connection.execute(
                    """INSERT INTO v4_life_task_package_items
                       (id,package_id,position,task_draft_id,source_subtask_id,provider_id,provider_name,
                        offering_id,offering_name,amount,points,starts_at,ends_at,status,details_json,
                        last_error,version,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'selected',?,?,1,?,?)""",
                    (
                        f"{package_id}-item-{position}", package_id, position, subtask.get("draftId"),
                        str(subtask.get("id") or position), str(selected.get("providerId") or ""),
                        str(selected.get("providerName") or ""), str(selected.get("offeringId") or ""),
                        str(selected.get("offeringName") or ""), int(quote.get("payable", selected.get("basePrice", 0)) or 0),
                        int(quote.get("points", 0) or 0), slot.get("startsAt"), slot.get("endsAt"),
                        json.dumps(details, ensure_ascii=False), None, timestamp, timestamp,
                    ),
                )
            row = connection.execute("SELECT * FROM v4_life_task_packages WHERE id=?", (package_id,)).fetchone()
            assert row is not None
            return self._record(connection, row)

    def get_owned(self, package_id: str, *, owner: Mapping[str, str]) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM v4_life_task_packages WHERE id=? AND {self._owner_clause()}",
                (package_id, *self._owner_values(owner)),
            ).fetchone()
            if row is None:
                raise TaskPackageError("查無生活任務包")
            return self._record(connection, row)

    def list_owned(self, *, owner: Mapping[str, str]) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM v4_life_task_packages WHERE {self._owner_clause()}
                   ORDER BY updated_at DESC,id DESC""",
                self._owner_values(owner),
            ).fetchall()
            return [self._record(connection, row) for row in rows]

    def bind_grant(self, package_id: str, *, owner: Mapping[str, str], grant_id: str) -> dict[str, Any]:
        if not grant_id.strip():
            raise TaskPackageError("ExecutionGrant id 不可空白")
        timestamp = self._timestamp()
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM v4_life_task_packages WHERE id=? AND {self._owner_clause()}",
                (package_id, *self._owner_values(owner)),
            ).fetchone()
            if row is None:
                raise TaskPackageError("查無生活任務包")
            if row["grant_id"] not in {None, grant_id} and row["status"] not in {
                "draft", "awaiting_confirmation",
            }:
                raise TaskPackageConflict("任務包已綁定另一筆授權")
            connection.execute(
                """UPDATE v4_life_task_packages SET grant_id=?,status='awaiting_confirmation',version=version+1,updated_at=?
                   WHERE id=?""",
                (grant_id, timestamp, package_id),
            )
            return self._record(connection, connection.execute("SELECT * FROM v4_life_task_packages WHERE id=?", (package_id,)).fetchone())

    def _owned_item(
        self, connection: sqlite3.Connection, package_id: str, item_id: str, owner: Mapping[str, str],
    ) -> tuple[sqlite3.Row, sqlite3.Row]:
        row = connection.execute(
            f"SELECT * FROM v4_life_task_packages WHERE id=? AND {self._owner_clause()}",
            (package_id, *self._owner_values(owner)),
        ).fetchone()
        if row is None:
            raise TaskPackageError("查無生活任務包")
        item = connection.execute(
            "SELECT * FROM v4_life_task_package_items WHERE id=? AND package_id=?",
            (item_id, package_id),
        ).fetchone()
        if item is None:
            raise TaskPackageError("查無任務包項目")
        return row, item

    @staticmethod
    def _find_option(item: sqlite3.Row, changes: Mapping[str, Any]) -> dict[str, Any]:
        details = json.loads(item["details_json"])
        options = details.get("proposalOptions") or []
        provider_id = changes.get("providerId")
        offering_id = changes.get("offeringId")
        option_id = changes.get("optionId")
        for option in options:
            if option_id and option.get("id") != option_id:
                continue
            if provider_id and option.get("providerId") != provider_id:
                continue
            if offering_id and option.get("offeringId") != offering_id:
                continue
            return dict(option)
        raise TaskPackageError("只能選擇這個任務包已由 Catalog 提供的方案")

    def patch_item(
        self,
        package_id: str,
        item_id: str,
        *,
        owner: Mapping[str, str],
        expected_version: int,
        operation: PackageItemOperation,
        changes: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if operation not in {"update", "pause", "resume", "remove", "replace_provider"}:
            raise TaskPackageError("任務包項目操作不在允許清單")
        changes = dict(changes or {})
        timestamp = self._timestamp()
        with self._connect() as connection:
            package, item = self._owned_item(connection, package_id, item_id, owner)
            if package["version"] != expected_version:
                raise TaskPackageConflict("任務包版本已更新，請重新載入")
            if package["status"] in TERMINAL_PACKAGE_STATES:
                raise TaskPackageConflict("已完成或取消的任務包不能修改")
            current = item["status"]
            if current in {"executing", "submitted", "succeeded"}:
                raise TaskPackageConflict("已送出或完成的項目不能修改")
            next_values: dict[str, Any] = {
                "providerId": item["provider_id"], "providerName": item["provider_name"],
                "offeringId": item["offering_id"], "offeringName": item["offering_name"],
                "amount": item["amount"], "startsAt": item["starts_at"], "endsAt": item["ends_at"],
                "status": current, "details": json.loads(item["details_json"]),
            }
            if operation == "pause":
                next_values["status"] = "paused"
            elif operation == "resume":
                if current == "removed":
                    raise TaskPackageConflict("已刪除的項目不能直接恢復")
                next_values["status"] = "selected"
            elif operation == "remove":
                next_values["status"] = "removed"
            elif operation in {"update", "replace_provider"}:
                option = self._find_option(item, changes)
                if operation == "replace_provider" or changes.get("optionId") or changes.get("providerId"):
                    next_values.update({
                        "providerId": option.get("providerId") or next_values["providerId"],
                        "providerName": option.get("providerName") or next_values["providerName"],
                        "offeringId": option.get("offeringId") or next_values["offeringId"],
                        "offeringName": option.get("offeringName") or next_values["offeringName"],
                        "amount": int((option.get("quote") or {}).get("payable", option.get("basePrice", next_values["amount"])) or 0),
                    })
                    slot = option.get("slot") or {}
                    next_values["startsAt"] = slot.get("startsAt", next_values["startsAt"])
                    next_values["endsAt"] = slot.get("endsAt", next_values["endsAt"])
                    next_values["details"]["selectedOptionId"] = option.get("id")
                    next_values["details"]["selectedSlotId"] = slot.get("id")
                elif set(changes) <= {"startsAt", "endsAt", "slotId"}:
                    slot_options = next_values["details"].get("slotOptions") or [
                        option.get("slot") for option in next_values["details"].get("proposalOptions", []) if option.get("slot")
                    ]
                    if changes.get("slotId") and not any(slot.get("id") == changes["slotId"] for slot in slot_options):
                        raise TaskPackageError("只能選擇這個任務包已由 Catalog 提供的時段")
                    next_values["startsAt"] = changes.get("startsAt", next_values["startsAt"])
                    next_values["endsAt"] = changes.get("endsAt", next_values["endsAt"])
                    if changes.get("slotId"):
                        next_values["details"]["selectedSlotId"] = changes["slotId"]
                else:
                    raise TaskPackageError("任務包只能修改已提供的方案或時段")
            connection.execute(
                """UPDATE v4_life_task_package_items SET provider_id=?,provider_name=?,offering_id=?,offering_name=?,
                   amount=?,starts_at=?,ends_at=?,status=?,details_json=?,version=version+1,updated_at=? WHERE id=?""",
                (
                    next_values["providerId"], next_values["providerName"], next_values["offeringId"],
                    next_values["offeringName"], next_values["amount"], next_values["startsAt"],
                    next_values["endsAt"], next_values["status"], json.dumps(next_values["details"], ensure_ascii=False),
                    timestamp, item_id,
                ),
            )
            connection.execute(
                "UPDATE v4_life_task_packages SET version=version+1,updated_at=? WHERE id=?",
                (timestamp, package_id),
            )
            updated = connection.execute("SELECT * FROM v4_life_task_packages WHERE id=?", (package_id,)).fetchone()
            assert updated is not None
            return self._record(connection, updated)

    def mark_item_executing(self, package_id: str, item_id: str, *, owner: Mapping[str, str]) -> dict[str, Any]:
        timestamp = self._timestamp()
        with self._connect() as connection:
            package, item = self._owned_item(connection, package_id, item_id, owner)
            if item["status"] in {"removed", "paused", "succeeded"}:
                return self._record(connection, package)
            connection.execute(
                "UPDATE v4_life_task_package_items SET status='executing',version=version+1,updated_at=? WHERE id=?",
                (timestamp, item_id),
            )
            connection.execute(
                "UPDATE v4_life_task_packages SET status='executing',updated_at=? WHERE id=?",
                (timestamp, package_id),
            )
            return self._record(connection, connection.execute("SELECT * FROM v4_life_task_packages WHERE id=?", (package_id,)).fetchone())

    def record_item_result(
        self,
        package_id: str,
        item_id: str,
        *,
        owner: Mapping[str, str],
        status: Literal["submitted", "succeeded", "failed"],
        event_key: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"submitted", "succeeded", "failed"} or not event_key.strip():
            raise TaskPackageError("任務包結果或 event key 不合法")
        timestamp = self._timestamp()
        with self._connect() as connection:
            package, item = self._owned_item(connection, package_id, item_id, owner)
            cursor = connection.execute(
                """INSERT OR IGNORE INTO v4_task_package_item_events
                   (id,package_id,item_id,event_key,result_status,error,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (f"package-event-{uuid4().hex[:16]}", package_id, item_id, event_key, status, error, timestamp),
            )
            if cursor.rowcount == 1:
                connection.execute(
                    """UPDATE v4_life_task_package_items SET status=?,last_error=?,version=version+1,updated_at=? WHERE id=?""",
                    (status, error, timestamp, item_id),
                )
                statuses = [row["status"] for row in connection.execute(
                    "SELECT status FROM v4_life_task_package_items WHERE package_id=? AND status NOT IN ('paused','removed')",
                    (package_id,),
                ).fetchall()]
                if statuses and all(value == "succeeded" for value in statuses):
                    package_status = "completed"
                elif any(value == "failed" for value in statuses):
                    package_status = "partial_failure"
                elif any(value in {"executing", "submitted"} for value in statuses):
                    package_status = "executing"
                else:
                    package_status = package["status"]
                connection.execute(
                    "UPDATE v4_life_task_packages SET status=?,version=version+1,updated_at=? WHERE id=?",
                    (package_status, timestamp, package_id),
                )
            updated = connection.execute("SELECT * FROM v4_life_task_packages WHERE id=?", (package_id,)).fetchone()
            assert updated is not None
            result = self._record(connection, updated)
            result["idempotentReplay"] = cursor.rowcount != 1
            return result
