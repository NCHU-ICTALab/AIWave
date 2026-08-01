"""平台側服務目錄投影(Provider / Location / Offering / Resource / Slot)。

Provider 是目錄的權威來源(spec 15 §7);平台保存一份投影讓探索頁
不依賴 upstream 存活,並在 booking 前仍以 connector 現場驗證。
投影是全域資料(不分 DemoWorkspace),reset 時不清除、只重新同步。
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CatalogNotFound(LookupError):
    pass


class SqliteCatalogRepository:
    def __init__(self, path: str | Path, *, now: Callable[[], datetime] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

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
                CREATE TABLE IF NOT EXISTS catalog_providers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    scene TEXT NOT NULL,
                    summary TEXT,
                    rating REAL,
                    review_count INTEGER,
                    placeholder INTEGER NOT NULL DEFAULT 0,
                    source_json TEXT,
                    seed_version TEXT NOT NULL,
                    synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS catalog_locations (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(provider_id) REFERENCES catalog_providers(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS catalog_offerings (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    domain_type TEXT,
                    fulfillment_kind TEXT NOT NULL DEFAULT 'booking',
                    base_price INTEGER NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'TWD',
                    pricing_unit TEXT,
                    cancel_policy_hours INTEGER,
                    description TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(provider_id) REFERENCES catalog_providers(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS catalog_resources (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT,
                    FOREIGN KEY(provider_id) REFERENCES catalog_providers(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS catalog_slots (
                    id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    offering_id TEXT NOT NULL,
                    location_id TEXT,
                    resource_id TEXT,
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    capacity INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(provider_id, id),
                    FOREIGN KEY(provider_id) REFERENCES catalog_providers(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS ix_catalog_slots_lookup
                    ON catalog_slots(provider_id, offering_id, starts_at);
                """
            )

    # ── 寫入(只由 CatalogSyncService 呼叫) ──────────────────────

    def replace_provider(
        self,
        catalog: dict[str, Any],
        slots: list[dict[str, Any]],
        *,
        seed_version: str,
    ) -> dict[str, Any]:
        provider = catalog["provider"]
        provider_id = provider["id"]
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("DELETE FROM catalog_providers WHERE id=?", (provider_id,))
            connection.execute(
                """INSERT INTO catalog_providers
                   (id,name,scene,summary,rating,review_count,placeholder,source_json,seed_version,synced_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    provider_id, provider.get("name", provider_id),
                    provider.get("scene", "other"), provider.get("summary"),
                    provider.get("rating"), provider.get("reviewCount"),
                    1 if provider.get("placeholder") else 0,
                    json.dumps(provider.get("source"), ensure_ascii=False),
                    seed_version, timestamp,
                ),
            )
            for location in catalog.get("locations", []):
                connection.execute(
                    "INSERT INTO catalog_locations (id,provider_id,name,payload_json) VALUES (?,?,?,?)",
                    (
                        location["id"], provider_id, location.get("name", location["id"]),
                        json.dumps(location, ensure_ascii=False),
                    ),
                )
            for offering in catalog.get("offerings", []):
                connection.execute(
                    """INSERT INTO catalog_offerings
                       (id,provider_id,name,domain_type,fulfillment_kind,base_price,currency,
                        pricing_unit,cancel_policy_hours,description,payload_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        offering["id"], provider_id, offering.get("name", offering["id"]),
                        offering.get("domainType"),
                        offering.get("fulfillmentKind", "booking"),
                        int(offering.get("basePrice", 0)),
                        offering.get("currency", "TWD"),
                        offering.get("pricingUnit"),
                        offering.get("cancelPolicyHours"),
                        offering.get("description"),
                        json.dumps(offering, ensure_ascii=False),
                    ),
                )
            for resource in catalog.get("resources", []):
                connection.execute(
                    "INSERT INTO catalog_resources (id,provider_id,name,kind) VALUES (?,?,?,?)",
                    (resource["id"], provider_id, resource.get("name", resource["id"]), resource.get("kind")),
                )
            for slot in slots:
                connection.execute(
                    """INSERT INTO catalog_slots
                       (id,provider_id,offering_id,location_id,resource_id,starts_at,ends_at,status,capacity)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        slot["id"], provider_id, slot["offeringId"], slot.get("locationId"),
                        slot.get("resourceId"), slot["startsAt"], slot["endsAt"],
                        slot.get("status", "available"), int(slot.get("capacity", 1)),
                    ),
                )
        return self.get_provider(provider_id)

    # ── 讀取 ────────────────────────────────────────────

    @staticmethod
    def _provider_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "scene": row["scene"],
            "summary": row["summary"], "rating": row["rating"],
            "reviewCount": row["review_count"],
            "placeholder": bool(row["placeholder"]),
            "source": json.loads(row["source_json"]) if row["source_json"] else None,
            "seedVersion": row["seed_version"], "syncedAt": row["synced_at"],
        }

    @staticmethod
    def _offering_row(row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        return {
            **payload,
            "id": row["id"], "providerId": row["provider_id"], "name": row["name"],
            "domainType": row["domain_type"], "fulfillmentKind": row["fulfillment_kind"],
            "basePrice": row["base_price"], "currency": row["currency"],
            "pricingUnit": row["pricing_unit"], "cancelPolicyHours": row["cancel_policy_hours"],
            "description": row["description"],
        }

    def list_providers(self, *, scene: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM catalog_providers"
        params: tuple[Any, ...] = ()
        if scene:
            query += " WHERE scene=?"
            params = (scene,)
        query += " ORDER BY scene, id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._provider_row(row) for row in rows]

    def get_provider(self, provider_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            provider = connection.execute(
                "SELECT * FROM catalog_providers WHERE id=?", (provider_id,)
            ).fetchone()
            if provider is None:
                raise CatalogNotFound(f"目錄中查無 Provider:{provider_id}")
            locations = connection.execute(
                "SELECT * FROM catalog_locations WHERE provider_id=? ORDER BY id", (provider_id,)
            ).fetchall()
            offerings = connection.execute(
                "SELECT * FROM catalog_offerings WHERE provider_id=? ORDER BY id", (provider_id,)
            ).fetchall()
            resources = connection.execute(
                "SELECT * FROM catalog_resources WHERE provider_id=? ORDER BY id", (provider_id,)
            ).fetchall()
        return {
            **self._provider_row(provider),
            "locations": [json.loads(row["payload_json"]) for row in locations],
            "offerings": [self._offering_row(row) for row in offerings],
            "resources": [
                {"id": row["id"], "providerId": row["provider_id"], "name": row["name"], "kind": row["kind"]}
                for row in resources
            ],
        }

    def get_offering(self, offering_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM catalog_offerings WHERE id=?", (offering_id,)
            ).fetchone()
        if row is None:
            raise CatalogNotFound(f"目錄中查無服務方案:{offering_id}")
        return self._offering_row(row)

    def list_slots(
        self,
        provider_id: str,
        *,
        offering_id: str | None = None,
        starts_after: str | None = None,
        starts_before: str | None = None,
        only_available: bool = True,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM catalog_slots WHERE provider_id=?"
        params: list[Any] = [provider_id]
        if offering_id:
            query += " AND offering_id=?"
            params.append(offering_id)
        if starts_after:
            query += " AND starts_at>=?"
            params.append(starts_after)
        if starts_before:
            query += " AND starts_at<=?"
            params.append(starts_before)
        if only_available:
            query += " AND status='available'"
        query += " ORDER BY starts_at"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "id": row["id"], "providerId": row["provider_id"], "offeringId": row["offering_id"],
                "locationId": row["location_id"], "resourceId": row["resource_id"],
                "startsAt": row["starts_at"], "endsAt": row["ends_at"],
                "status": row["status"], "capacity": row["capacity"],
            }
            for row in rows
        ]

    def health(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT p.id, p.seed_version, p.synced_at,
                          (SELECT COUNT(*) FROM catalog_offerings o WHERE o.provider_id=p.id) AS offerings,
                          (SELECT COUNT(*) FROM catalog_slots s
                             WHERE s.provider_id=p.id AND s.status='available') AS available_slots
                   FROM catalog_providers p ORDER BY p.id"""
            ).fetchall()
        return [
            {
                "providerId": row["id"], "seedVersion": row["seed_version"],
                "syncedAt": row["synced_at"], "offerings": row["offerings"],
                "availableSlots": row["available_slots"],
            }
            for row in rows
        ]
