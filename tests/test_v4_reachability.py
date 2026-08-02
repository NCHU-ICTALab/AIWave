from __future__ import annotations

import json
from pathlib import Path

import pytest
from datetime import date
from fastapi.testclient import TestClient

from api.app import create_app
from core.reachability import (
    ReachabilityError,
    ReachabilityService,
    SeededGeoJsonReachabilityProvider,
)


def geojson(path: Path) -> None:
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "metadata": {
            "source": "reviewed-demo-fixture",
            "isDemo": True,
            "realTime": False,
            "navigation": False,
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "originId": "venue-demo",
                    "travelMode": "pedestrian",
                    "thresholdMinutes": 10,
                    "eligibleLocationIds": ["loc-a"],
                },
                "geometry": {"type": "Polygon", "coordinates": [[[121.5, 25.0], [121.51, 25.0], [121.51, 25.01], [121.5, 25.0]]]},
            },
            {
                "type": "Feature",
                "properties": {
                    "originId": "venue-demo",
                    "travelMode": "pedestrian",
                    "thresholdMinutes": 15,
                    "eligibleLocationIds": ["loc-a", "loc-b"],
                },
                "geometry": {"type": "Polygon", "coordinates": [[[121.5, 25.0], [121.52, 25.0], [121.52, 25.02], [121.5, 25.0]]]},
            },
            {
                "type": "Feature",
                "properties": {
                    "originId": "venue-demo",
                    "travelMode": "scooter",
                    "thresholdMinutes": 10,
                    "eligibleLocationIds": ["loc-a", "loc-b"],
                },
                "geometry": {"type": "Polygon", "coordinates": [[[121.5, 25.0], [121.53, 25.0], [121.53, 25.03], [121.5, 25.0]]]},
            },
        ],
    }), encoding="utf-8")


class Catalog:
    def list_providers(self, *, scene=None):
        return [{"id": "provider-a"}, {"id": "provider-b"}, {"id": "provider-home"}]

    def get_provider(self, provider_id):
        return {
            "id": provider_id,
            "locations": [
                {"id": "loc-a", "providerId": "provider-a", "name": "門市 A"},
                {"id": "loc-b", "providerId": "provider-b", "name": "門市 B"},
            ] if provider_id != "provider-home" else [],
        }


def test_fixed_geojson_supports_only_supported_modes_and_thresholds(tmp_path: Path) -> None:
    path = tmp_path / "reachability.geojson"
    geojson(path)
    provider = SeededGeoJsonReachabilityProvider(path, now=lambda: "2026-08-01T10:00:00+08:00")
    service = ReachabilityService(provider, catalog=Catalog())

    result = service.area(origin_id="venue-demo", travel_mode="pedestrian", threshold_minutes=15)
    assert result.source == "reviewed-demo-fixture"
    assert result.is_demo is True
    assert result.real_time is False
    assert result.eligible_location_ids == ["loc-a", "loc-b"]
    assert result.geometry["type"] == "Polygon"

    with pytest.raises(ReachabilityError, match="不支援"):
        service.area(origin_id="venue-demo", travel_mode="bicycle", threshold_minutes=10)
    with pytest.raises(ReachabilityError, match="門檻"):
        service.area(origin_id="venue-demo", travel_mode="scooter", threshold_minutes=20)


def test_catalog_locations_are_the_only_locations_in_area(tmp_path: Path) -> None:
    path = tmp_path / "reachability.geojson"
    geojson(path)
    service = ReachabilityService(
        SeededGeoJsonReachabilityProvider(path), catalog=Catalog(),
    )
    result = service.area(origin_id="venue-demo", travel_mode="pedestrian", threshold_minutes=10)
    assert [location["id"] for location in result.locations] == ["loc-a"]


def test_provider_service_area_does_not_use_member_reachability(tmp_path: Path) -> None:
    path = tmp_path / "reachability.geojson"
    geojson(path)
    catalog = Catalog()
    catalog.get_provider = lambda provider_id: {
        "id": provider_id,
        "locations": [],
        "serviceArea": {"counties": ["臺北市"], "districts": ["信義區"]},
    } if provider_id == "provider-home" else Catalog.get_provider(catalog, provider_id)
    service = ReachabilityService(SeededGeoJsonReachabilityProvider(path), catalog=catalog)

    result = service.provider_service_area("provider-home", county="臺北市", district="信義區")
    assert result["eligible"] is True
    assert result["decision"] == "provider_service_area"
    assert result["source"] == "catalog"


