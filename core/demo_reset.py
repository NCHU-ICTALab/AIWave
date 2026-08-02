"""Scoped, repeatable reset for competition DemoWorkspaces.

Member reset is intentionally limited to the active member workspace.  Only a
platform operator may reset every fixed persona in a DemoWorkspace and the
independent fake upstream.  Authentication is handled by the Platform API; this
service never accepts a caller-provided role.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from core.access import SqliteAccessRepository
from core.communities import SqliteCommunityRepository
from core.data.personas import DEMO_HOUSEHOLDS
from core.groups import SqliteGroupRepository
from core.points import SqlitePointsLedger


LEGACY_MUTABLE_TABLES = (
    "support_events", "support_tickets", "life_task_items", "life_tasks",
    "platform_order_events", "platform_orders", "inquiry_events", "inquiries",
    "group_buy_joins", "group_buy_campaigns", "joint_service_signals",
    "joint_service_events", "joint_service_campaigns", "recommendation_feedback",
    "reminders", "stock_watches", "group_members", "member_groups",
)


class DemoResetService:
    def __init__(
        self,
        database: str | Path,
        *,
        access: SqliteAccessRepository,
        points: SqlitePointsLedger,
        now: Callable[[], datetime] | None = None,
        session_store: object | None = None,
        partner_fake_url: str = "",
        partner_control_key: str = "",
        retail_fake_url: str = "",
        retail_control_key: str = "",
        timeout_seconds: float = 2.0,
        catalog_sync: object | None = None,
    ) -> None:
        self.database = Path(database)
        self.access = access
        self.points = points
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.session_store = session_store
        self.partner_fake_url = partner_fake_url.rstrip("/")
        self.partner_control_key = partner_control_key
        self.retail_fake_url = retail_fake_url.rstrip("/")
        self.retail_control_key = retail_control_key
        self.timeout_seconds = timeout_seconds
        self.catalog_sync = catalog_sync

    def _timestamp(self) -> str:
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.isoformat()

    @staticmethod
    def _existing_tables(connection: sqlite3.Connection) -> set[str]:
        return {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            ).fetchall()
        }

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()}

    @staticmethod
    def _delete_ids(connection: sqlite3.Connection, table: str, column: str, ids: list[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        connection.execute(f'DELETE FROM "{table}" WHERE "{column}" IN ({placeholders})', ids)

    def _seed_points(self, *, demo_workspace_id: str, account_ids: list[str]) -> None:
        # DEMO_HOUSEHOLDS 而不是 PERSONAS:王小明也要拿到初始點數,否則按過
        # 平台的 Demo 重設之後,主展示住戶的點數會掉回 0 直到重啟。
        persona_ids = {persona.id for persona in DEMO_HOUSEHOLDS}
        for account_id in account_ids:
            if account_id not in persona_ids:
                continue
            self.points.post(
                demo_workspace_id=demo_workspace_id,
                workspace_id=f"workspace-personal-{account_id}",
                account_id=account_id,
                entry_type="earn",
                amount=180,
                description="Demo 初始 OPENPOINT 情境點數",
                reference_type="seed",
                reference_id="platform-demo-v2",
                idempotency_key=f"seed:points:{account_id}:v2",
            )

    def _clear_platform_scope(
        self,
        connection: sqlite3.Connection,
        *,
        demo_workspace_id: str,
        workspace_id: str | None,
        account_id: str | None,
    ) -> None:
        """Delete Platform-core rows, removing child rows before their parents."""
        scope_sql = "demo_workspace_id=?"
        values: list[Any] = [demo_workspace_id]
        if workspace_id is not None:
            scope_sql += " AND workspace_id=?"
            values.append(workspace_id)
        if account_id is not None:
            scope_sql += " AND account_id=?"
            values.append(account_id)

        booking_ids = [
            row[0] for row in connection.execute(
                f"SELECT id FROM bookings WHERE {scope_sql}", values,
            ).fetchall()
        ] if "bookings" in self._existing_tables(connection) else []
        order_ids = [
            row[0] for row in connection.execute(
                f"SELECT id FROM commerce_orders WHERE {scope_sql}", values,
            ).fetchall()
        ] if "commerce_orders" in self._existing_tables(connection) else []
        payment_ids = [
            row[0] for row in connection.execute(
                f"SELECT id FROM demo_payments WHERE {scope_sql}", values,
            ).fetchall()
        ] if "demo_payments" in self._existing_tables(connection) else []
        event_ids = [
            row[0] for row in connection.execute(
                f"SELECT id FROM calendar_events WHERE {scope_sql}", values,
            ).fetchall()
        ] if "calendar_events" in self._existing_tables(connection) else []
        v4_package_ids = [
            row[0] for row in connection.execute(
                f"SELECT id FROM v4_life_task_packages WHERE {scope_sql}", values,
            ).fetchall()
        ] if "v4_life_task_packages" in self._existing_tables(connection) else []

        existing = self._existing_tables(connection)
        for table, column, ids in (
            ("booking_reschedule_requests", "booking_id", booking_ids),
            ("provider_booking_links", "local_booking_id", booking_ids),
            ("commerce_order_items", "order_id", order_ids),
            ("demo_payment_events", "payment_id", payment_ids),
            ("calendar_event_exceptions", "event_id", event_ids),
            ("v4_task_package_item_events", "package_id", v4_package_ids),
            ("v4_life_task_package_items", "package_id", v4_package_ids),
        ):
            if table in existing:
                self._delete_ids(connection, table, column, ids)
        if "status_events" in existing:
            subject_ids = booking_ids + order_ids
            self._delete_ids(connection, "status_events", "subject_id", subject_ids)

        for table in (
            "task_drafts", "points_ledger", "demo_payments", "notifications",
            "calendar_events", "bookings", "commerce_orders",
            "v4_life_task_packages", "v4_life_context_events", "v4_care_candidates",
            "v4_care_messages", "v4_life_outcomes", "v4_achievement_unlocks",
            "v4_demo_reward_entries", "v4_provider_success_fees",
        ):
            if table in existing and "demo_workspace_id" in self._columns(connection, table):
                columns = self._columns(connection, table)
                table_scope = "demo_workspace_id=?"
                table_values: list[Any] = [demo_workspace_id]
                if workspace_id is not None and "workspace_id" in columns:
                    table_scope += " AND workspace_id=?"
                    table_values.append(workspace_id)
                if account_id is not None and "account_id" in columns:
                    table_scope += " AND account_id=?"
                    table_values.append(account_id)
                connection.execute(f'DELETE FROM "{table}" WHERE {table_scope}', table_values)
        if "v4_demo_reward_campaigns" in existing and "v4_demo_reward_entries" in existing:
            connection.execute(
                """UPDATE v4_demo_reward_campaigns SET issued_amount=(
                     SELECT COALESCE(SUM(CASE WHEN kind='grant' THEN amount ELSE -amount END),0)
                     FROM v4_demo_reward_entries WHERE campaign_id=v4_demo_reward_campaigns.id
                   ), updated_at=?""",
                (self._timestamp(),),
            )
        if account_id is not None and "notification_preferences" in existing:
            connection.execute("DELETE FROM notification_preferences WHERE account_id=?", (account_id,))

    def _clear_legacy_for_account(self, connection: sqlite3.Connection, account_id: str) -> None:
        existing = self._existing_tables(connection)
        for table in LEGACY_MUTABLE_TABLES:
            if table not in existing:
                continue
            columns = self._columns(connection, table)
            account_column = next(
                (candidate for candidate in ("account_id", "created_by", "owner_account_id") if candidate in columns),
                None,
            )
            if account_column:
                connection.execute(f'DELETE FROM "{table}" WHERE "{account_column}"=?', (account_id,))

    def _reset_sharing_models(self, connection: sqlite3.Connection) -> None:
        existing = self._existing_tables(connection)
        # Dynamic access memberships must be removed before their domain rows are reseeded.
        if "api_credentials" in existing:
            connection.execute(
                """DELETE FROM api_credentials WHERE membership_id LIKE 'membership-group-%'
                   OR membership_id LIKE 'membership-community-community-%'""",
            )
        if "role_memberships" in existing:
            connection.execute(
                """DELETE FROM role_memberships WHERE id LIKE 'membership-group-%'
                   OR id LIKE 'membership-community-community-%'""",
            )
        if "workspaces" in existing:
            connection.execute("DELETE FROM workspaces WHERE id LIKE 'workspace-group-%'")
            connection.execute(
                """DELETE FROM workspaces WHERE kind='community'
                   AND id NOT IN ('workspace-community-sunshine','workspace-community-greenfield')""",
            )
        for table in (
            "sharing_group_operations", "sharing_group_memberships", "sharing_groups",
            "agent_sessions", "execution_grants",
            "community_announcements",
            "community_invite_joins", "community_invites", "community_join_requests",
            "community_memberships", "communities",
        ):
            if table in existing:
                connection.execute(f'DELETE FROM "{table}"')

    def reset_member(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict[str, Any]:
        with sqlite3.connect(self.database) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            self._clear_platform_scope(
                connection, demo_workspace_id=demo_workspace_id,
                workspace_id=workspace_id, account_id=account_id,
            )
            self._clear_legacy_for_account(connection, account_id)
            existing = self._existing_tables(connection)
            for table in ("agent_sessions", "execution_grants"):
                if table in existing:
                    connection.execute(f'DELETE FROM "{table}" WHERE account_id=?', (account_id,))
            connection.commit()
        clear_sessions = getattr(self.session_store, "clear", None)
        if callable(clear_sessions):
            clear_sessions(account_id)
        self._seed_points(demo_workspace_id=demo_workspace_id, account_ids=[account_id])
        return {
            "status": "ready", "scope": "workspace", "resetAt": self._timestamp(),
            "demoWorkspaceId": demo_workspace_id, "workspaceId": workspace_id,
            "upstreams": {"partner": "not_applicable", "retail": "not_applicable"},
        }

    def _reset_upstream(self, *, base_url: str, control_key: str) -> dict[str, Any]:
        if not base_url:
            return {"status": "disabled", "seedVersion": None}
        if not control_key:
            return {"status": "not_configured", "seedVersion": None}
        try:
            response = httpx.post(
                f"{base_url}/__fake__/reset",
                headers={"X-Fake-Control-Key": control_key},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload)
            return {"status": "reset", "seedVersion": data.get("seedVersion")}
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return {"status": "unavailable", "seedVersion": None}

    def reset_demo(self, *, demo_workspace_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.database) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            self._clear_platform_scope(
                connection, demo_workspace_id=demo_workspace_id,
                workspace_id=None, account_id=None,
            )
            existing = self._existing_tables(connection)
            for table in LEGACY_MUTABLE_TABLES:
                if table in existing:
                    connection.execute(f'DELETE FROM "{table}"')
            self._reset_sharing_models(connection)
            if "notification_preferences" in existing:
                connection.execute("DELETE FROM notification_preferences")
            for table in (
                "provider_workbench_operations", "provider_workbench_bookings",
                "provider_workbench_state",
            ):
                if table in existing:
                    connection.execute(f'DELETE FROM "{table}"')
            connection.commit()

        # Constructors own fixed seed contracts, avoiding a second copy in reset code.
        SqliteGroupRepository(self.database, now=self._now, seed=True, access=self.access)
        SqliteCommunityRepository(self.database, now=self._now, seed=True, access=self.access)
        self.access.seed_demo()
        self._seed_points(
            demo_workspace_id=demo_workspace_id,
            account_ids=[persona.id for persona in DEMO_HOUSEHOLDS],
        )
        clear_sessions = getattr(self.session_store, "clear", None)
        if callable(clear_sessions):
            clear_sessions()
        reset_record = self.access.mark_demo_reset(demo_workspace_id)
        upstreams = {
            "partner": self._reset_upstream(
                base_url=self.partner_fake_url, control_key=self.partner_control_key,
            ),
            "retail": self._reset_upstream(
                base_url=self.retail_fake_url, control_key=self.retail_control_key,
            ),
        }
        # 協調 reset:上游 seed 回捲後,平台目錄投影要跟著重新同步,
        # 避免留下已被消耗的 slot 或不一致的 seed version。
        catalog_result: dict[str, Any] | None = None
        sync_all = getattr(self.catalog_sync, "sync_all", None)
        if callable(sync_all):
            try:
                catalog_result = sync_all()
            except Exception as exc:  # noqa: BLE001 - 誠實回報,不擋 reset
                catalog_result = {"status": "failed", "error": str(exc)}
        incomplete = {"not_configured", "unavailable"}
        return {
            "status": "partial" if any(item["status"] in incomplete for item in upstreams.values()) else "ready",
            "catalog": catalog_result,
            "scope": "demo_workspace", "resetAt": self._timestamp(),
            "demoWorkspaceId": demo_workspace_id,
            "seedVersion": reset_record["seedVersion"],
            "resetVersion": reset_record["resetVersion"],
            "upstreams": upstreams,
        }
