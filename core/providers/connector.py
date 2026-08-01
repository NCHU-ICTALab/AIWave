from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import httpx

from core.vendors import VendorClient


class ProviderConnectorError(RuntimeError):
    def __init__(self, message: str, *, state_unknown: bool = False) -> None:
        super().__init__(message)
        self.state_unknown = state_unknown


class ProviderConnector(Protocol):
    connector_mode: str

    def get_catalog(self) -> dict[str, Any]: ...
    def get_availability(self, **criteria: Any) -> list[dict[str, Any]]: ...
    def create_booking(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...
    def get_booking(self, booking_id: str) -> dict[str, Any]: ...
    def list_bookings(self, **criteria: Any) -> list[dict[str, Any]]: ...
    def update_booking(self, booking_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...
    def snapshot(self) -> dict[str, Any]: ...


class StandardProviderConnector:
    """HTTP implementation of the checked-in Partner OpenAPI contract."""

    connector_mode = "standard"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 2.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip() or not api_key.strip():
            raise ValueError("Standard ProviderConnector 需要 base URL 與 API key")
        self.api_key = api_key
        self.client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        expected: type = dict,
    ) -> Any:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            response = self.client.request(
                method, path,
                params={key: value for key, value in (params or {}).items() if value is not None} or None,
                json=json_body, headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise ProviderConnectorError("Partner API 逾時，寫入結果未知", state_unknown=method != "GET") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectorError(f"Partner API 無法連線：{exc}", state_unknown=method != "GET") from exc
        if response.status_code >= 400:
            try:
                error = response.json().get("error", {})
                message = error.get("message") or response.json().get("detail")
                state_unknown = error.get("code") == "STATE_UNKNOWN" or bool(error.get("details", {}).get("afterCommit"))
            except (ValueError, TypeError, AttributeError):
                message, state_unknown = None, False
            raise ProviderConnectorError(
                str(message or f"Partner API 回應 {response.status_code}"), state_unknown=state_unknown,
            )
        try:
            body = response.json()
            data, meta = body["data"], body["meta"]
            if not isinstance(data, expected) or not isinstance(meta, dict) or not meta.get("seedVersion"):
                raise TypeError
            return data
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ProviderConnectorError("Partner API 成功回應不符合 OpenAPI 契約") from exc

    def get_catalog(self) -> dict[str, Any]:
        data = self._request("GET", "/partner/v1/catalog")
        if not {"provider", "locations", "offerings", "resources", "seedVersion"} <= data.keys():
            raise ProviderConnectorError("Partner catalog 缺少必要欄位")
        return data

    def get_availability(self, **criteria: Any) -> list[dict[str, Any]]:
        return self._request("GET", "/partner/v1/availability", params=criteria, expected=list)

    def create_booking(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST", "/partner/v1/bookings", json_body=payload,
            idempotency_key=idempotency_key,
        )

    def get_booking(self, booking_id: str) -> dict[str, Any]:
        return self._request("GET", f"/partner/v1/bookings/{booking_id}")

    def list_bookings(self, **criteria: Any) -> list[dict[str, Any]]:
        return self._request("GET", "/partner/v1/bookings", params=criteria, expected=list)

    def update_booking(self, booking_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "PATCH", f"/partner/v1/bookings/{booking_id}", json_body=payload,
            idempotency_key=idempotency_key,
        )

    def snapshot(self) -> dict[str, Any]:
        return self._request("GET", "/partner/v1/snapshot")


class ExistingVendorAdapterConnector:
    """Maps the checked-in legacy VendorClient to the ProviderConnector contract.

    Legacy order creation requires inquiry and quote IDs; callers must pass them in
    the adapter payload. This makes the incompatibility explicit instead of hiding it.
    """

    connector_mode = "adapter"

    def __init__(self, client: VendorClient, *, provider_id: str) -> None:
        self.client = client
        self.provider_id = provider_id

    def get_catalog(self) -> dict[str, Any]:
        provider = self.client.get_vendor(self.provider_id)["data"]
        offerings = self.client.list_offerings(vendorId=self.provider_id)["data"]
        return {
            "seedVersion": "legacy-vendor-adapter-v1", "provider": provider,
            "locations": [], "offerings": offerings, "resources": [],
        }

    def get_availability(self, **criteria: Any) -> list[dict[str, Any]]:
        service_id = criteria.get("serviceId")
        if not service_id:
            raise ProviderConnectorError("Legacy adapter 查時段需要 serviceId")
        return self.client.get_availability(
            vendor_id=self.provider_id, service_id=service_id, date=criteria.get("date"),
        )["data"]

    def create_booking(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        inquiry_id, quote_id = payload.get("legacyInquiryId"), payload.get("legacyQuoteId")
        if not inquiry_id or not quote_id:
            raise ProviderConnectorError("Legacy adapter 建單需要 legacyInquiryId 與 legacyQuoteId")
        return self.client.create_order({
            "inquiryId": inquiry_id, "quoteId": quote_id,
            "accountId": payload["accountReference"],
            "externalReference": payload["externalReference"],
        }, idempotency_key=idempotency_key)["data"]

    def get_booking(self, booking_id: str) -> dict[str, Any]:
        return self.client.get_order(booking_id)["data"]

    def list_bookings(self, **criteria: Any) -> list[dict[str, Any]]:
        return self.client.list_orders(vendorId=self.provider_id, **criteria)["data"]

    def update_booking(self, booking_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self.client.append_order_event(booking_id, {
            "type": f"status_{payload['status']}", "status": payload["status"], "note": payload.get("note"),
        }, idempotency_key=idempotency_key)["data"]

    def snapshot(self) -> dict[str, Any]:
        catalog = self.get_catalog()
        bookings = self.list_bookings()
        return {
            "providerId": self.provider_id, "seedVersion": catalog["seedVersion"],
            "catalogVersion": 1, "availabilityVersion": 1,
            "bookingVersion": max((item.get("version", 0) for item in bookings), default=0),
            "counts": {"offerings": len(catalog["offerings"]), "bookings": len(bookings)},
        }


class WorkbenchProviderConnector:
    """ProviderConnector for partners without an API, backed by their workbench."""

    connector_mode = "workbench"

    def __init__(self, path: str | Path, *, provider_id: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.provider_id = provider_id
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS provider_workbench_state (
                    provider_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    PRIMARY KEY(provider_id,kind)
                );
                CREATE TABLE IF NOT EXISTS provider_workbench_bookings (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    UNIQUE(provider_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS provider_workbench_operations (
                    provider_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    payload_fingerprint TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    PRIMARY KEY(provider_id,operation,idempotency_key)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _replay(
        self, connection: sqlite3.Connection, *, operation: str,
        idempotency_key: str, payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if len(idempotency_key.strip()) < 8:
            raise ProviderConnectorError("Idempotency-Key 至少需要 8 個字元")
        row = connection.execute(
            """SELECT payload_fingerprint,response_json FROM provider_workbench_operations
               WHERE provider_id=? AND operation=? AND idempotency_key=?""",
            (self.provider_id, operation, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if row["payload_fingerprint"] != self._fingerprint(payload):
            raise ProviderConnectorError("相同 Idempotency-Key 不可用於不同請求內容")
        return json.loads(row["response_json"])

    def _remember(
        self, connection: sqlite3.Connection, *, operation: str,
        idempotency_key: str, payload: dict[str, Any], response: dict[str, Any],
    ) -> None:
        connection.execute(
            """INSERT INTO provider_workbench_operations
               (provider_id,operation,idempotency_key,payload_fingerprint,response_json)
               VALUES (?,?,?,?,?)""",
            (
                self.provider_id, operation, idempotency_key, self._fingerprint(payload),
                json.dumps(response, ensure_ascii=False),
            ),
        )

    def save_catalog(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("provider", {}).get("id") != self.provider_id:
            raise ProviderConnectorError("Workbench catalog 的 Provider 不相符")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO provider_workbench_state(provider_id,kind,payload_json,version)
                   VALUES (?,'catalog',?,1) ON CONFLICT(provider_id,kind) DO UPDATE SET
                     payload_json=excluded.payload_json,version=provider_workbench_state.version+1""",
                (self.provider_id, json.dumps(payload, ensure_ascii=False)),
            )
        return payload

    def save_availability(self, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if any(item.get("providerId") != self.provider_id for item in slots):
            raise ProviderConnectorError("Workbench availability 的 Provider 不相符")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO provider_workbench_state(provider_id,kind,payload_json,version)
                   VALUES (?,'availability',?,1) ON CONFLICT(provider_id,kind) DO UPDATE SET
                     payload_json=excluded.payload_json,version=provider_workbench_state.version+1""",
                (self.provider_id, json.dumps(slots, ensure_ascii=False)),
            )
        return slots

    def _state(self, kind: str, default: Any) -> tuple[Any, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json,version FROM provider_workbench_state WHERE provider_id=? AND kind=?",
                (self.provider_id, kind),
            ).fetchone()
        return (default, 0) if row is None else (json.loads(row["payload_json"]), row["version"])

    def get_catalog(self) -> dict[str, Any]:
        payload, _ = self._state("catalog", None)
        if payload is None:
            raise ProviderConnectorError("Workbench 尚未建立 catalog")
        return payload

    def get_availability(self, **criteria: Any) -> list[dict[str, Any]]:
        rows, _ = self._state("availability", [])
        if criteria.get("offeringId"):
            rows = [item for item in rows if item["offeringId"] == criteria["offeringId"]]
        return rows

    def create_booking(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        with self._connect() as connection:
            replay = self._replay(
                connection, operation="create-booking", idempotency_key=idempotency_key, payload=payload,
            )
            if replay is not None:
                return replay
            booking = {
                **payload, "id": f"workbench-booking-{uuid4().hex[:12]}",
                "providerId": self.provider_id, "status": "pending_provider", "version": 1,
            }
            connection.execute(
                """INSERT INTO provider_workbench_bookings
                   (id,provider_id,payload_json,status,version,idempotency_key) VALUES (?,?,?,?,?,?)""",
                (booking["id"], self.provider_id, json.dumps(booking, ensure_ascii=False), booking["status"], 1, idempotency_key),
            )
            self._remember(
                connection, operation="create-booking", idempotency_key=idempotency_key,
                payload=payload, response=booking,
            )
            return booking

    def get_booking(self, booking_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM provider_workbench_bookings WHERE id=? AND provider_id=?",
                (booking_id, self.provider_id),
            ).fetchone()
        if row is None:
            raise ProviderConnectorError("Workbench 查無 booking")
        return {**json.loads(row["payload_json"]), "status": row["status"], "version": row["version"]}

    def list_bookings(self, **criteria: Any) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM provider_workbench_bookings WHERE provider_id=? ORDER BY id", (self.provider_id,),
            ).fetchall()
        result = [{**json.loads(row["payload_json"]), "status": row["status"], "version": row["version"]} for row in rows]
        return [item for item in result if not criteria.get("status") or item["status"] == criteria["status"]]

    def update_booking(self, booking_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        with self._connect() as connection:
            operation = f"update-booking:{booking_id}"
            replay = self._replay(
                connection, operation=operation, idempotency_key=idempotency_key, payload=payload,
            )
            if replay is not None:
                return replay
            row = connection.execute(
                "SELECT * FROM provider_workbench_bookings WHERE id=? AND provider_id=?",
                (booking_id, self.provider_id),
            ).fetchone()
            if row is None:
                raise ProviderConnectorError("Workbench 查無 booking")
            if row["version"] != payload["expectedVersion"]:
                raise ProviderConnectorError("Workbench booking version 已更新")
            connection.execute(
                "UPDATE provider_workbench_bookings SET status=?,version=version+1 WHERE id=?",
                (payload["status"], booking_id),
            )
            response = {
                **json.loads(row["payload_json"]),
                "status": payload["status"], "version": row["version"] + 1,
            }
            self._remember(
                connection, operation=operation, idempotency_key=idempotency_key,
                payload=payload, response=response,
            )
            return response

    def snapshot(self) -> dict[str, Any]:
        _, catalog_version = self._state("catalog", {})
        availability, availability_version = self._state("availability", [])
        bookings = self.list_bookings()
        return {
            "providerId": self.provider_id, "seedVersion": "workbench-v1",
            "catalogVersion": catalog_version, "availabilityVersion": availability_version,
            "bookingVersion": max((item["version"] for item in bookings), default=0),
            "counts": {"availability": len(availability), "bookings": len(bookings)},
        }


def build_provider_connector(
    *,
    mode: str,
    provider_id: str,
    database: str | Path,
    standard_url: str = "",
    standard_api_key: str = "",
    timeout_seconds: float = 2.0,
    vendor_client: VendorClient | None = None,
) -> ProviderConnector:
    normalized = mode.strip().lower()
    if normalized == "standard":
        return StandardProviderConnector(
            base_url=standard_url, api_key=standard_api_key, timeout_seconds=timeout_seconds,
        )
    if normalized == "adapter":
        if vendor_client is None:
            raise ValueError("PROVIDER_MODE=adapter 需要 VendorClient")
        return ExistingVendorAdapterConnector(vendor_client, provider_id=provider_id)
    if normalized == "workbench":
        return WorkbenchProviderConnector(database, provider_id=provider_id)
    raise ValueError("PROVIDER_MODE 只接受 standard、adapter 或 workbench")