def test_seeded_geojson_only_references_locations_that_exist_in_the_catalog() -> None:
    """每個 eligibleLocationIds 都必須在目錄投影裡真的存在。

    這是「地圖上什麼服務都不顯示」的守門測試：`ReachabilityService.area()` 會把
    GeoJSON 的 id 與目錄的 location 取交集，只要 seed 用了舊命名（例如 `loc-02-01`），
    交集就是空的，API 回 `locations: []`，前端就一片空白。
    """
    from fake_upstreams.partner_seed import build_partner_seed

    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "reachability" / "demo.geojson").read_text(encoding="utf-8")
    )
    catalog_location_ids = {
        location["id"]
        for partner in build_partner_seed().values()
        for location in partner["catalog"].get("locations") or []
    }

    for feature in payload["features"]:
        properties = feature["properties"]
        eligible = properties["eligibleLocationIds"]
        unknown = sorted(set(eligible) - catalog_location_ids)
        assert not unknown, (
            f"{properties['travelMode']}/{properties['thresholdMinutes']} 參照了目錄裡沒有的 location: {unknown}"
        )
        assert eligible, "每個門檻至少要有一個據點，否則地圖會是空的"


def test_seeded_geojson_thresholds_are_nested_and_always_include_a_convenience_store() -> None:
    """門檻放寬只能新增據點，而且最小的步行圈就要有小七（社區生活的基本盤）。"""
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "reachability" / "demo.geojson").read_text(encoding="utf-8")
    )
    by_key = {
        (feature["properties"]["travelMode"], feature["properties"]["thresholdMinutes"]): set(
            feature["properties"]["eligibleLocationIds"]
        )
        for feature in payload["features"]
    }
    walkable = by_key[("pedestrian", 10)]
    assert {"loc-711-shop-01", "loc-711-c2c-01"} <= walkable

    for narrow, wide in (
        (("pedestrian", 10), ("pedestrian", 15)),
        (("pedestrian", 15), ("scooter", 10)),
        (("scooter", 10), ("scooter", 15)),
    ):
        assert by_key[narrow] < by_key[wide], f"{wide} 應該是 {narrow} 的嚴格超集"


def test_api_returns_the_seeded_signal_locations_for_the_venue(tmp_path: Path) -> None:
    """端到端：GeoJSON × 目錄的交集不可以是空的，否則前端地圖沒有任何服務點。"""
    from core.providers import StandardProviderConnector
    from fake_upstreams.partner_app import create_partner_fake_app
    from fake_upstreams.partner_seed import DEFAULT_PARTNER_KEYS

    upstream = TestClient(create_partner_fake_app(control_key="aiwave-partner-control"))
    connectors = {
        provider_id: StandardProviderConnector(base_url="http://partner-fake", api_key=key, client=upstream)
        for provider_id, key in DEFAULT_PARTNER_KEYS.items()
    }
    client = TestClient(create_app(
        demo_db_path=tmp_path / "reachability-locations.sqlite3",
        today=date(2026, 8, 1),
        provider_connectors=connectors,
    ))
    synced = client.post("/api/v1/platform/catalog/sync", headers={"Authorization": "Bearer aiwave-admin"})
    assert synced.status_code == 200

    seen: dict[int, set[str]] = {}
    for threshold in (10, 15):
        response = client.get(
            "/api/v1/platform/reachability/area",
            params={
                "originId": "venue-huanan-bank-conference-center",
                "travelMode": "pedestrian",
                "thresholdMinutes": threshold,
            },
            headers={"Authorization": "Bearer aiwave"},
        )
        assert response.status_code == 200
        area = response.json()["data"]
        ids = {location["id"] for location in area["locations"]}
        assert ids, f"步行 {threshold} 分鐘沒有任何據點，地圖會是空的"
        assert ids == set(area["eligibleLocationIds"])
        seen[threshold] = ids

    assert {"loc-711-shop-01", "loc-711-c2c-01"} <= seen[10]
    assert seen[10] < seen[15]


def test_api_exposes_fixed_demo_venue_data_without_claiming_live_navigation(tmp_path: Path) -> None:
    client = TestClient(create_app(demo_db_path=tmp_path / "reachability-api.sqlite3", today=date(2026, 8, 1)))
    response = client.get(
        "/api/v1/platform/reachability/area",
        params={"originId": "venue-huanan-bank-conference-center", "travelMode": "pedestrian", "thresholdMinutes": 10},
        headers={"Authorization": "Bearer aiwave"},
    )
    assert response.status_code == 200
    area = response.json()["data"]
    assert area["isDemo"] is True
    assert area["realTime"] is False
    assert area["navigation"] is False
    assert area["source"] == "競賽 Demo 固定示意資料（非導航）"
    assert area["geometry"]["type"] == "Polygon"
