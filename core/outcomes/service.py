"""Completion, Demo reward, achievement, and provider-fee projections.

This module consumes an already-authoritative fulfillment status transition.
It does not decide whether a booking/order may transition.  Member-facing
projections intentionally omit provider fees; the fee table is exposed only
through the provider settlement projection.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.points import PointsError, SqlitePointsLedger


class OutcomeError(ValueError):
    pass


COMPLETION_STATES = {"completed", "delivered"}
REVERSAL_STATES = {"cancelled", "failed", "rejected", "exception", "refunded"}


class SqliteOutcomeProjectionService:
    """Idempotent projections for the competition Demo commercial loop."""

    CAMPAIGN_ID = "demo-completion-reward-2026"
    REWARD_AMOUNT = 20
    CAMPAIGN_BUDGET = 500
    MEMBER_CAP = 100
    FEE_RATE_BPS = 500  # explicitly Demo-only 5%; not an official platform fee

    def __init__(
        self,
        path: str | Path,
        *,
        points: SqlitePointsLedger | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.points = points
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
                CREATE TABLE IF NOT EXISTS v4_life_outcomes (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    package_id TEXT,
                    subject_type TEXT NOT NULL CHECK(subject_type IN ('booking','commerce_order')),
                    subject_id TEXT NOT NULL,
                    provider_id TEXT,
                    amount INTEGER NOT NULL CHECK(amount>=0),
                    status TEXT NOT NULL CHECK(status IN ('completed','reversal_pending','reversed')),
                    summary TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,subject_type,subject_id)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_life_outcomes_owner
                    ON v4_life_outcomes(demo_workspace_id,workspace_id,account_id,created_at);
                CREATE TABLE IF NOT EXISTS v4_achievement_unlocks (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    achievement_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    outcome_id TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,account_id,achievement_key)
                );
                CREATE TABLE IF NOT EXISTS v4_demo_reward_campaigns (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','paused','exhausted')),
                    budget INTEGER NOT NULL CHECK(budget>=0),
                    issued_amount INTEGER NOT NULL DEFAULT 0,
                    member_cap INTEGER NOT NULL CHECK(member_cap>=0),
                    reward_amount INTEGER NOT NULL CHECK(reward_amount>=0),
                    data_source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS v4_demo_reward_entries (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('grant','reversal')),
                    amount INTEGER NOT NULL CHECK(amount>0),
                    points_entry_id TEXT,
                    reverses_entry_id TEXT,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(campaign_id,demo_workspace_id,idempotency_key),
                    UNIQUE(reverses_entry_id)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_demo_rewards_owner
                    ON v4_demo_reward_entries(demo_workspace_id,workspace_id,account_id,created_at);
                CREATE TABLE IF NOT EXISTS v4_provider_success_fees (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('charge','reversal')),
                    amount INTEGER NOT NULL CHECK(amount>=0),
                    rate_bps INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    reversal_of TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,subject_type,subject_id,kind,event_id),
                    UNIQUE(reversal_of)
                );
                CREATE INDEX IF NOT EXISTS ix_v4_provider_fees_provider
                    ON v4_provider_success_fees(demo_workspace_id,provider_id,created_at);
                """
            )
            timestamp = self._timestamp()
            connection.execute(
                """INSERT OR IGNORE INTO v4_demo_reward_campaigns
                   (id,title,status,budget,issued_amount,member_cap,reward_amount,data_source,created_at,updated_at)
                   VALUES (?,?,?, ?,0,?,?,?, ?,?)""",
                (
                    self.CAMPAIGN_ID, "Demo 完成回饋（非正式 OPENPOINT 活動）", "active",
                    self.CAMPAIGN_BUDGET, self.MEMBER_CAP, self.REWARD_AMOUNT,
                    "competition_demo_rule", timestamp, timestamp,
                ),
            )

    @staticmethod
    def _outcome(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "packageId": row["package_id"], "subjectType": row["subject_type"],
            "subjectId": row["subject_id"], "providerId": row["provider_id"], "amount": row["amount"],
            "status": row["status"], "summary": row["summary"], "eventId": row["event_id"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _reward(row: sqlite3.Row) -> dict[str, Any]:
        signed = int(row["amount"]) if row["kind"] == "grant" else -int(row["amount"])
        return {
            "id": row["id"], "campaignId": row["campaign_id"], "subjectType": row["subject_type"],
            "subjectId": row["subject_id"], "kind": row["kind"], "amount": signed,
            "pointsEntryId": row["points_entry_id"], "reversesEntryId": row["reverses_entry_id"],
            "idempotencyKey": row["idempotency_key"], "createdAt": row["created_at"],
        }

    def _owner_values(self, owner: Mapping[str, str]) -> tuple[str, str, str]:
        return owner["demo_workspace_id"], owner["workspace_id"], owner["account_id"]

    def project_status(
        self,
        *,
        owner: Mapping[str, str],
        subject_type: str,
        subject_id: str,
        provider_id: str,
        status: str,
        event_id: str,
        amount: int = 0,
        summary: str = "",
        package_id: str | None = None,
    ) -> dict[str, Any]:
        if subject_type not in {"booking", "commerce_order"} or not subject_id.strip() or not event_id.strip():
            raise OutcomeError("成果投影主體或事件 id 不合法")
        if amount < 0:
            raise OutcomeError("成果金額不可為負")
        if status in COMPLETION_STATES:
            return self._complete(
                owner=owner, subject_type=subject_type, subject_id=subject_id,
                provider_id=provider_id, event_id=event_id, amount=amount,
                summary=summary, package_id=package_id,
            )
        if status in REVERSAL_STATES:
            return self._reverse(
                owner=owner, subject_type=subject_type, subject_id=subject_id, event_id=event_id,
            )
        return {
            "status": "ignored", "subjectType": subject_type, "subjectId": subject_id,
            "reason": "只有 completed 或 delivered 才會產生完成投影",
        }

    def _complete(
        self,
        *,
        owner: Mapping[str, str],
        subject_type: str,
        subject_id: str,
        provider_id: str,
        event_id: str,
        amount: int,
        summary: str,
        package_id: str | None,
    ) -> dict[str, Any]:
        timestamp = self._timestamp()
        owner_values = self._owner_values(owner)
        reward_to_post: dict[str, Any] | None = None
        with self._connect() as connection:
            existing = connection.execute(
                """SELECT * FROM v4_life_outcomes WHERE demo_workspace_id=? AND subject_type=? AND subject_id=?""",
                (owner_values[0], subject_type, subject_id),
            ).fetchone()
            if existing is not None:
                return self._projection(connection, existing, idempotent=True)
            outcome_id = f"outcome-{uuid4().hex[:16]}"
            connection.execute(
                """INSERT INTO v4_life_outcomes
                   (id,demo_workspace_id,workspace_id,account_id,package_id,subject_type,subject_id,
                    provider_id,amount,status,summary,event_id,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,'completed',?,?,?,?)""",
                (
                    outcome_id, *owner_values, package_id, subject_type, subject_id, provider_id,
                    amount, summary or f"{subject_type}:{subject_id} 已完成", event_id, timestamp, timestamp,
                ),
            )
            achievement = connection.execute(
                """INSERT OR IGNORE INTO v4_achievement_unlocks
                   (id,demo_workspace_id,workspace_id,account_id,achievement_key,title,outcome_id,unlocked_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    f"achievement-{uuid4().hex[:16]}", owner_values[0], owner_values[1], owner_values[2],
                    "first_life_outcome", "完成一項生活任務", outcome_id, timestamp,
                ),
            )
            campaign = connection.execute(
                "SELECT * FROM v4_demo_reward_campaigns WHERE id=?", (self.CAMPAIGN_ID,)
            ).fetchone()
            if campaign is None:
                raise OutcomeError("Demo reward campaign 未初始化")
            member_issued = connection.execute(
                """SELECT COALESCE(SUM(CASE WHEN kind='grant' THEN amount ELSE -amount END),0)
                   AS issued FROM v4_demo_reward_entries
                   WHERE campaign_id=? AND demo_workspace_id=? AND workspace_id=? AND account_id=?""",
                (self.CAMPAIGN_ID, *owner_values),
            ).fetchone()["issued"]
            can_reward = (
                campaign["status"] == "active"
                and int(campaign["issued_amount"]) + int(campaign["reward_amount"]) <= int(campaign["budget"])
                and int(member_issued) + int(campaign["reward_amount"]) <= int(campaign["member_cap"])
            )
            if can_reward:
                reward_id = f"reward-{uuid4().hex[:16]}"
                connection.execute(
                    """INSERT INTO v4_demo_reward_entries
                       (id,campaign_id,demo_workspace_id,workspace_id,account_id,subject_type,subject_id,
                        kind,amount,idempotency_key,created_at)
                       VALUES (?,?,?,?,?,?,?,'grant',?,?,?)""",
                    (
                        reward_id, self.CAMPAIGN_ID, *owner_values, subject_type, subject_id,
                        int(campaign["reward_amount"]), f"reward:{self.CAMPAIGN_ID}:{subject_type}:{subject_id}", timestamp,
                    ),
                )
                connection.execute(
                    "UPDATE v4_demo_reward_campaigns SET issued_amount=issued_amount+?,updated_at=? WHERE id=?",
                    (int(campaign["reward_amount"]), timestamp, self.CAMPAIGN_ID),
                )
                reward_to_post = {
                    "id": reward_id, "amount": int(campaign["reward_amount"]),
                    "idempotencyKey": f"reward:{self.CAMPAIGN_ID}:{subject_type}:{subject_id}",
                }
            fee_amount = (amount * self.FEE_RATE_BPS) // 10_000 if provider_id and amount else 0
            if fee_amount > 0:
                connection.execute(
                    """INSERT OR IGNORE INTO v4_provider_success_fees
                       (id,demo_workspace_id,workspace_id,subject_type,subject_id,provider_id,kind,amount,rate_bps,event_id,created_at)
                       VALUES (?,?,?,?,?,?, 'charge',?,?,?,?)""",
                    (
                        f"fee-{uuid4().hex[:16]}", owner_values[0], owner_values[1], subject_type, subject_id,
                        provider_id, fee_amount, self.FEE_RATE_BPS, event_id, timestamp,
                    ),
                )
            outcome = connection.execute("SELECT * FROM v4_life_outcomes WHERE id=?", (outcome_id,)).fetchone()
            result = self._projection(connection, outcome, idempotent=False)
            result["achievementUnlocked"] = achievement.rowcount == 1
            result["rewardPending"] = reward_to_post is not None
        if reward_to_post is not None and self.points is not None:
            try:
                entry = self.points.post(
                    demo_workspace_id=owner_values[0], workspace_id=owner_values[1], account_id=owner_values[2],
                    entry_type="earn", amount=reward_to_post["amount"], description="Demo 完成回饋（非正式活動）",
                    reference_type="life_outcome", reference_id=result["outcome"]["id"],
                    idempotency_key=reward_to_post["idempotencyKey"],
                )
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE v4_demo_reward_entries SET points_entry_id=? WHERE id=?",
                        (entry["id"], reward_to_post["id"]),
                    )
                result["rewardPending"] = False
            except PointsError as exc:
                result["rewardWarning"] = str(exc)
        result["rewards"] = self.list_rewards(owner=owner)
        result["dataSource"] = "competition_demo_projection"
        return result

    def _projection(self, connection: sqlite3.Connection, outcome: sqlite3.Row, *, idempotent: bool) -> dict[str, Any]:
        return {
            "outcome": self._outcome(outcome),
            "idempotentReplay": idempotent,
            "dataSource": "competition_demo_projection",
        }

    def _reverse(
        self,
        *,
        owner: Mapping[str, str],
        subject_type: str,
        subject_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        owner_values = self._owner_values(owner)
        timestamp = self._timestamp()
        reward_candidates: list[sqlite3.Row] = []
        fee_candidates: list[sqlite3.Row] = []
        with self._connect() as connection:
            outcome = connection.execute(
                """SELECT * FROM v4_life_outcomes WHERE demo_workspace_id=? AND subject_type=? AND subject_id=?""",
                (owner_values[0], subject_type, subject_id),
            ).fetchone()
            if outcome is None:
                return {"status": "ignored", "reason": "此交易尚未有完成成果，不需沖銷"}
            if outcome["status"] == "reversed":
                return {"outcome": self._outcome(outcome), "idempotentReplay": True, "rewards": self.list_rewards(owner=owner)}
            reward_candidates = connection.execute(
                """SELECT * FROM v4_demo_reward_entries grant_entry
                   WHERE grant_entry.demo_workspace_id=? AND grant_entry.subject_type=? AND grant_entry.subject_id=?
                     AND grant_entry.kind='grant'
                     AND NOT EXISTS (
                       SELECT 1 FROM v4_demo_reward_entries reversal
                       WHERE reversal.reverses_entry_id=grant_entry.id
                     )""",
                (owner_values[0], subject_type, subject_id),
            ).fetchall()
            fee_candidates = connection.execute(
                """SELECT * FROM v4_provider_success_fees charge
                   WHERE charge.demo_workspace_id=? AND charge.subject_type=? AND charge.subject_id=?
                     AND charge.kind='charge'
                     AND NOT EXISTS (
                       SELECT 1 FROM v4_provider_success_fees reversal
                       WHERE reversal.reversal_of=charge.id
                     )""",
                (owner_values[0], subject_type, subject_id),
            ).fetchall()
            connection.execute(
                "UPDATE v4_life_outcomes SET status='reversal_pending',updated_at=? WHERE id=?",
                (timestamp, outcome["id"]),
            )
        warnings: list[str] = []
        for reward in reward_candidates:
            points_entry_id = reward["points_entry_id"]
            if self.points is not None and points_entry_id:
                try:
                    self.points.post(
                        demo_workspace_id=owner_values[0], workspace_id=owner_values[1], account_id=owner_values[2],
                        entry_type="reversal", amount=-int(reward["amount"]), description="Demo 完成回饋沖銷",
                        reference_type="life_outcome", reference_id=subject_id,
                        idempotency_key=f"reversal:reward:{reward['id']}", reverses_entry_id=points_entry_id,
                    )
                except PointsError as exc:
                    warnings.append(str(exc))
                    continue
            with self._connect() as connection:
                connection.execute(
                    """INSERT OR IGNORE INTO v4_demo_reward_entries
                       (id,campaign_id,demo_workspace_id,workspace_id,account_id,subject_type,subject_id,
                        kind,amount,reverses_entry_id,idempotency_key,created_at)
                       VALUES (?,?,?,?,?,?,?,'reversal',?,?,?,?)""",
                    (
                        f"reward-reversal-{uuid4().hex[:16]}", reward["campaign_id"], *owner_values,
                        subject_type, subject_id, int(reward["amount"]), reward["id"],
                        f"reversal:reward:{reward['id']}", timestamp,
                    ),
                )
        with self._connect() as connection:
            for fee in fee_candidates:
                connection.execute(
                    """INSERT OR IGNORE INTO v4_provider_success_fees
                       (id,demo_workspace_id,workspace_id,subject_type,subject_id,provider_id,kind,amount,rate_bps,event_id,reversal_of,created_at)
                       VALUES (?,?,?,?,?,?, 'reversal',?,?,?, ?,?)""",
                    (
                        f"fee-reversal-{uuid4().hex[:16]}", fee["demo_workspace_id"], fee["workspace_id"],
                        fee["subject_type"], fee["subject_id"], fee["provider_id"], fee["amount"],
                        fee["rate_bps"], event_id, fee["id"], timestamp,
                    ),
                )
            new_status = "reversal_pending" if warnings else "reversed"
            connection.execute(
                "UPDATE v4_life_outcomes SET status=?,updated_at=? WHERE id=?",
                (new_status, timestamp, outcome["id"]),
            )
            updated = connection.execute("SELECT * FROM v4_life_outcomes WHERE id=?", (outcome["id"],)).fetchone()
        result = {"outcome": self._outcome(updated), "idempotentReplay": False, "rewards": self.list_rewards(owner=owner)}
        if warnings:
            result["warnings"] = warnings
        return result

    def list_outcomes(self, *, owner: Mapping[str, str]) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM v4_life_outcomes
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=? ORDER BY created_at DESC""",
                self._owner_values(owner),
            ).fetchall()
            return [self._outcome(row) for row in rows]

    def list_achievements(self, *, owner: Mapping[str, str]) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT achievement_key,title,outcome_id,unlocked_at FROM v4_achievement_unlocks
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=? ORDER BY unlocked_at""",
                self._owner_values(owner),
            ).fetchall()
            return [{
                "key": row["achievement_key"], "title": row["title"],
                "outcomeId": row["outcome_id"], "unlockedAt": row["unlocked_at"],
            } for row in rows]

    def list_rewards(self, *, owner: Mapping[str, str]) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM v4_demo_reward_entries
                   WHERE demo_workspace_id=? AND workspace_id=? AND account_id=? ORDER BY created_at DESC""",
                self._owner_values(owner),
            ).fetchall()
            return [self._reward(row) for row in rows]

    def member_projection(self, *, owner: Mapping[str, str]) -> dict[str, Any]:
        return {
            "outcomes": self.list_outcomes(owner=owner),
            "achievements": self.list_achievements(owner=owner),
            "rewards": self.list_rewards(owner=owner),
            "note": "會員端只顯示自己的成果、成就與 Demo 回饋；Provider success fee 不在此顯示。",
        }

    def provider_settlement(self, *, demo_workspace_id: str, provider_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM v4_provider_success_fees
                   WHERE demo_workspace_id=? AND provider_id=? ORDER BY created_at""",
                (demo_workspace_id, provider_id),
            ).fetchall()
            fees = [{
                "id": row["id"], "subjectType": row["subject_type"], "subjectId": row["subject_id"],
                "kind": row["kind"], "amount": row["amount"], "rateBps": row["rate_bps"],
                "eventId": row["event_id"], "reversalOf": row["reversal_of"], "createdAt": row["created_at"],
            } for row in rows]
        net = sum(int(row["amount"]) if row["kind"] == "charge" else -int(row["amount"]) for row in rows)
        return {
            "providerId": provider_id, "fees": fees, "netAmount": net,
            "rateBps": self.FEE_RATE_BPS, "dataSource": "competition_demo_fee_projection",
            "officialRate": False,
        }
