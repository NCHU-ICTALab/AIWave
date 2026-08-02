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
