from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.fulfillment import SqliteFulfillmentRepository

from .connector import ProviderConnector, ProviderConnectorError


class ProviderBookingError(RuntimeError):
    """A platform booking could not be synchronized with its provider."""

    def __init__(
        self,
        message: str,
        *,
        booking_id: str | None = None,
        state_unknown: bool = False,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.booking_id = booking_id
        self.state_unknown = state_unknown
        self.recoverable = recoverable


class ProviderBookingService:
    """Coordinates the local Booking aggregate with one ProviderConnector.

    A local booking is created first and becomes the stable external reference.  If a
    remote write times out, the same remote idempotency key is retained and a retry is
    safe.  The link table is deliberately separate from ``bookings`` so the domain
    aggregate does not acquire transport-specific nullable columns.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        fulfillment: SqliteFulfillmentRepository,
        connector: ProviderConnector | None = None,
        connectors: dict[str, ProviderConnector] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if connector is None and not connectors:
            raise ValueError("ProviderBookingService 需要至少一個 connector")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fulfillment = fulfillment
        self.connector = connector  # 單一 connector 的舊介面(測試/單廠商模式)
        self.connectors: dict[str, ProviderConnector] = dict(connectors or {})
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connector_for(self, provider_id: str | None) -> ProviderConnector:
        if provider_id and provider_id in self.connectors:
            return self.connectors[provider_id]
        if self.connector is not None:
            return self.connector
        raise ProviderBookingError(f"平台未設定 Provider connector:{provider_id}", recoverable=False)

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
                CREATE TABLE IF NOT EXISTS provider_booking_links (
                    local_booking_id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    external_booking_id TEXT,
                    external_version INTEGER,
                    sync_status TEXT NOT NULL CHECK(sync_status IN
                        ('pending','synced','failed','state_unknown')),
                    remote_idempotency_key TEXT NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,provider_id,remote_idempotency_key),
                    FOREIGN KEY(local_booking_id) REFERENCES bookings(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS ix_provider_booking_links_workspace
                    ON provider_booking_links(demo_workspace_id,provider_id,sync_status);
                """
            )

    @staticmethod
    def _link(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "localBookingId": row["local_booking_id"],
            "demoWorkspaceId": row["demo_workspace_id"],
            "providerId": row["provider_id"],
            "externalBookingId": row["external_booking_id"],
            "externalVersion": row["external_version"],
            "syncStatus": row["sync_status"],
            "lastError": row["last_error"],
            "updatedAt": row["updated_at"],
        }

    def _get_link(self, booking_id: str, *, demo_workspace_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM provider_booking_links
                   WHERE local_booking_id=? AND demo_workspace_id=?""",
                (booking_id, demo_workspace_id),
            ).fetchone()
        if row is None:
            raise ProviderBookingError("預約尚未建立 Provider 同步紀錄", booking_id=booking_id)
        return self._link(row)

    def _ensure_link(self, booking: dict[str, Any]) -> dict[str, Any]:
        timestamp = self._timestamp()
        remote_key = f"provider:create:{booking['demoWorkspaceId']}:{booking['id']}"
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO provider_booking_links
                   (local_booking_id,demo_workspace_id,provider_id,external_booking_id,
                    external_version,sync_status,remote_idempotency_key,last_error,created_at,updated_at)
                   VALUES (?,?,?,NULL,NULL,'pending',?,NULL,?,?)""",
                (
                    booking["id"], booking["demoWorkspaceId"], booking["providerId"],
                    remote_key, timestamp, timestamp,
                ),
            )
        return self._get_link(booking["id"], demo_workspace_id=booking["demoWorkspaceId"])

    def _set_link(
        self,
        booking_id: str,
        *,
        sync_status: str,
        external_booking_id: str | None = None,
        external_version: int | None = None,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """UPDATE provider_booking_links SET
                     external_booking_id=COALESCE(?,external_booking_id),
                     external_version=COALESCE(?,external_version),sync_status=?,last_error=?,updated_at=?
                   WHERE local_booking_id=?""",
                (
                    external_booking_id, external_version, sync_status, last_error,
                    self._timestamp(), booking_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM provider_booking_links WHERE local_booking_id=?", (booking_id,),
            ).fetchone()
        if row is None:
            raise ProviderBookingError("Provider 同步紀錄不存在", booking_id=booking_id)
        return self._link(row)

    def catalog(self, provider_id: str | None = None) -> dict[str, Any]:
        try:
            return self._connector_for(provider_id).get_catalog()
        except ProviderConnectorError as exc:
            raise ProviderBookingError(str(exc), state_unknown=False, recoverable=True) from exc

    def availability(self, provider_id: str | None = None, **criteria: Any) -> list[dict[str, Any]]:
        try:
            return self._connector_for(provider_id).get_availability(**criteria)
        except ProviderConnectorError as exc:
            raise ProviderBookingError(str(exc), state_unknown=False, recoverable=True) from exc

    def _validate_selection(self, request: dict[str, Any]) -> None:
        catalog = self.catalog(request["provider_id"])
        provider_id = catalog.get("provider", {}).get("id")
        if request["provider_id"] != provider_id:
            raise ProviderBookingError("選擇的 Provider 不屬於目前 connector")
        if request["location_id"] not in {item.get("id") for item in catalog.get("locations", [])}:
            raise ProviderBookingError("選擇的服務據點不存在")
        if request["offering_id"] not in {item.get("id") for item in catalog.get("offerings", [])}:
            raise ProviderBookingError("選擇的服務方案不存在")
        if request.get("resource_id") and request["resource_id"] not in {
            item.get("id") for item in catalog.get("resources", [])
        }:
            raise ProviderBookingError("選擇的服務資源不存在")
        slots = self.availability(request["provider_id"], offeringId=request["offering_id"])
        slot = next((item for item in slots if item.get("id") == request["slot_id"]), None)
        if slot is None or slot.get("status") != "available":
            raise ProviderBookingError("選擇的時段目前不可預約")
        expected = {
            "providerId": request["provider_id"], "locationId": request["location_id"],
            "offeringId": request["offering_id"], "startsAt": request["starts_at"],
            "endsAt": request["ends_at"],
        }
        if any(slot.get(key) != value for key, value in expected.items()):
            raise ProviderBookingError("預約內容與 Provider 提供的空檔不一致")
        if request.get("resource_id") != slot.get("resourceId"):
            raise ProviderBookingError("預約資源與 Provider 提供的空檔不一致")

    def _sync_create(self, booking: dict[str, Any]) -> dict[str, Any]:
        link = self._ensure_link(booking)
        if link["syncStatus"] == "synced":
            return {**booking, "providerSync": link, "idempotentReplay": True}
        payload = {
            "externalReference": booking["id"],
            "accountReference": hashlib.sha256(booking["accountId"].encode("utf-8")).hexdigest(),
            "offeringId": booking["offeringId"], "locationId": booking["locationId"],
            "resourceId": booking["resourceId"], "slotId": booking["slotId"],
            "startsAt": booking["startsAt"], "endsAt": booking["endsAt"],
        }
        try:
            external = self._connector_for(booking["providerId"]).create_booking(
                payload, idempotency_key=f"provider:create:{booking['demoWorkspaceId']}:{booking['id']}",
            )
        except ProviderConnectorError as exc:
            status = "state_unknown" if exc.state_unknown else "failed"
            self._set_link(booking["id"], sync_status=status, last_error=str(exc))
            raise ProviderBookingError(
                str(exc), booking_id=booking["id"], state_unknown=exc.state_unknown, recoverable=True,
            ) from exc
        link = self._set_link(
            booking["id"], sync_status="synced", external_booking_id=external["id"],
            external_version=int(external.get("version", 1)), last_error=None,
        )
        return {**booking, "providerSync": link}

    def create_booking(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        provider_id: str,
        location_id: str,
        offering_id: str,
        resource_id: str | None,
        slot_id: str,
        starts_at: str,
        ends_at: str,
        idempotency_key: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = locals().copy()
        request.pop("self")
        existing = self.fulfillment.find_booking_by_idempotency(
            demo_workspace_id=demo_workspace_id, workspace_id=workspace_id,
            account_id=account_id, idempotency_key=idempotency_key,
        )
        if existing is not None:
            return self._sync_create(existing)
        payload = {key: value for key, value in request.items() if key != "details"}
        self._validate_selection(payload)
        booking = self.fulfillment.create_booking(**payload, details=details)
        return self._sync_create(booking)

    def retry_create(
        self,
        booking_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
    ) -> dict[str, Any]:
        booking = self.fulfillment.get_booking(
            booking_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, account_id=account_id,
        )
        return self._sync_create(booking)

    def transition_booking(
        self,
        booking_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        provider_id: str,
        expected_version: int,
        to_status: str,
        actor_account_id: str,
        idempotency_key: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        booking = self.fulfillment.get_booking(
            booking_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, provider_id=provider_id,
        )
        if booking["version"] != expected_version:
            # Keep local optimistic concurrency authoritative before touching the provider.
            from core.fulfillment import FulfillmentConflict

            raise FulfillmentConflict("預約版本已更新，請重新載入")
        link = self._get_link(booking_id, demo_workspace_id=demo_workspace_id)
        if link["syncStatus"] == "pending" or not link["externalBookingId"]:
            raise ProviderBookingError(
                "預約尚未與 Provider 同步，請先重試建立同步",
                booking_id=booking_id, recoverable=True,
            )
        remote_key = f"provider:update:{demo_workspace_id}:{booking_id}:{idempotency_key}"
        try:
            external = self._connector_for(booking["providerId"]).update_booking(
                link["externalBookingId"],
                {"expectedVersion": link["externalVersion"], "status": to_status, "note": note},
                idempotency_key=remote_key,
            )
        except ProviderConnectorError as exc:
            status = "state_unknown" if exc.state_unknown else "failed"
            self._set_link(booking_id, sync_status=status, last_error=str(exc))
            raise ProviderBookingError(
                str(exc), booking_id=booking_id, state_unknown=exc.state_unknown, recoverable=True,
            ) from exc
        updated = self.fulfillment.transition_booking(
            booking_id, demo_workspace_id=demo_workspace_id, provider_id=provider_id,
            expected_version=expected_version, to_status=to_status,
            actor_account_id=actor_account_id, idempotency_key=idempotency_key, note=note,
        )
        current_link = self._set_link(
            booking_id, sync_status="synced", external_version=int(external.get("version", 1)),
            last_error=None,
        )
        return {**updated, "providerSync": current_link}

    def member_cancel(
        self,
        booking_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        expected_version: int,
        idempotency_key: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """會員自助取消:先向 Provider 取消,成功後本地轉移(actor=member)。

        只有 ``pending_provider`` 與 ``confirmed`` 可由會員取消;退款與點數沖銷
        由 API 層在取消成功後接續(付款是平台的權威範圍)。
        """
        booking = self.fulfillment.get_booking(
            booking_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, account_id=account_id,
        )
        if booking["status"] not in {"pending_provider", "confirmed"}:
            from core.fulfillment import FulfillmentConflict

            raise FulfillmentConflict(f"預約狀態 {booking['status']} 不可由會員取消")
        if booking["version"] != expected_version:
            from core.fulfillment import FulfillmentConflict

            raise FulfillmentConflict("預約版本已更新，請重新載入")
        link = self._get_link(booking_id, demo_workspace_id=demo_workspace_id)
        if link["externalBookingId"]:
            remote_key = f"provider:update:{demo_workspace_id}:{booking_id}:{idempotency_key}"
            try:
                self._connector_for(booking["providerId"]).update_booking(
                    link["externalBookingId"],
                    {"expectedVersion": link["externalVersion"], "status": "cancelled", "note": note},
                    idempotency_key=remote_key,
                )
            except ProviderConnectorError as exc:
                status = "state_unknown" if exc.state_unknown else "failed"
                self._set_link(booking_id, sync_status=status, last_error=str(exc))
                raise ProviderBookingError(
                    str(exc), booking_id=booking_id,
                    state_unknown=exc.state_unknown, recoverable=True,
                ) from exc
        updated = self.fulfillment.transition_booking(
            booking_id, demo_workspace_id=demo_workspace_id, provider_id=booking["providerId"],
            expected_version=expected_version, to_status="cancelled",
            actor_account_id=account_id, idempotency_key=idempotency_key,
            note=note, actor_role="member",
        )
        return {**updated, "providerSync": self._get_link(booking_id, demo_workspace_id=demo_workspace_id)}

    def snapshot(self, provider_id: str | None = None) -> dict[str, Any]:
        try:
            return self._connector_for(provider_id).snapshot()
        except ProviderConnectorError as exc:
            raise ProviderBookingError(str(exc), state_unknown=False, recoverable=True) from exc
