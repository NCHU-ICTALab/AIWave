"""門市商品與庫存的 Connector seam。

平台只依賴 `RetailConnector`。HTTP adapter 可連 fake upstream 或未來正式 API；
離線 adapter 使用同一版本的情境資料，並在 fallback 時明確揭露降級。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

import httpx

from .seed_data import PRODUCTS, STORES


class RetailConnectorError(RuntimeError):
    """上游契約、網路或資料錯誤。"""


@dataclass(frozen=True)
class RetailProduct:
    id: str
    name: str


@dataclass(frozen=True)
class StoreInventory:
    store_id: str
    store_name: str
    district: str
    address: str
    distance_meters: int
    capabilities: tuple[str, ...]
    stock: int


@dataclass(frozen=True)
class RetailSnapshot:
    product: RetailProduct
    stores: tuple[StoreInventory, ...]
    data_source: str
    as_of: str
    connector_mode: str
    degraded_reason: str | None = None


class RetailConnector(Protocol):
    def lookup(self, query: str) -> RetailSnapshot: ...
    def inventory(self, product_id: str) -> RetailSnapshot: ...


def _seed_product(query: str) -> RetailProduct:
    normalized = query.strip().lower()
    for product_id, product in PRODUCTS.items():
        if product["name"].lower() in normalized or any(word.lower() in normalized for word in product["keywords"]):
            return RetailProduct(id=product_id, name=product["name"])
    raise ValueError("目前找不到這項商品，請改用商品名稱或聯名關鍵字")


class SeedRetailConnector:
    def lookup(self, query: str) -> RetailSnapshot:
        return self.inventory(_seed_product(query).id)

    def inventory(self, product_id: str) -> RetailSnapshot:
        product = PRODUCTS.get(product_id)
        if product is None:
            raise ValueError("查無商品")
        stores = tuple(StoreInventory(
            store_id=store["id"], store_name=store["storeName"], district=store["district"],
            address=store["address"], distance_meters=store["distanceMeters"],
            capabilities=tuple(store["capabilities"]), stock=store["inventory"].get(product_id, 0),
        ) for store in STORES)
        return RetailSnapshot(
            product=RetailProduct(id=product_id, name=product["name"]), stores=stores,
            data_source="competition_seed", as_of="2026-07-25T09:00:00+08:00", connector_mode="seed",
        )


class HttpRetailConnector:
    def __init__(self, *, base_url: str, client: httpx.Client | None = None, timeout_seconds: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout_seconds)

    def _get(self, path: str, **params) -> dict:
        try:
            response = self.client.get(path, params=params or None)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail")
            except ValueError:
                detail = None
            raise RetailConnectorError(detail or f"上游回應 {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RetailConnectorError(f"上游庫存服務無法連線：{exc}") from exc

    def lookup(self, query: str) -> RetailSnapshot:
        product_payload = self._get("/v1/retail/products/resolve", q=query)
        try:
            product = product_payload["data"]
            product_id = str(product["id"])
            product_name = str(product["name"])
        except (KeyError, TypeError) as exc:
            raise RetailConnectorError("上游商品回應不符合契約") from exc
        return self._inventory_payload(
            {"id": product_id, "name": product_name}, self._get(f"/v1/retail/inventory/{product_id}"),
        )

    def inventory(self, product_id: str) -> RetailSnapshot:
        payload = self._get(f"/v1/retail/inventory/{product_id}")
        return self._inventory_payload(payload.get("product"), payload)

    @staticmethod
    def _inventory_payload(product: dict, payload: dict) -> RetailSnapshot:
        try:
            meta = payload.get("meta", {})
            stores = tuple(StoreInventory(
                store_id=str(row["storeId"]), store_name=str(row["storeName"]), district=str(row["district"]),
                address=str(row["address"]), distance_meters=int(row["distanceMeters"]),
                capabilities=tuple(str(item) for item in row["capabilities"]), stock=int(row["stock"]),
            ) for row in payload["data"])
            return RetailSnapshot(
                product=RetailProduct(id=str(product["id"]), name=str(product["name"])), stores=stores,
                data_source=str(meta.get("dataSource", "upstream")), as_of=str(meta.get("asOf", "unknown")),
                connector_mode="http",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RetailConnectorError("上游庫存回應不符合契約") from exc


class FallbackRetailConnector:
    def __init__(self, *, primary: RetailConnector, fallback: RetailConnector) -> None:
        self.primary = primary
        self.fallback = fallback

    @staticmethod
    def _degraded(snapshot: RetailSnapshot, error: RetailConnectorError) -> RetailSnapshot:
        return replace(snapshot, data_source="competition_seed_offline_fallback",
                       connector_mode="offline_fallback", degraded_reason=str(error))

    def lookup(self, query: str) -> RetailSnapshot:
        try:
            return self.primary.lookup(query)
        except RetailConnectorError as error:
            return self._degraded(self.fallback.lookup(query), error)

    def inventory(self, product_id: str) -> RetailSnapshot:
        try:
            return self.primary.inventory(product_id)
        except RetailConnectorError as error:
            return self._degraded(self.fallback.inventory(product_id), error)


def build_retail_connector(*, upstream_url: str, timeout_seconds: float) -> RetailConnector:
    """依部署設定組出唯一 connector；HTTP 與 MCP 共用，避免兩處組裝漂移。"""
    fallback = SeedRetailConnector()
    if not upstream_url:
        return fallback
    return FallbackRetailConnector(
        primary=HttpRetailConnector(base_url=upstream_url, timeout_seconds=timeout_seconds),
        fallback=fallback,
    )
