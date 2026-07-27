"""超商生態查詢的 deterministic connector 與候補 repository。

競賽尚未取得即時門市 API，因此庫存與能力資料均帶 `competition_seed`，但候補狀態
寫入平台自己的 SQLite，並非前端假資料。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path


STORES = (
    {
        "id": "qingchuan",
        "storeName": "7-ELEVEN 晴川門市",
        "district": "大同區",
        "address": "台北市大同區民權西路 100 號",
        "capabilities": ["列印", "取貨", "寄件", "ATM", "CITY CAFE"],
        "distanceMeters": 280,
        "inventory": {"limited-cup": 0, "tissue-pack": 8},
    },
    {
        "id": "zhongxing",
        "storeName": "7-ELEVEN 中興門市",
        "district": "中山區",
        "address": "台北市中山區中山北路二段 88 號",
        "capabilities": ["列印", "取貨", "寄件", "ATM", "CITY CAFE"],
        "distanceMeters": 920,
        "inventory": {"limited-cup": 12, "tissue-pack": 4},
    },
    {
        "id": "minsheng",
        "storeName": "7-ELEVEN 民生門市",
        "district": "大同區",
        "address": "台北市大同區民生西路 210 號",
        "capabilities": ["取貨", "ATM", "CITY CAFE"],
        "distanceMeters": 510,
        "inventory": {"limited-cup": 3, "tissue-pack": 10},
    },
)

PRODUCTS = {
    "limited-cup": {"name": "吉伊卡哇限定杯", "keywords": ("吉伊卡哇", "限定杯", "聯名杯")},
    "tissue-pack": {"name": "舒適衛生紙補貨組", "keywords": ("衛生紙", "補貨", "日用品")},
}


class SqliteRetailRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_watches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    store_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(account_id, product_id, store_id)
                )
                """
            )

    def watch(self, account_id: str, product_id: str, store_id: str) -> dict:
        timestamp = self._now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO stock_watches (account_id, product_id, store_id, status, created_at)
                   VALUES (?, ?, ?, 'watching', ?)
                   ON CONFLICT(account_id, product_id, store_id) DO UPDATE SET status = 'watching'""",
                (account_id, product_id, store_id, timestamp),
            )
        return self._record(account_id, product_id, store_id)

    def _record(self, account_id: str, product_id: str, store_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM stock_watches WHERE account_id = ? AND product_id = ? AND store_id = ?",
                (account_id, product_id, store_id),
            ).fetchone()
        assert row is not None
        return {
            "id": row["id"],
            "accountId": row["account_id"],
            "productId": row["product_id"],
            "productName": PRODUCTS[row["product_id"]]["name"],
            "storeId": row["store_id"],
            "storeName": next(store["storeName"] for store in STORES if store["id"] == row["store_id"]),
            "status": row["status"],
            "createdAt": row["created_at"],
        }

    def list_for(self, account_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT product_id, store_id FROM stock_watches WHERE account_id = ? AND status = 'watching' ORDER BY id",
                (account_id,),
            ).fetchall()
        return [self._record(account_id, row["product_id"], row["store_id"]) for row in rows]


class RetailService:
    def __init__(self, repository: SqliteRetailRepository) -> None:
        self.repository = repository

    @staticmethod
    def _product(query: str) -> tuple[str, dict]:
        normalized = query.strip().lower()
        for product_id, product in PRODUCTS.items():
            if product["name"].lower() in normalized or any(word.lower() in normalized for word in product["keywords"]):
                return product_id, product
        raise ValueError("目前找不到這項商品，請改用商品名稱或聯名關鍵字")

    def search(self, *, query: str, district: str | None = None, capability: str | None = None) -> dict:
        product_id, product = self._product(query)

        def eligible(store: dict) -> bool:
            return capability is None or capability in store["capabilities"]

        def view(store: dict) -> dict:
            return {
                "storeId": store["id"],
                "storeName": store["storeName"],
                "district": store["district"],
                "address": store["address"],
                "distanceMeters": store["distanceMeters"],
                "capabilities": list(store["capabilities"]),
                "stock": store["inventory"].get(product_id, 0),
                "productId": product_id,
                "productName": product["name"],
            }

        exact = [view(store) for store in STORES if eligible(store) and store["district"] == district and store["inventory"].get(product_id, 0) > 0]
        alternatives = [view(store) for store in STORES if eligible(store) and store["district"] != district and store["inventory"].get(product_id, 0) > 0]
        exact.sort(key=lambda row: row["distanceMeters"])
        alternatives.sort(key=lambda row: row["distanceMeters"])
        unavailable = [view(store) for store in STORES if eligible(store) and store["district"] == district and store["inventory"].get(product_id, 0) == 0]
        return {
            "query": query,
            "product": {"id": product_id, "name": product["name"]},
            "criteria": {"district": district, "capability": capability},
            "exactMatches": exact,
            "alternatives": alternatives,
            "unavailableNearby": unavailable,
            "dataSource": "competition_seed",
            "asOf": "2026-07-25T09:00:00+08:00",
        }

    def join_waitlist(self, account_id: str, *, product_id: str, store_id: str) -> dict:
        if product_id not in PRODUCTS:
            raise ValueError("查無商品")
        store = next((item for item in STORES if item["id"] == store_id), None)
        if store is None:
            raise ValueError("查無門市")
        if store["inventory"].get(product_id, 0) > 0:
            raise ValueError("這間門市目前有庫存，可直接前往，不需要加入候補")
        return self.repository.watch(account_id, product_id, store_id)

    def list_watches(self, account_id: str) -> list[dict]:
        return self.repository.list_for(account_id)
