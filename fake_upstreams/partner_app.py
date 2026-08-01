"""Independent Partner API fake upstream implementing contracts/vendor-openapi.yaml."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from fake_upstreams.partner_seed import DEFAULT_PARTNER_KEYS, build_partner_seed
from fake_upstreams.partner_seed import SEED_VERSION as PARTNER_SEED_VERSION
from fake_upstreams.vendor_seed import SEED_VERSION as LEGACY_SEED_VERSION

SEED_VERSION = PARTNER_SEED_VERSION
ALL_PARTNER_SCOPES = frozenset({
    "catalog:read", "catalog:write", "availability:read", "availability:write",
    "bookings:read", "bookings:write", "snapshot:read", "webhooks:write",
})


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PartnerPrincipal:
    provider_id: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class PendingFault:
    method: str
    path: str
    status: int
    detail: str
    delay_ms: int
    body: Any | None
    after_commit: bool


class FaultReq(BaseModel):
    method: str = "GET"
    path: str
    status: int = Field(default=503, ge=200, le=599)
    detail: str = "模擬 Partner API 異常"
    delay_ms: int = Field(default=0, ge=0, le=30_000)
    body: Any | None = None
    after_commit: bool = False


class CatalogReq(BaseModel):
    seedVersion: str
    provider: dict[str, Any]
    locations: list[dict[str, Any]]
    offerings: list[dict[str, Any]]
    resources: list[dict[str, Any]]


class AvailabilityReq(BaseModel):
    seedVersion: str
    slots: list[dict[str, Any]]


class BookingCreateReq(BaseModel):
    externalReference: str
    accountReference: str
    offeringId: str
    locationId: str
    resourceId: str | None = None
    slotId: str
    startsAt: str
    endsAt: str
    notes: str | None = None


class BookingUpdateReq(BaseModel):
    expectedVersion: int = Field(ge=1)
    status: str
    note: str | None = None


class WebhookReq(BaseModel):
    url: str
    events: list[str]
    signingSecret: str = Field(min_length=16)


class PartnerScenario:
    """多 Provider 的 fake 上游狀態;每家 Provider 有獨立 catalog/availability/bookings 與版本。"""

    def __init__(self, keys: dict[str, tuple[str, frozenset[str]]]) -> None:
        self._lock = RLock()
        self._keys = {_hash(raw): PartnerPrincipal(provider, scopes) for raw, (provider, scopes) in keys.items()}
        self._faults: list[PendingFault] = []
        self._idempotency: dict[tuple[str, str, str], tuple[str, dict[str, Any]]] = {}
        self._request_count = 0
        self._providers = build_partner_seed()
        self._versions = {
            provider_id: {"catalog": 1, "availability": 1, "booking": 0}
            for provider_id in self._providers
        }

    def resolve(self, raw_key: str) -> PartnerPrincipal | None:
        with self._lock:
            return self._keys.get(_hash(raw_key))

    def record_request(self) -> None:
        with self._lock:
            self._request_count += 1

    def consume_fault(self, method: str, path: str) -> PendingFault | None:
        with self._lock:
            for index, fault in enumerate(self._faults):
                if fault.method == method.upper() and fault.path == path:
                    return self._faults.pop(index)
        return None

    def add_fault(self, fault: PendingFault) -> dict:
        with self._lock:
            self._faults.append(fault)
            return asdict(fault)

    def clear_faults(self) -> dict:
        with self._lock:
            cleared = len(self._faults)
            self._faults.clear()
            return {"cleared": cleared}

    def _provider_data(self, provider_id: str) -> dict[str, Any]:
        data = self._providers.get(provider_id)
        if data is None:
            raise KeyError("provider")
        return data

    def data(self, provider_id: str, key: str) -> Any:
        with self._lock:
            return deepcopy(self._provider_data(provider_id)[key])

    def replace(self, provider_id: str, key: str, value: Any) -> Any:
        with self._lock:
            data = self._provider_data(provider_id)
            data[key] = deepcopy(value)
            if key in self._versions[provider_id]:
                self._versions[provider_id][key] += 1
            return deepcopy(data[key])

    def idempotent(
        self, provider_id: str, scope: str, key: str | None, payload: Any, factory,
    ) -> tuple[dict, bool]:
        if not key or len(key.strip()) < 8:
            raise ValueError("Idempotency-Key 至少需要 8 個字元")
        token = (provider_id, scope, key)
        fingerprint = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with self._lock:
            if token in self._idempotency:
                stored_fingerprint, stored_value = self._idempotency[token]
                if stored_fingerprint != fingerprint:
                    raise ValueError("相同 Idempotency-Key 不可用於不同請求內容")
                return deepcopy(stored_value), True
            value = factory()
            self._idempotency[token] = (fingerprint, deepcopy(value))
            return deepcopy(value), False

    def _slot_consume(self, data: dict[str, Any], slot_id: str) -> None:
        """建單成功即消耗 slot 容量;容量歸零時整個 slot 標為 booked。"""
        for slot in data["availability"]:
            if slot["id"] == slot_id:
                slot["capacity"] = max(0, int(slot.get("capacity", 1)) - 1)
                if slot["capacity"] == 0:
                    slot["status"] = "booked"
                return

    def _slot_release(self, data: dict[str, Any], slot_id: str | None) -> None:
        if not slot_id:
            return
        for slot in data["availability"]:
            if slot["id"] == slot_id:
                slot["capacity"] = int(slot.get("capacity", 0)) + 1
                slot["status"] = "available"
                return

    def create_booking(self, provider_id: str, payload: dict) -> dict:
        with self._lock:
            data = self._provider_data(provider_id)
            if payload["offeringId"] not in {item["id"] for item in data["catalog"]["offerings"]}:
                raise ValueError("offeringId 不屬於此 Provider")
            if payload["slotId"] not in {
                item["id"] for item in data["availability"] if item["status"] == "available"
            }:
                raise ValueError("slotId 不存在或已不可預約")
            timestamp = _now()
            booking = {
                **deepcopy(payload), "id": f"partner-booking-{uuid4().hex[:12]}",
                "providerId": provider_id, "status": "pending_provider", "version": 1,
                "createdAt": timestamp, "updatedAt": timestamp,
            }
            data["bookings"].append(booking)
            self._slot_consume(data, payload["slotId"])
            self._versions[provider_id]["booking"] += 1
            self._versions[provider_id]["availability"] += 1
            return deepcopy(booking)

    def get_booking(self, provider_id: str, booking_id: str) -> dict | None:
        with self._lock:
            data = self._provider_data(provider_id)
            return deepcopy(next((
                item for item in data["bookings"] if item["id"] == booking_id
            ), None))

    def update_booking(self, provider_id: str, booking_id: str, *, expected_version: int, status: str) -> dict:
        allowed = {
            "pending_provider": {"confirmed", "rejected", "cancelled"},
            "confirmed": {"in_service", "cancelled"},
            "in_service": {"completed", "exception"},
            "exception": {"in_service", "cancelled"},
        }
        with self._lock:
            data = self._provider_data(provider_id)
            booking = next((item for item in data["bookings"] if item["id"] == booking_id), None)
            if booking is None:
                raise KeyError("booking")
            if booking["version"] != expected_version:
                raise RuntimeError("version")
            if status not in allowed.get(booking["status"], set()):
                raise RuntimeError("transition")
            booking["status"] = status
            booking["version"] += 1
            booking["updatedAt"] = _now()
            if status in {"cancelled", "rejected"}:
                self._slot_release(data, booking.get("slotId"))
                self._versions[provider_id]["availability"] += 1
            self._versions[provider_id]["booking"] += 1
            return deepcopy(booking)

    def snapshot(self, provider_id: str) -> dict:
        with self._lock:
            data = self._provider_data(provider_id)
            versions = self._versions[provider_id]
            return {
                "providerId": provider_id, "seedVersion": SEED_VERSION,
                "catalogVersion": versions["catalog"],
                "availabilityVersion": versions["availability"],
                "bookingVersion": versions["booking"],
                "counts": {
                    "locations": len(data["catalog"]["locations"]),
                    "offerings": len(data["catalog"]["offerings"]),
                    "resources": len(data["catalog"]["resources"]),
                    "availability": len(data["availability"]),
                    "bookings": len(data["bookings"]),
                },
            }

    def state(self) -> dict:
        with self._lock:
            return {
                "seedVersion": SEED_VERSION,
                "legacySeedVersion": LEGACY_SEED_VERSION,
                "requestCount": self._request_count,
                "pendingFaults": [asdict(item) for item in self._faults],
                "apiKeyHashes": sorted(self._keys),
                "providers": sorted(self._providers),
                "snapshots": {
                    provider_id: self.snapshot(provider_id) for provider_id in sorted(self._providers)
                },
            }

    def reset(self) -> dict:
        with self._lock:
            self._faults.clear()
            self._idempotency.clear()
            self._request_count = 0
            self._providers = build_partner_seed()
            self._versions = {
                provider_id: {"catalog": 1, "availability": 1, "booking": 0}
                for provider_id in self._providers
            }
            return self.state()


def create_partner_fake_app(
    *,
    control_key: str | None = None,
    partner_keys: dict[str, tuple[str, frozenset[str]]] | None = None,
) -> FastAPI:
    expected_control_key = control_key or os.environ.get("VENDOR_FAKE_CONTROL_KEY") or secrets.token_urlsafe(32)
    if partner_keys is None:
        configured_keys = {
            key: (provider_id, ALL_PARTNER_SCOPES)
            for provider_id, key in DEFAULT_PARTNER_KEYS.items()
        }
        override = os.environ.get("PARTNER_FAKE_API_KEY")
        if override:
            configured_keys[override] = ("vendor-prince-electric", ALL_PARTNER_SCOPES)
    else:
        configured_keys = partner_keys
    scenario = PartnerScenario(configured_keys)
    app = FastAPI(
        title="AIWave Partner API Fake Upstream", version="2.0.0",
        docs_url="/__fake__/docs", openapi_url="/__fake__/openapi.json",
    )

    def require_control_key(x_fake_control_key: str | None = Header(default=None)) -> None:
        if not x_fake_control_key or not secrets.compare_digest(x_fake_control_key, expected_control_key):
            raise HTTPException(401, "fake server 控制金鑰錯誤")

    def require_scope(scope: str):
        def dependency(authorization: str | None = Header(default=None, alias="Authorization")) -> PartnerPrincipal:
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(401, "缺少 Partner Bearer API key")
            principal = scenario.resolve(authorization[7:].strip())
            if principal is None:
                raise HTTPException(401, "Partner API key 無效")
            if scope not in principal.scopes:
                raise HTTPException(403, f"Partner API key 缺少 {scope} scope")
            return principal
        return dependency

    def envelope(data: Any, *, request: Request, replayed: bool = False) -> dict:
        return {"data": data, "meta": {
            "traceId": request.state.trace_id, "seedVersion": SEED_VERSION,
            "idempotentReplay": replayed, "asOf": _now(),
        }}

    def error(status: int, code: str, message: str, request: Request, details: Any = None) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": {
            "code": code, "message": message, "traceId": request.state.trace_id, "details": details,
        }}, headers={"X-Trace-Id": request.state.trace_id})

    @app.middleware("http")
    async def fake_behavior(request: Request, call_next):
        request.state.trace_id = request.headers.get("X-Trace-Id") or f"trc-{uuid4().hex[:16]}"
        scenario.record_request()
        fault = None
        if request.url.path.startswith("/partner/v1/"):
            fault = scenario.consume_fault(request.method, request.url.path)
            if fault is not None and not fault.after_commit:
                if fault.delay_ms:
                    await asyncio.sleep(fault.delay_ms / 1000)
                if fault.body is not None:
                    return JSONResponse(status_code=fault.status, content=fault.body)
                if fault.status >= 400:
                    return error(fault.status, "INJECTED_FAULT", fault.detail, request, {"afterCommit": False})
        response = await call_next(request)
        if fault is not None and fault.after_commit:
            if fault.delay_ms:
                await asyncio.sleep(fault.delay_ms / 1000)
            if fault.body is not None:
                return JSONResponse(status_code=fault.status, content=fault.body)
            return error(fault.status, "STATE_UNKNOWN", fault.detail, request, {"afterCommit": True})
        response.headers["X-Trace-Id"] = request.state.trace_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "REQUEST_REJECTED"
        return error(exc.status_code, code, str(exc.detail), request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error(422, "VALIDATION_ERROR", "請求內容不符合 Partner OpenAPI", request, exc.errors())

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "seedVersion": SEED_VERSION}

    @app.get("/partner/v1/catalog")
    def get_catalog(request: Request, principal: PartnerPrincipal = Depends(require_scope("catalog:read"))) -> dict:
        try:
            catalog = scenario.data(principal.provider_id, "catalog")
        except KeyError:
            raise HTTPException(404, "查無 Provider catalog") from None
        return envelope(catalog, request=request)

    @app.put("/partner/v1/catalog")
    def replace_catalog(
        payload: CatalogReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        principal: PartnerPrincipal = Depends(require_scope("catalog:write")),
    ) -> dict:
        if payload.provider.get("id") != principal.provider_id:
            raise HTTPException(403, "不可寫入其他 Provider catalog")
        try:
            row, replayed = scenario.idempotent(
                principal.provider_id, "catalog", idempotency_key,
                payload.model_dump(),
                lambda: scenario.replace(principal.provider_id, "catalog", payload.model_dump()),
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return envelope(row, request=request, replayed=replayed)

    @app.get("/partner/v1/availability")
    def get_availability(
        request: Request, offeringId: str | None = None,
        startsAfter: str | None = None, startsBefore: str | None = None,
        principal: PartnerPrincipal = Depends(require_scope("availability:read")),
    ) -> dict:
        rows = list(scenario.data(principal.provider_id, "availability"))
        if offeringId:
            rows = [item for item in rows if item["offeringId"] == offeringId]
        if startsAfter:
            rows = [item for item in rows if item["startsAt"] >= startsAfter]
        if startsBefore:
            rows = [item for item in rows if item["startsAt"] <= startsBefore]
        return envelope(rows, request=request)

    @app.put("/partner/v1/availability")
    def replace_availability(
        payload: AvailabilityReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        principal: PartnerPrincipal = Depends(require_scope("availability:write")),
    ) -> dict:
        if any(item.get("providerId") != principal.provider_id for item in payload.slots):
            raise HTTPException(403, "不可寫入其他 Provider availability")
        try:
            rows, replayed = scenario.idempotent(
                principal.provider_id, "availability", idempotency_key,
                payload.model_dump(),
                lambda: scenario.replace(principal.provider_id, "availability", payload.slots),
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return envelope(rows, request=request, replayed=replayed)

    @app.get("/partner/v1/bookings")
    def list_bookings(
        request: Request, status: str | None = None, updatedAfter: str | None = None,
        principal: PartnerPrincipal = Depends(require_scope("bookings:read")),
    ) -> dict:
        rows = list(scenario.data(principal.provider_id, "bookings"))
        if status:
            rows = [item for item in rows if item["status"] == status]
        if updatedAfter:
            rows = [item for item in rows if item["updatedAt"] >= updatedAfter]
        return envelope(rows, request=request)

    @app.post("/partner/v1/bookings", status_code=201)
    def create_booking(
        payload: BookingCreateReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        principal: PartnerPrincipal = Depends(require_scope("bookings:write")),
    ) -> dict:
        try:
            booking, replayed = scenario.idempotent(
                principal.provider_id, "booking-create", idempotency_key,
                payload.model_dump(),
                lambda: scenario.create_booking(principal.provider_id, payload.model_dump()),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return envelope(booking, request=request, replayed=replayed)

    @app.get("/partner/v1/bookings/{booking_id}")
    def get_booking(
        booking_id: str, request: Request,
        principal: PartnerPrincipal = Depends(require_scope("bookings:read")),
    ) -> dict:
        booking = scenario.get_booking(principal.provider_id, booking_id)
        if booking is None:
            raise HTTPException(404, "查無 booking")
        return envelope(booking, request=request)

    @app.patch("/partner/v1/bookings/{booking_id}")
    def update_booking(
        booking_id: str, payload: BookingUpdateReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        principal: PartnerPrincipal = Depends(require_scope("bookings:write")),
    ) -> dict:
        def update() -> dict:
            return scenario.update_booking(
                principal.provider_id, booking_id,
                expected_version=payload.expectedVersion, status=payload.status,
            )
        try:
            booking, replayed = scenario.idempotent(
                principal.provider_id, f"booking-update:{booking_id}", idempotency_key,
                payload.model_dump(), update,
            )
        except KeyError as exc:
            raise HTTPException(404, "查無 booking") from exc
        except RuntimeError as exc:
            message = "booking version 已更新" if str(exc) == "version" else "booking 狀態轉移不合法"
            raise HTTPException(409, message) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return envelope(booking, request=request, replayed=replayed)

    @app.get("/partner/v1/snapshot")
    def snapshot(
        request: Request,
        principal: PartnerPrincipal = Depends(require_scope("snapshot:read")),
    ) -> dict:
        return envelope(scenario.snapshot(principal.provider_id), request=request)

    @app.put("/partner/v1/webhook-subscriptions")
    def configure_webhook(
        payload: WebhookReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        principal: PartnerPrincipal = Depends(require_scope("webhooks:write")),
    ) -> dict:
        try:
            webhook, replayed = scenario.idempotent(
                principal.provider_id, "webhook", idempotency_key,
                payload.model_dump(),
                lambda: scenario.replace(principal.provider_id, "webhook", {
                    "url": payload.url, "events": payload.events,
                    "signingSecretHash": _hash(payload.signingSecret),
                }),
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return envelope(webhook, request=request, replayed=replayed)

    @app.get("/__fake__/state", dependencies=[Depends(require_control_key)])
    def state(request: Request) -> dict:
        return envelope(scenario.state(), request=request)

    @app.put("/__fake__/faults/next", dependencies=[Depends(require_control_key)])
    def inject_fault(payload: FaultReq, request: Request) -> dict:
        fault = PendingFault(
            method=payload.method.upper(), path=payload.path, status=payload.status,
            detail=payload.detail, delay_ms=payload.delay_ms, body=payload.body,
            after_commit=payload.after_commit,
        )
        return envelope(scenario.add_fault(fault), request=request)

    @app.delete("/__fake__/faults", dependencies=[Depends(require_control_key)])
    def clear_faults(request: Request) -> dict:
        return envelope(scenario.clear_faults(), request=request)

    @app.post("/__fake__/reset", dependencies=[Depends(require_control_key)])
    def reset(request: Request) -> dict:
        return envelope(scenario.reset(), request=request)

    return app


app = create_partner_fake_app()


def main() -> None:
    uvicorn.run(
        "fake_upstreams.partner_app:app",
        host=os.environ.get("VENDOR_FAKE_HOST", "127.0.0.1"),
        port=int(os.environ.get("VENDOR_FAKE_PORT", "8020")),
        reload=False,
    )


if __name__ == "__main__":
    main()
