"""社區聯合服務：把匿名需求、方案決策與廠商履約放在同一筆可稽核資料。

這個模組不假裝連到品牌正式報價。Hero 種子與所有方案都帶 `competition_seed`
來源，讓傳輸層能如實呈現「競賽建置資料」。
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

DRAFT = "draft"
COLLECTING = "collecting"
PROPOSAL_REVIEW = "proposal_review"
ASSIGNED = "assigned"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"

STATUS_LABELS = {
    DRAFT: "草稿",
    COLLECTING: "需求募集",
    PROPOSAL_REVIEW: "方案評選",
    ASSIGNED: "已指派",
    IN_PROGRESS: "服務進行中",
    COMPLETED: "已完成",
}


class JointServiceError(ValueError):
    """聯合服務操作不符合狀態或資料契約。"""


class JointServiceRepository(Protocol):
    def list_campaigns(self) -> list[dict]: ...
    def list_for_resident(self, *, account_id: str) -> list[dict]: ...
    def get_campaign(self, campaign_id: int) -> dict | None: ...
    def create_draft(self, *, title: str, service_id: str, created_by: str | None = None) -> dict: ...
    def publish(self, campaign_id: int, *, actor: str) -> dict: ...
    def join(self, campaign_id: int, *, account_id: str, units: int, equipment: str,
             preferred_slot: str, special_requirement: str | None = None) -> dict: ...
    def prepare_proposals(self, campaign_id: int, *, actor: str) -> dict: ...
    def assign(self, campaign_id: int, *, proposal_id: str, actor: str) -> dict: ...
    def list_assigned(self, *, vendor_id: str | None = None) -> list[dict]: ...
    def start(self, campaign_id: int, *, vendor_id: str, actor: str) -> dict: ...
    def complete(self, campaign_id: int, *, vendor_id: str, actor: str, note: str) -> dict: ...


def _hero_demand() -> dict:
    return {
        "householdCount": 18,
        "unitCount": 27,
        "equipment": [{"label": "分離式冷氣", "count": 23}, {"label": "窗型冷氣", "count": 4}],
        "timePreferences": [
            {"label": "週六上午", "households": 10},
            {"label": "週六下午", "households": 5},
            {"label": "平日下午", "households": 3},
        ],
        "specialRequirements": ["3 戶需高樓外機評估", "2 戶家中有幼兒，偏好低氣味清潔"],
        "privacy": "以匿名住戶雜湊去重；方案比較不含姓名、電話與門牌",
        "source": "competition_seed",
        "sourceLabel": "競賽建置需求資料",
    }


def _hero_proposals(unit_count: int = 27) -> list[dict]:
    care_cleaning = unit_count * 1500
    value_cleaning = unit_count * 1400
    return [
        {
            "id": "proposal-care",
            "vendorId": "vendor-duskin",
            "vendorName": "DUSKIN 樂清",
            "vendorSource": "core.matching.vendors",
            "badge": "整體推薦",
            "items": [
                {"name": f"冷氣清洗 {unit_count} 台", "amount": care_cleaning},
                {"name": "公共區域防護與清潔", "amount": 2400},
                {"name": "社區分梯排程", "amount": 1800},
            ],
            "total": care_cleaning + 4200,
            "perUnit": round((care_cleaning + 4200) / max(unit_count, 1)),
            "availableSlots": ["8/8（六）09:00–17:00", "8/15（六）09:00–17:00"],
            "strengths": ["可一次涵蓋多數住戶偏好時段", "含公共區域防護", "分梯排程降低電梯壅塞"],
            "concerns": ["高樓外機需現場確認後另估"],
            "score": 92,
            "source": "competition_seed",
            "sourceLabel": "競賽建置方案，非品牌即時報價",
        },
        {
            "id": "proposal-value",
            "vendorId": "vendor-prince-property",
            "vendorName": "太子物業",
            "vendorSource": "core.matching.vendors",
            "badge": "價格較低",
            "items": [
                {"name": f"冷氣清洗 {unit_count} 台", "amount": value_cleaning},
                {"name": "耗材與室內防護", "amount": 1800},
                {"name": "社區統籌費", "amount": 900},
            ],
            "total": value_cleaning + 2700,
            "perUnit": round((value_cleaning + 2700) / max(unit_count, 1)),
            "availableSlots": ["8/12（三）09:00–17:00", "8/13（四）09:00–17:00"],
            "strengths": ["總價少 NT$4,200", "每台均價最低"],
            "concerns": ["可用時段與 15 戶週末偏好不一致", "高樓外機與公共區域防護需另確認"],
            "score": 78,
            "source": "competition_seed",
            "sourceLabel": "競賽建置方案，非品牌即時報價",
        },
    ]


class SqliteJointServiceRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None, seed: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()
        if seed:
            self._seed_hero()

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
                CREATE TABLE IF NOT EXISTS joint_service_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    community_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    demand_json TEXT NOT NULL,
                    draft_json TEXT NOT NULL,
                    proposals_json TEXT NOT NULL,
                    selected_proposal_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS joint_service_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    detail TEXT,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (campaign_id) REFERENCES joint_service_campaigns(id)
                );
                CREATE TABLE IF NOT EXISTS joint_service_signals (
                    campaign_id INTEGER NOT NULL,
                    household_hash TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    equipment TEXT NOT NULL,
                    preferred_slot TEXT NOT NULL,
                    special_requirement TEXT,
                    joined_at TEXT NOT NULL,
                    consent_version TEXT NOT NULL DEFAULT 'joint-demand-v1',
                    consented_at TEXT,
                    PRIMARY KEY (campaign_id, household_hash),
                    FOREIGN KEY (campaign_id) REFERENCES joint_service_campaigns(id)
                );
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(joint_service_signals)")}
            if "consent_version" not in columns:
                connection.execute(
                    "ALTER TABLE joint_service_signals ADD COLUMN consent_version TEXT NOT NULL DEFAULT 'joint-demand-v1'"
                )
            if "consented_at" not in columns:
                connection.execute("ALTER TABLE joint_service_signals ADD COLUMN consented_at TEXT")

    def _seed_hero(self) -> None:
        with self._connect() as connection:
            exists = connection.execute("SELECT 1 FROM joint_service_campaigns LIMIT 1").fetchone()
            if exists:
                return
            now = self._timestamp()
            collecting_draft = {
                "title": "九月冷氣聯合清洗需求調查",
                "closeTime": "2026-08-16T20:00:00+08:00",
                "notification": "只在你明確同意後，匿名彙整設備數量、偏好時段與特殊需求。",
                "questionnaire": ["冷氣型式與台數", "可服務時段", "不含姓名、電話與門牌"],
                "generatedBy": "AI Copilot 草稿；已由社區管理者確認發布",
                "serviceContext": "DUSKIN 公開服務情境；履約方案為競賽建置資料",
            }
            collecting_cursor = connection.execute(
                """INSERT INTO joint_service_campaigns
                (community_id,title,service_id,status,demand_json,draft_json,proposals_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                ("community-sunshine-demo", collecting_draft["title"], "service-aircon", COLLECTING,
                 json.dumps({
                     "householdCount": 0, "unitCount": 0, "equipment": [], "timePreferences": [],
                     "specialRequirements": [],
                     "privacy": "以匿名住戶雜湊去重；不共享姓名、電話與門牌",
                     "source": "resident_input", "sourceLabel": "住戶確認後的匿名需求",
                 }, ensure_ascii=False), json.dumps(collecting_draft, ensure_ascii=False), "[]", now, now),
            )
            connection.execute(
                "INSERT INTO joint_service_events (campaign_id,event_type,actor,detail,occurred_at) VALUES (?,?,?,?,?)",
                (int(collecting_cursor.lastrowid), "joint_service.published", "社區管理者",
                 "開始募集住戶明確同意的匿名需求", now),
            )
            draft = {
                "title": "八月冷氣聯合清洗",
                "closeTime": "2026-08-02T20:00:00+08:00",
                "notification": "18 戶需求已完成匿名彙整，請管委會比較方案後指派。",
                "questionnaire": ["冷氣型式與台數", "可服務時段", "外機位置與特殊需求"],
                "generatedBy": "AI Copilot 草稿；管委會尚未確認指派",
                "serviceContext": "DUSKIN 公開服務情境；履約夥伴與方案資料為競賽建置",
            }
            cursor = connection.execute(
                """INSERT INTO joint_service_campaigns
                (community_id,title,service_id,status,demand_json,draft_json,proposals_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                ("community-sunshine-demo", draft["title"], "service-aircon", PROPOSAL_REVIEW,
                 json.dumps(_hero_demand(), ensure_ascii=False), json.dumps(draft, ensure_ascii=False),
                 json.dumps(_hero_proposals(), ensure_ascii=False), now, now),
            )
            connection.execute(
                "INSERT INTO joint_service_events (campaign_id,event_type,actor,detail,occurred_at) VALUES (?,?,?,?,?)",
                (int(cursor.lastrowid), "joint_service.proposals_ready", "AI Copilot",
                 "已彙整 18 戶需求並產生兩案比較草稿", now),
            )

    def _record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        events = connection.execute(
            "SELECT event_type,actor,detail,occurred_at FROM joint_service_events WHERE campaign_id=? ORDER BY id",
            (row["id"],),
        ).fetchall()
        proposals = json.loads(row["proposals_json"])
        selected = next((item for item in proposals if item["id"] == row["selected_proposal_id"]), None)
        return {
            "id": row["id"], "communityId": row["community_id"], "title": row["title"],
            "serviceId": row["service_id"], "status": row["status"],
            "statusLabel": STATUS_LABELS[row["status"]], "demand": json.loads(row["demand_json"]),
            "draft": json.loads(row["draft_json"]), "proposals": proposals,
            "selectedProposalId": row["selected_proposal_id"], "selectedProposal": selected,
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
            "events": [{"type": event["event_type"], "actor": event["actor"], "detail": event["detail"],
                        "occurredAt": event["occurred_at"]} for event in events],
            "dataNotice": "需求、時段、報價與評分為競賽建置資料，非品牌即時報價。",
        }

    def list_campaigns(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM joint_service_campaigns ORDER BY id DESC").fetchall()
            return [self._record(connection, row) for row in rows]

    def list_for_resident(self, *, account_id: str) -> list[dict]:
        household_hash = hashlib.sha256(f"joint-service:{account_id}".encode()).hexdigest()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM joint_service_campaigns ORDER BY id DESC").fetchall()
            records: list[dict] = []
            for row in rows:
                record = self._record(connection, row)
                signal = connection.execute(
                    """SELECT units,equipment,preferred_slot,special_requirement,consent_version,
                              COALESCE(consented_at, joined_at) AS consented_at
                       FROM joint_service_signals WHERE campaign_id=? AND household_hash=?""",
                    (row["id"], household_hash),
                ).fetchone()
                record["myParticipation"] = None if signal is None else {
                    "units": signal["units"], "equipment": signal["equipment"],
                    "preferredSlot": signal["preferred_slot"],
                    "specialRequirement": signal["special_requirement"],
                    "consentVersion": signal["consent_version"], "consentedAt": signal["consented_at"],
                }
                records.append(record)
            return records

    def get_campaign(self, campaign_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM joint_service_campaigns WHERE id=?", (campaign_id,)).fetchone()
            return None if row is None else self._record(connection, row)

    def create_draft(self, *, title: str, service_id: str, created_by: str | None = None) -> dict:
        if not title.strip():
            raise JointServiceError("聯合服務名稱不可空白")
        now = self._timestamp()
        draft = {"title": title.strip(), "generatedBy": "AI Copilot 草稿；需管委會確認後發布"}
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO joint_service_campaigns
                (community_id,title,service_id,status,demand_json,draft_json,proposals_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                ("community-sunshine-demo", title.strip(), service_id, DRAFT,
                 json.dumps({"householdCount": 0, "unitCount": 0, "source": "resident_input"}),
                 json.dumps(draft, ensure_ascii=False), "[]", now, now),
            )
            campaign_id = int(cursor.lastrowid)
            connection.execute(
                "INSERT INTO joint_service_events (campaign_id,event_type,actor,detail,occurred_at) VALUES (?,?,?,?,?)",
                (campaign_id, "joint_service.draft_created", created_by or "社區管理者", title.strip(), now),
            )
        result = self.get_campaign(campaign_id)
        assert result is not None
        return result

    def _transition(self, campaign_id: int, *, expected: str, target: str, actor: str, event: str, detail: str) -> dict:
        now = self._timestamp()
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE joint_service_campaigns SET status=?,updated_at=? WHERE id=? AND status=?",
                (target, now, campaign_id, expected),
            ).rowcount
            if not changed:
                row = connection.execute("SELECT status FROM joint_service_campaigns WHERE id=?", (campaign_id,)).fetchone()
                if row is None:
                    raise JointServiceError(f"查無聯合服務 {campaign_id}")
                raise JointServiceError(f"目前為「{STATUS_LABELS[row['status']]}」，不能執行這項操作")
            connection.execute(
                "INSERT INTO joint_service_events (campaign_id,event_type,actor,detail,occurred_at) VALUES (?,?,?,?,?)",
                (campaign_id, event, actor, detail, now),
            )
        result = self.get_campaign(campaign_id)
        assert result is not None
        return result

    def publish(self, campaign_id: int, *, actor: str) -> dict:
        return self._transition(campaign_id, expected=DRAFT, target=COLLECTING, actor=actor,
                                event="joint_service.published", detail="開始向住戶募集匿名需求")

    def join(self, campaign_id: int, *, account_id: str, units: int, equipment: str,
             preferred_slot: str, special_requirement: str | None = None) -> dict:
        if units < 1:
            raise JointServiceError("設備台數至少 1 台")
        household_hash = hashlib.sha256(f"joint-service:{account_id}".encode()).hexdigest()
        now = self._timestamp()
        with self._connect() as connection:
            row = connection.execute("SELECT status FROM joint_service_campaigns WHERE id=?", (campaign_id,)).fetchone()
            if row is None:
                raise JointServiceError(f"查無聯合服務 {campaign_id}")
            if row["status"] != COLLECTING:
                raise JointServiceError("這項聯合服務目前沒有募集需求")
            connection.execute(
                """INSERT INTO joint_service_signals
                (campaign_id,household_hash,units,equipment,preferred_slot,special_requirement,joined_at,
                 consent_version,consented_at)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(campaign_id,household_hash) DO UPDATE SET
                units=excluded.units,equipment=excluded.equipment,preferred_slot=excluded.preferred_slot,
                special_requirement=excluded.special_requirement,joined_at=excluded.joined_at,
                consent_version=excluded.consent_version,consented_at=excluded.consented_at""",
                (campaign_id, household_hash, units, equipment.strip(), preferred_slot.strip(),
                 (special_requirement or "").strip() or None, now, "joint-demand-v1", now),
            )
            signals = connection.execute(
                "SELECT units,equipment,preferred_slot,special_requirement FROM joint_service_signals WHERE campaign_id=?",
                (campaign_id,),
            ).fetchall()
            equipment_counts: dict[str, int] = {}
            slot_counts: dict[str, int] = {}
            requirements: list[str] = []
            for signal in signals:
                equipment_counts[signal["equipment"]] = equipment_counts.get(signal["equipment"], 0) + signal["units"]
                slot_counts[signal["preferred_slot"]] = slot_counts.get(signal["preferred_slot"], 0) + 1
                if signal["special_requirement"]:
                    requirements.append(signal["special_requirement"])
            demand = {
                "householdCount": len(signals), "unitCount": sum(item["units"] for item in signals),
                "equipment": [{"label": key, "count": value} for key, value in equipment_counts.items()],
                "timePreferences": [{"label": key, "households": value} for key, value in slot_counts.items()],
                "specialRequirements": requirements,
                "privacy": "以匿名住戶雜湊去重；方案比較不含姓名、電話與門牌",
                "source": "resident_input", "sourceLabel": "住戶確認後的匿名需求",
            }
            connection.execute(
                "UPDATE joint_service_campaigns SET demand_json=?,updated_at=? WHERE id=? AND status=?",
                (json.dumps(demand, ensure_ascii=False), now, campaign_id, COLLECTING),
            )
        result = self.get_campaign(campaign_id)
        assert result is not None
        return result

    def prepare_proposals(self, campaign_id: int, *, actor: str) -> dict:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise JointServiceError(f"查無聯合服務 {campaign_id}")
        if campaign["demand"].get("householdCount", 0) < 1:
            raise JointServiceError("至少要有一戶需求才能產生合作方案")
        now = self._timestamp()
        proposals = _hero_proposals(campaign["demand"]["unitCount"])
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE joint_service_campaigns SET status=?,proposals_json=?,updated_at=? WHERE id=? AND status=?",
                (PROPOSAL_REVIEW, json.dumps(proposals, ensure_ascii=False), now, campaign_id, COLLECTING),
            ).rowcount
            if not changed:
                raise JointServiceError("目前狀態無法截止需求募集")
            connection.execute(
                "INSERT INTO joint_service_events (campaign_id,event_type,actor,detail,occurred_at) VALUES (?,?,?,?,?)",
                (campaign_id, "joint_service.proposals_ready", actor,
                 f"已彙整 {campaign['demand']['householdCount']} 戶需求並產生兩案比較", now),
            )
        result = self.get_campaign(campaign_id)
        assert result is not None
        return result

    def assign(self, campaign_id: int, *, proposal_id: str, actor: str) -> dict:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise JointServiceError(f"查無聯合服務 {campaign_id}")
        proposal = next((item for item in campaign["proposals"] if item["id"] == proposal_id), None)
        if proposal is None:
            raise JointServiceError("查無指定方案")
        now = self._timestamp()
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE joint_service_campaigns SET status=?,selected_proposal_id=?,updated_at=? WHERE id=? AND status=?",
                (ASSIGNED, proposal_id, now, campaign_id, PROPOSAL_REVIEW),
            ).rowcount
            if not changed:
                raise JointServiceError("此聯合服務已完成方案決策，不能重複指派")
            connection.execute(
                "INSERT INTO joint_service_events (campaign_id,event_type,actor,detail,occurred_at) VALUES (?,?,?,?,?)",
                (campaign_id, "joint_service.assigned", actor,
                 f"指派 {proposal['vendorName']}，總額 NT${proposal['total']:,}", now),
            )
        result = self.get_campaign(campaign_id)
        assert result is not None
        return result

    def list_assigned(self, *, vendor_id: str | None = None) -> list[dict]:
        records = [item for item in self.list_campaigns() if item["status"] in {ASSIGNED, IN_PROGRESS, COMPLETED}]
        if vendor_id:
            records = [item for item in records if item["selectedProposal"] and item["selectedProposal"]["vendorId"] == vendor_id]
        return records

    def _require_vendor(self, campaign_id: int, vendor_id: str) -> None:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            raise JointServiceError(f"查無聯合服務 {campaign_id}")
        selected = campaign["selectedProposal"]
        if not selected or selected["vendorId"] != vendor_id:
            raise JointServiceError("這張聯合服務工單沒有指派給目前廠商")

    def start(self, campaign_id: int, *, vendor_id: str, actor: str) -> dict:
        self._require_vendor(campaign_id, vendor_id)
        return self._transition(campaign_id, expected=ASSIGNED, target=IN_PROGRESS, actor=actor,
                                event="joint_service.started", detail="廠商已回報開工")

    def complete(self, campaign_id: int, *, vendor_id: str, actor: str, note: str) -> dict:
        self._require_vendor(campaign_id, vendor_id)
        if not note.strip():
            raise JointServiceError("完工回報需填寫說明")
        return self._transition(campaign_id, expected=IN_PROGRESS, target=COMPLETED, actor=actor,
                                event="joint_service.completed", detail=note.strip())
