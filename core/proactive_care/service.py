"""Explicitly-authorized life-context events and in-app care messages.

The v4 care loop deliberately separates three states:

* a whitelisted context event exists;
* a deterministic candidate is generated from that event; and
* a member-visible message is delivered and can be acted on.

No background location, calendar scraping, push notification, or external
side effect is performed here.  The seeded event is competition demo data and
is labelled as such in every projection.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from .policy import CarePreferences, evaluate_delivery


class CareError(ValueError):
    pass


CareAction = Literal["ignore", "snooze", "close", "open_guide"]
CARE_ACTIONS: set[str] = {"ignore", "snooze", "close", "open_guide"}
MESSAGE_STATES = {"delivered", "ignored", "snoozed", "closed"}

DEMO_LIFE_GUIDE = {
    "status": "published",
    "title": "中元普渡準備・競賽 Demo 指南",
    "updatedAt": "2026-08-01",
    "reviewedBy": "AIWave Demo Editorial",
    "source": "AIWave 競賽 Demo 編寫資料",
    "message": "這是一份人工檢視過的競賽 Demo 指南，不是政府公告或採購清單；請依家庭與社區規範調整。",
    "steps": [
        {"id": "confirm-context", "title": "先確認情境", "body": "確認家人是否參與、日期、地點與社區公共區域規則。"},
        {"id": "separate-items", "title": "分開必要與可選", "body": "把家中已有與仍需準備的項目分開，不把便利或合作推薦誤標成必要。"},
        {"id": "make-checklist", "title": "建立可修改清單", "body": "依人數、場地與保存方式建立準備清單，活動前再次確認安全與清潔安排。"},
    ],
    "preparationItems": [
        {"id": "common-supplies", "name": "供桌／容器與飲水", "necessity": "common-required", "quantityBasis": "依家庭與場地規範", "estimatedPoints": 20},
        {"id": "optional-food", "name": "水果或點心", "necessity": "optional", "quantityBasis": "依參與人數與家庭習慣", "estimatedPoints": 15},
        {"id": "cleaning-storage", "name": "清潔與收納用品", "necessity": "convenience", "quantityBasis": "依場地大小", "estimatedPoints": 10},
        {"id": "community-help", "name": "社區代收／整理服務", "necessity": "cooperation-recommendation", "cooperationLabel": "合作推薦（非必要）", "quantityBasis": "需另行確認", "estimatedPoints": 20},
    ],
    "pointsEstimate": {"min": 20, "max": 65, "label": "Demo 點數估算 20–65 點"},
    "warnings": [
        "不同家庭、宗教與社區規定可能不同；不確定時先詢問家人或管理室。",
        "食品、香火、用火與公共空間使用要遵守當地安全規範。",
    ],
    "suggestedActions": [
        {"type": "create-checklist", "label": "幫我整理準備清單"},
        {"type": "view-life-circle", "label": "查看生活圈"},
    ],
    "commercialBoundary": "只整理類別與 Demo 點數估算，不建立訂單、不代替會員同意採購。",
}


class ProactiveCareService:
    """Deterministic care candidate/message store scoped to a Demo member."""

    DEMO_EVENT_ID = "life-event-demo-zhongyuan-2026"
    DEMO_EVENT_ALLOWLIST = {"competition_demo_event"}

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

    def _now_value(self) -> datetime:
        value = self._now()
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS v4_life_context_events (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    starts_at TEXT,
                    source TEXT NOT NULL,
                    authorization TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,workspace_id,account_id,id)
                );
                CREATE INDEX IF NOT EXISTS ix_life_context_owner
                    ON v4_life_context_events(demo_workspace_id,workspace_id,account_id,starts_at);
                CREATE TABLE IF NOT EXISTS v4_care_candidates (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('candidate','delivered','suppressed')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,workspace_id,account_id,event_id,kind)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_care_candidates_owner
                    ON v4_care_candidates(demo_workspace_id,workspace_id,account_id,created_at);
                CREATE TABLE IF NOT EXISTS v4_care_messages (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('delivered','ignored','snoozed','closed')),
                    delivered_at TEXT NOT NULL,
                    acted_at TEXT,
                    action TEXT,
                    UNIQUE(demo_workspace_id,workspace_id,account_id,candidate_id)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_care_messages_owner
                    ON v4_care_messages(demo_workspace_id,workspace_id,account_id,delivered_at);
                """
            )

    @staticmethod
    def _decode(raw: str) -> dict[str, Any]:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}

    def ensure_demo_event(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict[str, Any]:
        """Create the one explicitly-whitelisted competition event if absent."""

        timestamp = self._timestamp()
        data = {
            "dataSource": "competition_demo_event",
            "isDemo": True,
            "officialCalendar": False,
            "authorization": "member_demo_allowlist",
            "dateSource": "competition_demo_seed",
            "guideStatus": "published_internal_demo",
        }
        event_id = f"{self.DEMO_EVENT_ID}-{account_id}"
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO v4_life_context_events
                   (id,demo_workspace_id,workspace_id,account_id,event_type,title,starts_at,
                    source,authorization,data_json,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id, demo_workspace_id, workspace_id, account_id,
                    "demo_cultural_preparation", "中元關懷 Demo 事件（競賽展示資料）",
                    "2026-08-15", "competition_demo_event", "member_demo_allowlist",
                    json.dumps(data, ensure_ascii=False), timestamp, timestamp,
                ),
            )
            row = connection.execute(
                """SELECT * FROM v4_life_context_events
                   WHERE id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (event_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
        if row is None:  # pragma: no cover - defensive database failure guard
            raise CareError("Demo event 建立失敗")
        return self._event(row)

    @staticmethod
    def _event(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "eventType": row["event_type"], "title": row["title"],
            "startsAt": row["starts_at"], "source": row["source"],
            "authorization": row["authorization"], "data": json.loads(row["data_json"]),
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _candidate(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "eventId": row["event_id"], "kind": row["kind"],
            "reason": row["reason"], "evidence": json.loads(row["evidence_json"]),
            "status": row["status"], "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _message(row: sqlite3.Row, candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "candidateId": row["candidate_id"], "state": row["state"],
            "deliveredAt": row["delivered_at"], "actedAt": row["acted_at"],
            "action": row["action"], "candidate": candidate,
        }

    def generate_candidates(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> list[dict[str, Any]]:
        event = self.ensure_demo_event(
            demo_workspace_id=demo_workspace_id, workspace_id=workspace_id, account_id=account_id,
        )
        if event["source"] not in self.DEMO_EVENT_ALLOWLIST:
            raise CareError("這個 life context event 不在 Demo 白名單")
        timestamp = self._timestamp()
        evidence = {
            "dataUsed": ["explicitly_authorized_demo_event"],
            "source": event["source"],
            "eventId": event["id"],
            "isDemo": True,
            "noBackgroundTracking": True,
            "guideStatus": event["data"].get("guideStatus"),
            "actions": sorted(CARE_ACTIONS),
        }
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO v4_care_candidates
                   (id,event_id,demo_workspace_id,workspace_id,account_id,kind,reason,
                    evidence_json,status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"care-candidate-{account_id}-{event['id']}", event["id"],
                    demo_workspace_id, workspace_id, account_id, "life_preparation",
                    "你已授權的競賽 Demo event 可能需要提前查看準備資訊。",
                    json.dumps(evidence, ensure_ascii=False), "candidate", timestamp, timestamp,
                ),
            )
            rows = connection.execute(
                """SELECT * FROM v4_care_candidates
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=?
                   ORDER BY created_at,id""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
        return [self._candidate(row) for row in rows]

    def deliver(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        preferences: CarePreferences | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate candidates, then deliver eligible messages; repeated calls are idempotent."""

        candidates = self.generate_candidates(
            demo_workspace_id=demo_workspace_id, workspace_id=workspace_id, account_id=account_id,
        )
        preferences = preferences or CarePreferences()
        timestamp = self._timestamp()
        with self._connect() as connection:
            recent_rows = connection.execute(
                """SELECT c.kind,m.delivered_at AS deliveredAt
                   FROM v4_care_messages m JOIN v4_care_candidates c ON c.id=m.candidate_id
                   WHERE m.demo_workspace_id=? AND m.workspace_id=? AND m.account_id=?""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
            recent_deliveries = [dict(row) for row in recent_rows]
            for candidate in candidates:
                decision = evaluate_delivery(
                    candidate, preferences=preferences, now=self._now_value(),
                    recent_deliveries=recent_deliveries,
                )
                if not decision.allowed:
                    continue
                connection.execute(
                    """INSERT OR IGNORE INTO v4_care_messages
                       (id,candidate_id,demo_workspace_id,workspace_id,account_id,state,delivered_at)
                       VALUES (?,?,?,?,?,'delivered',?)""",
                    (
                        f"care-message-{candidate['id']}", candidate["id"], demo_workspace_id,
                        workspace_id, account_id, timestamp,
                    ),
                )
                recent_deliveries.append({"kind": candidate["kind"], "deliveredAt": timestamp})
                connection.execute(
                    """UPDATE v4_care_candidates SET status='delivered',updated_at=?
                       WHERE id=? AND status='candidate'""",
                    (timestamp, candidate["id"]),
                )
            rows = connection.execute(
                """SELECT m.*,c.kind,c.reason,c.evidence_json,c.event_id,c.status AS candidate_status,
                          c.created_at,c.updated_at
                   FROM v4_care_messages m JOIN v4_care_candidates c ON c.id=m.candidate_id
                   WHERE m.demo_workspace_id=? AND m.workspace_id=? AND m.account_id=?
                   ORDER BY m.delivered_at DESC,m.id""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
        return [
            self._message(
                row,
                {
                    "id": row["candidate_id"], "eventId": row["event_id"], "kind": row["kind"],
                    "reason": row["reason"], "evidence": json.loads(row["evidence_json"]),
                    "status": row["candidate_status"], "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                },
            )
            for row in rows
        ]

    def list_messages(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        include_closed: bool = False,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT m.*,c.kind,c.reason,c.evidence_json,c.event_id,c.status AS candidate_status,
                          c.created_at,c.updated_at
                   FROM v4_care_messages m JOIN v4_care_candidates c ON c.id=m.candidate_id
                   WHERE m.demo_workspace_id=? AND m.workspace_id=? AND m.account_id=?
                   ORDER BY m.delivered_at DESC,m.id""",
                (demo_workspace_id, workspace_id, account_id),
            ).fetchall()
        messages = [self._message_from_join(row) for row in rows]
        if include_closed:
            return messages
        return [item for item in messages if item["state"] not in {"closed", "ignored", "snoozed"}]

    def act(
        self,
        message_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        action: CareAction,
    ) -> dict[str, Any]:
        if action not in CARE_ACTIONS:
            raise CareError("照護訊息 action 不在允許清單")
        timestamp = self._timestamp()
        state = {"ignore": "ignored", "snooze": "snoozed", "close": "closed", "open_guide": "delivered"}[action]
        with self._connect() as connection:
            row = connection.execute(
                """SELECT m.*,c.kind,c.reason,c.evidence_json,c.event_id,c.status AS candidate_status,
                          c.created_at,c.updated_at
                   FROM v4_care_messages m JOIN v4_care_candidates c ON c.id=m.candidate_id
                   WHERE m.id=? AND m.demo_workspace_id=? AND m.workspace_id=? AND m.account_id=?""",
                (message_id, demo_workspace_id, workspace_id, account_id),
            ).fetchone()
            if row is None:
                raise CareError("查無照護訊息")
            if row["state"] in {"ignored", "closed"} and action != "open_guide":
                result = self._message_from_join(row)
                result["idempotentReplay"] = True
                return result
            connection.execute(
                """UPDATE v4_care_messages SET state=?,acted_at=?,action=? WHERE id=?""",
                (state, timestamp, action, message_id),
            )
            updated = connection.execute(
                """SELECT m.*,c.kind,c.reason,c.evidence_json,c.event_id,c.status AS candidate_status,
                          c.created_at,c.updated_at
                   FROM v4_care_messages m JOIN v4_care_candidates c ON c.id=m.candidate_id WHERE m.id=?""",
                (message_id,),
            ).fetchone()
        result = self._message_from_join(updated)
        result["idempotentReplay"] = False
        if action == "open_guide":
            result["guide"] = dict(DEMO_LIFE_GUIDE)
        return result

    def _message_from_join(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._message(
            row,
            {
                "id": row["candidate_id"], "eventId": row["event_id"], "kind": row["kind"],
                "reason": row["reason"], "evidence": json.loads(row["evidence_json"]),
                "status": row["candidate_status"], "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            },
        )
