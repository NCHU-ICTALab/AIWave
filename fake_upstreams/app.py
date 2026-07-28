"""`demo_seed_v1` fake upstream HTTP server。

資料端點模擬尚未取得的品牌能力；`/__fake__` 是只供本機測試與彩排的控制面。
Vue 不得直接呼叫本服務。
"""

from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from core.retail.seed_data import PRODUCTS, STORES

SCENARIO = "demo_seed_v1"
DATA_SOURCE = f"fake_upstream:{SCENARIO}"


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
    status: int = Field(default=200, ge=200, le=599)
    detail: str = "模擬上游服務異常"
    delay_ms: int = Field(default=0, ge=0, le=5000)
    body: Any | None = None


class ScenarioController:
    """執行中情境的唯一控制介面；fault 取用與 reset 都是原子的。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._faults: list[PendingFault] = []
        self._request_count = 0

    def record_request(self) -> None:
        with self._lock:
            self._request_count += 1

    def add_fault(self, fault: PendingFault) -> dict:
        with self._lock:
            self._faults.append(fault)
        return asdict(fault)

    def consume(self, method: str, path: str) -> PendingFault | None:
        with self._lock:
            for index, fault in enumerate(self._faults):
                if fault.method == method.upper() and fault.path == path:
                    return self._faults.pop(index)
        return None

    def state(self) -> dict:
        with self._lock:
            return {
                "scenario": SCENARIO,
                "requestCount": self._request_count,
                "pendingFaults": [asdict(fault) for fault in self._faults],
            }

    def reset(self) -> dict:
        with self._lock:
            self._faults.clear()
            self._request_count = 0
            return {
                "scenario": SCENARIO,
                "requestCount": self._request_count,
                "pendingFaults": [],
            }


def create_fake_upstream_app(*, control_key: str | None = None) -> FastAPI:
    # 沒設定時使用不可預測的一次性金鑰，寧可讓控制面不可用，也不能用公開預設密碼。
    expected_key = control_key or os.environ.get("FAKE_CONTROL_KEY") or secrets.token_urlsafe(32)
    controller = ScenarioController()
    app = FastAPI(title="AIWave Fake Upstream", docs_url="/__fake__/docs", openapi_url="/__fake__/openapi.json")

    def require_control_key(x_fake_control_key: str | None = Header(default=None)) -> None:
        if not x_fake_control_key or x_fake_control_key != expected_key:
            raise HTTPException(401, "fake server 控制金鑰錯誤")

    @app.middleware("http")
    async def scenario_behavior(request, call_next):
        controller.record_request()
        if request.url.path.startswith("/v1/"):
            fault = controller.consume(request.method, request.url.path)
            if fault is not None:
                if fault.delay_ms:
                    await asyncio.sleep(fault.delay_ms / 1000)
                if fault.body is not None:
                    return JSONResponse(status_code=fault.status, content=fault.body)
                if fault.status < 400:
                    return await call_next(request)
                return JSONResponse(status_code=fault.status, content={
                    "detail": fault.detail,
                    "meta": {"dataSource": DATA_SOURCE, "injected": True},
                })
        return await call_next(request)

    def meta() -> dict:
        return {"scenario": SCENARIO, "dataSource": DATA_SOURCE, "asOf": "2026-07-25T09:00:00+08:00"}

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "scenario": SCENARIO}

    @app.get("/v1/retail/products/resolve")
    def resolve_product(q: str) -> dict:
        normalized = q.strip().lower()
        for product_id, product in PRODUCTS.items():
            if product["name"].lower() in normalized or any(
                keyword.lower() in normalized for keyword in product["keywords"]
            ):
                return {"data": {"id": product_id, "name": product["name"]}, "meta": meta()}
        raise HTTPException(404, "上游商品目錄找不到這項商品")

    @app.get("/v1/retail/inventory/{product_id}")
    def inventory(product_id: str) -> dict:
        product = PRODUCTS.get(product_id)
        if product is None:
            raise HTTPException(404, "上游商品目錄查無商品")
        rows = [{
            "storeId": store["id"],
            "storeName": store["storeName"],
            "district": store["district"],
            "address": store["address"],
            "distanceMeters": store["distanceMeters"],
            "capabilities": list(store["capabilities"]),
            "stock": store["inventory"].get(product_id, 0),
        } for store in STORES]
        return {"product": {"id": product_id, "name": product["name"]}, "data": rows, "meta": meta()}

    @app.get("/__fake__/state", dependencies=[Depends(require_control_key)])
    def fake_state() -> dict:
        return {"data": controller.state()}

    @app.put("/__fake__/faults/next", dependencies=[Depends(require_control_key)])
    def add_fault(req: FaultReq) -> dict:
        fault = PendingFault(
            method=req.method.upper(), path=req.path, status=req.status,
            detail=req.detail.strip(), delay_ms=req.delay_ms, body=req.body,
        )
        return {"data": controller.add_fault(fault)}

    @app.post("/__fake__/reset", dependencies=[Depends(require_control_key)])
    def reset() -> dict:
        return {"data": controller.reset()}

    return app


app = create_fake_upstream_app()


def main() -> None:
    uvicorn.run(
        "fake_upstreams.app:app",
        host=os.environ.get("FAKE_UPSTREAM_HOST", "127.0.0.1"),
        port=int(os.environ.get("FAKE_UPSTREAM_PORT", "8010")),
        reload=False,
    )


if __name__ == "__main__":
    main()
