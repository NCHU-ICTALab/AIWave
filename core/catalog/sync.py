"""把各 Provider connector 的 catalog/availability 同步進平台投影。

同步是顯式操作(啟動時或 operator 觸發);失敗誠實回報 per-provider 狀態,
不會讓一家 upstream 掛掉拖垮整個探索頁。
"""

from __future__ import annotations

from typing import Any, Mapping

from core.providers.connector import ProviderConnector, ProviderConnectorError

from .repository import SqliteCatalogRepository


class CatalogSyncService:
    def __init__(
        self,
        repository: SqliteCatalogRepository,
        *,
        connectors: Mapping[str, ProviderConnector],
    ) -> None:
        self.repository = repository
        self.connectors = dict(connectors)

    def sync_provider(self, provider_id: str) -> dict[str, Any]:
        connector = self.connectors.get(provider_id)
        if connector is None:
            return {"providerId": provider_id, "status": "unknown_provider"}
        try:
            catalog = connector.get_catalog()
            slots = connector.get_availability()
        except ProviderConnectorError as exc:
            return {"providerId": provider_id, "status": "failed", "error": str(exc)}
        self.repository.replace_provider(
            catalog, slots, seed_version=str(catalog.get("seedVersion", "unknown"))
        )
        return {
            "providerId": provider_id, "status": "synced",
            "seedVersion": catalog.get("seedVersion"),
            "offerings": len(catalog.get("offerings", [])),
            "slots": len(slots),
        }

    def sync_all(self) -> dict[str, Any]:
        results = [self.sync_provider(provider_id) for provider_id in sorted(self.connectors)]
        synced = sum(1 for item in results if item["status"] == "synced")
        return {
            "status": "ok" if synced == len(results) else ("partial" if synced else "failed"),
            "providers": results,
        }
