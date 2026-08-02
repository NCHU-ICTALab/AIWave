"""Deterministic reachability seam for the v4 Demo.

The fixed provider is intentionally data-driven.  It cannot claim a venue
coordinate, live traffic, or navigation until a reviewed GeoJSON fixture is
provided.  Provider Service Area is a separate decision and never falls back
to distance from a member origin.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class ReachabilityError(ValueError):
    pass


class ReachabilityProvider(Protocol):
    def calculate(self, *, origin_id: str, travel_mode: str, threshold_minutes: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ReachabilityArea:
    origin_id: str
    travel_mode: str
    threshold_minutes: int
    geometry: dict[str, Any]
    eligible_location_ids: list[str]
    source: str
    calculated_at: str | None
    is_demo: bool
    real_time: bool
    navigation: bool
    locations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "originId": self.origin_id,
            "travelMode": self.travel_mode,
            "thresholdMinutes": self.threshold_minutes,
            "geometry": self.geometry,
            "eligibleLocationIds": self.eligible_location_ids,
            "locations": self.locations,
            "source": self.source,
            "calculatedAt": self.calculated_at,
            "isDemo": self.is_demo,
            "realTime": self.real_time,
            "navigation": self.navigation,
        }


class SeededGeoJsonReachabilityProvider:
    ALLOWED_MODES = {"pedestrian", "scooter"}
    ALLOWED_THRESHOLDS = {10, 15}

    def __init__(self, path: str | Path, *, now: Any | None = None) -> None:
        self.path = Path(path)
        self._now = now
        self._metadata: dict[str, Any] = {}
        self._features: list[dict[str, Any]] = []
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ReachabilityError(f"GeoJSON 無法讀取: {self.path}") from exc
            if payload.get("type") != "FeatureCollection":
                raise ReachabilityError("Reachability GeoJSON 必須是 FeatureCollection")
            self._metadata = dict(payload.get("metadata") or {})
            self._features = [feature for feature in payload.get("features") or [] if isinstance(feature, dict)]

    def calculate(self, *, origin_id: str, travel_mode: str, threshold_minutes: int) -> dict[str, Any]:
        if travel_mode not in self.ALLOWED_MODES:
            raise ReachabilityError("只支援 pedestrian 與 scooter，不支援 bicycle routing")
        if threshold_minutes not in self.ALLOWED_THRESHOLDS:
            raise ReachabilityError("時間門檻只支援 10 或 15 分鐘")
        feature = next((item for item in self._features if (
            (item.get("properties") or {}).get("originId") == origin_id
            and (item.get("properties") or {}).get("travelMode") == travel_mode
            and int((item.get("properties") or {}).get("thresholdMinutes", 0)) == threshold_minutes
        )), None)
        if feature is None:
            raise ReachabilityError("目前沒有經確認的生活圈 GeoJSON 資料")
        properties = dict(feature.get("properties") or {})
        eligible = properties.get("eligibleLocationIds") or []
        if not isinstance(eligible, list) or any(not isinstance(value, str) for value in eligible):
            raise ReachabilityError("GeoJSON eligibleLocationIds 形狀錯誤")
        return {
            "originId": origin_id,
            "travelMode": travel_mode,
            "thresholdMinutes": threshold_minutes,
            "geometry": feature.get("geometry"),
            "eligibleLocationIds": eligible,
            "source": self._metadata.get("source") or str(self.path),
            "calculatedAt": self._now() if callable(self._now) else None,
            "isDemo": bool(self._metadata.get("isDemo", True)),
            "realTime": bool(self._metadata.get("realTime", False)),
            "navigation": bool(self._metadata.get("navigation", False)),
        }


class ReachabilityService:
    def __init__(self, provider: ReachabilityProvider, *, catalog: Any) -> None:
        self.provider = provider
        self.catalog = catalog

    def area(self, *, origin_id: str, travel_mode: str, threshold_minutes: int) -> ReachabilityArea:
        raw = self.provider.calculate(
            origin_id=origin_id, travel_mode=travel_mode, threshold_minutes=threshold_minutes,
        )
        eligible_ids = list(raw.get("eligibleLocationIds") or [])
        locations: list[dict[str, Any]] = []
        seen_location_ids: set[str] = set()
        # Catalog is the authority for names and Provider mapping.  Geometry can
        # only filter this list; it cannot invent a location.
        for provider in self.catalog.list_providers():
            try:
                detail = self.catalog.get_provider(provider["id"])
            except Exception:
                continue
            for location in detail.get("locations") or []:
                if location.get("id") in eligible_ids and location.get("id") not in seen_location_ids:
                    locations.append({**location, "providerName": provider.get("name")})
                    seen_location_ids.add(str(location["id"]))
        eligible_ids = [location["id"] for location in locations]
        return ReachabilityArea(
            origin_id=str(raw["originId"]), travel_mode=str(raw["travelMode"]),
            threshold_minutes=int(raw["thresholdMinutes"]), geometry=dict(raw.get("geometry") or {}),
            eligible_location_ids=eligible_ids, source=str(raw.get("source") or "unknown"),
            calculated_at=raw.get("calculatedAt"), is_demo=bool(raw.get("isDemo", True)),
            real_time=bool(raw.get("realTime", False)), navigation=bool(raw.get("navigation", False)),
            locations=locations,
        )

    def provider_service_area(self, provider_id: str, *, county: str, district: str) -> dict[str, Any]:
        try:
            provider = self.catalog.get_provider(provider_id)
        except Exception as exc:
            raise ReachabilityError("查無 Provider，無法判斷到府服務範圍") from exc
        area = provider.get("serviceArea") or provider.get("service_area")
        if not isinstance(area, dict):
            return {
                "providerId": provider_id, "decision": "provider_service_area",
                "eligible": False, "reason": "Provider 沒有提供可驗證的到府服務範圍", "source": "catalog",
            }
        counties = {str(value) for value in area.get("counties") or area.get("countyNames") or []}
        districts = {str(value) for value in area.get("districts") or area.get("districtNames") or []}
        eligible = (not counties or county in counties) and (not districts or district in districts)
        return {
            "providerId": provider_id, "decision": "provider_service_area", "eligible": eligible,
            "county": county, "district": district, "serviceArea": area, "source": "catalog",
        }
