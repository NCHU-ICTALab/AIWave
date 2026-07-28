"""可獨立啟動的廠商 API fake server（預設 http://127.0.0.1:8020）。"""

from __future__ import annotations

import asyncio
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

from fake_upstreams.vendor_seed import DATA_SOURCE, SEED_VERSION, build_vendor_seed


@dataclass(frozen=True)
class PendingFault:
    method: str
    path: str
    status: int
    detail: str
    delay_ms: int
    body: Any | None


class FaultReq(BaseModel):
    method: str = "GET"
    path: str
    status: int = Field(default=503, ge=200, le=599)
    detail: str = "模擬廠商 API 異常"
    delay_ms: int = Field(default=0, ge=0, le=10_000)
    body: Any | None = None


class InquiryReq(BaseModel):
    accountId: str
    serviceId: str
    vendorId: str | None = None
    consumer: dict[str, Any]
    location: dict[str, Any]
    preferredSlots: list[str] = []
    budget: int | None = Field(default=None, ge=0)
    urgency: str = "normal"
    answers: dict[str, Any] = {}
    summary: str
    externalReference: str | None = None


class QuoteItemReq(BaseModel):
    name: str
    quantity: int = Field(default=1, ge=1)
    unitPrice: int = Field(ge=0)


class QuoteReq(BaseModel):
    vendorId: str
    items: list[QuoteItemReq]
    validUntil: str


class OrderReq(BaseModel):
    inquiryId: str
    quoteId: str
    accountId: str
    externalReference: str | None = None


class OrderEventReq(BaseModel):
    type: str
    status: str
    note: str | None = None
    occurredAt: str | None = None


def _now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _error(status: int, code: str, message: str, trace_id: str, details: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "details": details, "traceId": trace_id,
    }}, headers={"X-Trace-Id": trace_id})


class VendorScenario:
    def __init__(self) -> None:
        self._lock = RLock()
        self._faults: list[PendingFault] = []
        self._request_count = 0
        self._idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self._data = build_vendor_seed()

    def record_request(self) -> None:
        with self._lock:
            self._request_count += 1

    def consume_fault(self, method: str, path: str) -> PendingFault | None:
        with self._lock:
            for index, fault in enumerate(self._faults):
                if fault.method == method.upper() and fault.path == path:
                    return self._faults.pop(index)
        return None

    def add_fault(self, fault: PendingFault) -> dict[str, Any]:
        with self._lock:
            self._faults.append(fault)
            return asdict(fault)

    def list(self, key: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._data[key])

    def get(self, key: str, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(next((item for item in self._data[key] if item["id"] == item_id), None))

    def append(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._data[key].append(deepcopy(value))
            return deepcopy(value)

    def idempotent(self, scope: str, key: str | None, factory) -> tuple[dict[str, Any], bool]:
        if not key:
            raise ValueError("Idempotency-Key header is required")
        token = (scope, key)
        with self._lock:
            if token in self._idempotency:
                return deepcopy(self._idempotency[token]), True
            value = factory()
            self._idempotency[token] = deepcopy(value)
            return deepcopy(value), False

    def update_order(self, order_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            order = next((item for item in self._data["orders"] if item["id"] == order_id), None)
            if order is None:
                return None
            order["events"].append(deepcopy(event))
            order["status"] = event["status"]
            order["version"] += 1
            order["updatedAt"] = event["occurredAt"]
            return deepcopy(order)

    def update_inquiry_status(self, inquiry_id: str, status: str) -> dict[str, Any] | None:
        with self._lock:
            inquiry = next((item for item in self._data["inquiries"] if item["id"] == inquiry_id), None)
            if inquiry is None:
                return None
            inquiry["status"] = status
            inquiry["version"] += 1
            inquiry["updatedAt"] = _now()
            return deepcopy(inquiry)

    def state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "scenario": SEED_VERSION, "requestCount": self._request_count,
                "pendingFaults": [asdict(item) for item in self._faults],
                "counts": {key: len(value) for key, value in self._data.items()},
            }

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._faults.clear()
            self._request_count = 0
            self._idempotency.clear()
            self._data = build_vendor_seed()
            return self.state()


def create_fake_vendor_app(*, control_key: str | None = None) -> FastAPI:
    expected_key = control_key or os.environ.get("VENDOR_FAKE_CONTROL_KEY") or secrets.token_urlsafe(32)
    scenario = VendorScenario()
    app = FastAPI(
        title="AIWave Vendor Fake Server", version="1.0.0",
        docs_url="/__fake__/docs", openapi_url="/__fake__/openapi.json",
    )

    def require_control_key(x_fake_control_key: str | None = Header(default=None)) -> None:
        if not x_fake_control_key or not secrets.compare_digest(x_fake_control_key, expected_key):
            raise HTTPException(401, "fake server 控制金鑰錯誤")

    def envelope(data: Any, *, trace_id: str, replayed: bool = False) -> dict[str, Any]:
        return {"data": data, "meta": {
            "scenario": SEED_VERSION, "dataSource": DATA_SOURCE, "asOf": _now(),
            "traceId": trace_id, "idempotentReplay": replayed,
        }}

    @app.middleware("http")
    async def behavior(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or f"trc-{uuid4().hex[:16]}"
        request.state.trace_id = trace_id
        scenario.record_request()
        if request.url.path.startswith("/v1/"):
            fault = scenario.consume_fault(request.method, request.url.path)
            if fault is not None:
                if fault.delay_ms:
                    await asyncio.sleep(fault.delay_ms / 1000)
                if fault.body is not None:
                    return JSONResponse(status_code=fault.status, content=fault.body, headers={"X-Trace-Id": trace_id})
                if fault.status >= 400:
                    return _error(fault.status, "INJECTED_FAULT", fault.detail, trace_id, {"injected": True})
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        trace_id = getattr(request.state, "trace_id", f"trc-{uuid4().hex[:16]}")
        code = "NOT_FOUND" if exc.status_code == 404 else "REQUEST_REJECTED"
        return _error(exc.status_code, code, str(exc.detail), trace_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", f"trc-{uuid4().hex[:16]}")
        return _error(422, "VALIDATION_ERROR", "請求內容不符合契約", trace_id, exc.errors())

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "scenario": SEED_VERSION}

    @app.get("/v1/vendors")
    def vendors(
        request: Request, serviceId: str | None = None, countyCode: str | None = None,
        districtCode: str | None = None, supportsUrgent: bool | None = None,
    ) -> dict[str, Any]:
        rows = scenario.list("vendors")
        locations = scenario.list("locations")
        if serviceId:
            rows = [row for row in rows if serviceId in row["serviceIds"]]
        if supportsUrgent is not None:
            rows = [row for row in rows if row["supportsUrgent"] is supportsUrgent]
        if countyCode:
            allowed = {row["vendorId"] for row in locations if row["countyCode"] == countyCode and (
                not districtCode or row["districtCode"] == districtCode
            )}
            rows = [row for row in rows if row["id"] in allowed]
        return envelope(rows, trace_id=request.state.trace_id)

    @app.get("/v1/vendors/{vendor_id}")
    def vendor(vendor_id: str, request: Request) -> dict[str, Any]:
        row = scenario.get("vendors", vendor_id)
        if row is None:
            raise HTTPException(404, "查無廠商")
        return envelope(row, trace_id=request.state.trace_id)

    @app.get("/v1/vendors/{vendor_id}/locations")
    def vendor_locations(vendor_id: str, request: Request) -> dict[str, Any]:
        if scenario.get("vendors", vendor_id) is None:
            raise HTTPException(404, "查無廠商")
        rows = [item for item in scenario.list("locations") if item["vendorId"] == vendor_id]
        return envelope(rows, trace_id=request.state.trace_id)

    @app.get("/v1/offerings")
    def offerings(
        request: Request, vendorId: str | None = None, serviceId: str | None = None,
    ) -> dict[str, Any]:
        rows = scenario.list("offerings")
        if vendorId:
            rows = [row for row in rows if row["vendorId"] == vendorId]
        if serviceId:
            rows = [row for row in rows if row["serviceId"] == serviceId]
        return envelope(rows, trace_id=request.state.trace_id)

    @app.get("/v1/availability")
    def availability(
        request: Request, vendorId: str = Query(...), serviceId: str = Query(...),
        date: str | None = None,
    ) -> dict[str, Any]:
        offering = next((item for item in scenario.list("offerings") if
                         item["vendorId"] == vendorId and item["serviceId"] == serviceId), None)
        if offering is None:
            raise HTTPException(404, "查無廠商服務方案")
        target_date = date or "2026-08-01"
        rows = [{"date": target_date, "slot": slot, "available": True,
                 "remainingCapacity": 1 + index % 3} for index, slot in enumerate(offering["slots"])]
        return envelope(rows, trace_id=request.state.trace_id)

    @app.get("/v1/inquiries")
    def list_inquiries(
        request: Request, vendorId: str | None = None, status: str | None = None,
        accountId: str | None = None,
    ) -> dict[str, Any]:
        rows = scenario.list("inquiries")
        if vendorId:
            rows = [row for row in rows if row.get("vendorId") == vendorId]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if accountId:
            rows = [row for row in rows if row.get("accountId") == accountId]
        rows.sort(key=lambda row: (row.get("createdAt", ""), row["id"]), reverse=True)
        return envelope(rows, trace_id=request.state.trace_id)

    @app.post("/v1/inquiries", status_code=201)
    def create_inquiry(
        payload: InquiryReq, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        if payload.vendorId and scenario.get("vendors", payload.vendorId) is None:
            raise HTTPException(422, "vendorId 不存在")

        def factory() -> dict[str, Any]:
            created_at = _now()
            row = payload.model_dump()
            row.update({
                "id": f"vinq-{uuid4().hex[:12]}", "status": "submitted", "version": 1,
                "createdAt": created_at, "updatedAt": created_at, "dataSource": DATA_SOURCE,
            })
            return scenario.append("inquiries", row)

        try:
            row, replayed = scenario.idempotent("create-inquiry", idempotency_key, factory)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return envelope(row, trace_id=request.state.trace_id, replayed=replayed)

    @app.get("/v1/inquiries/{inquiry_id}")
    def get_inquiry(inquiry_id: str, request: Request) -> dict[str, Any]:
        row = scenario.get("inquiries", inquiry_id)
        if row is None:
            raise HTTPException(404, "查無諮詢單")
        return envelope(row, trace_id=request.state.trace_id)

    @app.post("/v1/inquiries/{inquiry_id}/quotes", status_code=201)
    def create_quote(
        inquiry_id: str, payload: QuoteReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        if scenario.get("inquiries", inquiry_id) is None:
            raise HTTPException(404, "查無諮詢單")
        if scenario.get("vendors", payload.vendorId) is None:
            raise HTTPException(422, "vendorId 不存在")

        def factory() -> dict[str, Any]:
            items = [{**item.model_dump(), "amount": item.quantity * item.unitPrice} for item in payload.items]
            total = sum(item["amount"] for item in items)
            created = scenario.append("quotes", {
                "id": f"vqt-{uuid4().hex[:12]}", "inquiryId": inquiry_id, "vendorId": payload.vendorId,
                "items": items, "subtotal": total, "total": total, "currency": "TWD", "status": "proposed",
                "validUntil": payload.validUntil, "createdAt": _now(), "dataSource": DATA_SOURCE,
            })
            scenario.update_inquiry_status(inquiry_id, "quoted")
            return created

        try:
            row, replayed = scenario.idempotent(f"create-quote:{inquiry_id}", idempotency_key, factory)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return envelope(row, trace_id=request.state.trace_id, replayed=replayed)

    @app.get("/v1/inquiries/{inquiry_id}/quotes")
    def list_quotes(inquiry_id: str, request: Request) -> dict[str, Any]:
        if scenario.get("inquiries", inquiry_id) is None:
            raise HTTPException(404, "查無諮詢單")
        rows = [item for item in scenario.list("quotes") if item["inquiryId"] == inquiry_id]
        return envelope(rows, trace_id=request.state.trace_id)

    @app.get("/v1/orders")
    def list_orders(
        request: Request, vendorId: str | None = None, status: str | None = None,
        accountId: str | None = None,
    ) -> dict[str, Any]:
        rows = scenario.list("orders")
        if vendorId:
            rows = [row for row in rows if row.get("vendorId") == vendorId]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if accountId:
            rows = [row for row in rows if row.get("accountId") == accountId]
        rows.sort(key=lambda row: (row.get("createdAt", ""), row["id"]), reverse=True)
        return envelope(rows, trace_id=request.state.trace_id)

    @app.post("/v1/orders", status_code=201)
    def create_order(
        payload: OrderReq, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        inquiry = scenario.get("inquiries", payload.inquiryId)
        quote = scenario.get("quotes", payload.quoteId)
        if inquiry is None or quote is None or quote["inquiryId"] != payload.inquiryId:
            raise HTTPException(422, "諮詢單與報價不相符")

        def factory() -> dict[str, Any]:
            created_at = _now()
            event = {"id": f"evt-{uuid4().hex[:10]}", "type": "created", "status": "confirmed",
                     "note": "住戶已確認報價", "occurredAt": created_at}
            created = scenario.append("orders", {
                "id": f"vord-{uuid4().hex[:12]}", "inquiryId": payload.inquiryId,
                "quoteId": payload.quoteId, "vendorId": quote["vendorId"], "accountId": payload.accountId,
                "status": "confirmed", "version": 1, "externalReference": payload.externalReference,
                "events": [event], "createdAt": created_at, "updatedAt": created_at, "dataSource": DATA_SOURCE,
            })
            scenario.update_inquiry_status(payload.inquiryId, "accepted")
            return created

        try:
            row, replayed = scenario.idempotent("create-order", idempotency_key, factory)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return envelope(row, trace_id=request.state.trace_id, replayed=replayed)

    @app.get("/v1/orders/{order_id}")
    def get_order(order_id: str, request: Request) -> dict[str, Any]:
        row = scenario.get("orders", order_id)
        if row is None:
            raise HTTPException(404, "查無訂單")
        return envelope(row, trace_id=request.state.trace_id)

    @app.post("/v1/orders/{order_id}/events", status_code=201)
    def append_order_event(
        order_id: str, payload: OrderEventReq, request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            event = payload.model_dump()
            event.update({"id": f"evt-{uuid4().hex[:10]}", "occurredAt": payload.occurredAt or _now()})
            updated = scenario.update_order(order_id, event)
            if updated is None:
                raise HTTPException(404, "查無訂單")
            return updated

        try:
            row, replayed = scenario.idempotent(f"order-event:{order_id}", idempotency_key, factory)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return envelope(row, trace_id=request.state.trace_id, replayed=replayed)

    @app.get("/__fake__/state", dependencies=[Depends(require_control_key)])
    def state(request: Request) -> dict[str, Any]:
        return envelope(scenario.state(), trace_id=request.state.trace_id)

    @app.put("/__fake__/faults/next", dependencies=[Depends(require_control_key)])
    def inject_fault(payload: FaultReq, request: Request) -> dict[str, Any]:
        fault = PendingFault(
            method=payload.method.upper(), path=payload.path, status=payload.status,
            detail=payload.detail.strip(), delay_ms=payload.delay_ms, body=payload.body,
        )
        return envelope(scenario.add_fault(fault), trace_id=request.state.trace_id)

    @app.post("/__fake__/reset", dependencies=[Depends(require_control_key)])
    def reset(request: Request) -> dict[str, Any]:
        return envelope(scenario.reset(), trace_id=request.state.trace_id)

    return app


app = create_fake_vendor_app()


def main() -> None:
    uvicorn.run(
        "fake_upstreams.vendor_app:app",
        host=os.environ.get("VENDOR_FAKE_HOST", "127.0.0.1"),
        port=int(os.environ.get("VENDOR_FAKE_PORT", "8020")),
        reload=False,
    )


if __name__ == "__main__":
    main()
