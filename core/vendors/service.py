"""廠商媒合與履約服務；Web、AI、MCP 共用這一層。"""

from __future__ import annotations

from typing import Any, Callable

from core.matching import SLOTS, match as seed_match

from .client import VendorClient, VendorClientError


class VendorService:
    def __init__(self, client: VendorClient, *, fallback_matcher: Callable[..., Any] = seed_match) -> None:
        self.client = client
        self.fallback_matcher = fallback_matcher

    @staticmethod
    def _score(
        vendor: dict[str, Any], offering: dict[str, Any], *, has_region: bool,
        budget: int | None, slot: str | None, urgent: bool,
    ) -> dict[str, Any]:
        reasons: list[dict[str, Any]] = []
        concerns: list[str] = []
        score = 0
        if has_region:
            reasons.append({"code": "coverage", "label": "服務據點涵蓋你的地區", "points": 20})
            score += 20
        rating = float(vendor["rating"])
        rating_points = max(0, round((rating - 4.0) * 20))
        reasons.append({
            "code": "rating", "label": f"競賽情境評價 {rating}（{vendor['reviewCount']} 則）",
            "points": rating_points,
        })
        score += rating_points
        price = int(offering["basePrice"])
        if budget is not None:
            if price <= budget:
                points = 25 if budget and budget - price >= budget * 0.2 else 15
                reasons.append({"code": "budget", "label": f"展示參考價 NT${price} 在預算內", "points": points})
                score += points
            else:
                concerns.append(f"展示參考價 NT${price}，超出預算 NT${price - budget}")
                score -= 15
        slots = [str(item) for item in offering["slots"]]
        if slot:
            if slot in slots:
                reasons.append({"code": "slot", "label": f"可配合{SLOTS.get(slot, slot)}", "points": 20})
                score += 20
            else:
                concerns.append(f"無法配合{SLOTS.get(slot, slot)}")
                score -= 20
        if urgent:
            if bool(vendor["supportsUrgent"]) and bool(offering.get("supportsUrgent")):
                reasons.append({"code": "urgent", "label": "可提出加急需求", "points": 25})
                score += 25
            else:
                concerns.append("不提供加急，需照常排程")
                score -= 25
        return {
            "vendorId": vendor["id"], "vendorName": vendor["name"], "intro": vendor["summary"],
            "rating": rating, "reviewCount": int(vendor["reviewCount"]),
            "supportsUrgent": bool(vendor["supportsUrgent"]), "basePrice": price,
            "slots": slots, "slotLabels": [SLOTS.get(item, item) for item in slots],
            "score": score, "reasons": reasons, "concerns": concerns, "computedBy": "rules",
            "source": vendor["source"],
        }

    def match(
        self, service_id: str, *, county_code: str | None = None, district_code: str | None = None,
        budget: int | None = None, slot: str | None = None, urgent: bool = False, limit: int = 3,
    ) -> dict[str, Any]:
        try:
            vendor_payload = self.client.search_vendors(
                serviceId=service_id, countyCode=county_code, districtCode=district_code,
            )
            offering_payload = self.client.list_offerings(serviceId=service_id)
            offering_by_vendor = {item["vendorId"]: item for item in offering_payload["data"]}
            rows = [self._score(
                vendor, offering_by_vendor[vendor["id"]], has_region=county_code is not None,
                budget=budget, slot=slot, urgent=urgent,
            ) for vendor in vendor_payload["data"] if vendor["id"] in offering_by_vendor]
            rows.sort(key=lambda item: (-item["score"], -item["rating"], item["vendorId"]))
            meta = vendor_payload["meta"]
            for row in rows:
                row.update({
                    "dataSource": meta["dataSource"], "connectorMode": self.client.connector_mode,
                    "degradedReason": None,
                })
            return {"vendors": rows[:limit], "meta": {
                **meta, "connectorMode": self.client.connector_mode, "degradedReason": None,
            }}
        except VendorClientError as error:
            fallback = self.fallback_matcher(
                service_id, county_code=county_code, district_code=district_code,
                budget=budget, slot=slot, urgent=urgent, limit=limit,
            )
            rows = []
            for item in fallback:
                row = item.to_dict()
                row.update({
                    "dataSource": "competition_seed_offline_fallback",
                    "connectorMode": "offline_fallback", "degradedReason": str(error),
                })
                rows.append(row)
            return {"vendors": rows, "meta": {
                "dataSource": "competition_seed_offline_fallback", "connectorMode": "offline_fallback",
                "degradedReason": str(error),
            }}

    def get_availability(self, **kwargs: Any) -> dict[str, Any]:
        return self.client.get_availability(**kwargs)

    def create_inquiry(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self.client.create_inquiry(payload, idempotency_key=idempotency_key)

    def list_inquiries(self, **criteria: Any) -> dict[str, Any]:
        return self.client.list_inquiries(**criteria)

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any]:
        return self.client.get_inquiry(inquiry_id)

    def create_quote(self, inquiry_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self.client.create_quote(inquiry_id, payload, idempotency_key=idempotency_key)

    def list_quotes(self, inquiry_id: str) -> dict[str, Any]:
        return self.client.list_quotes(inquiry_id)

    def create_order(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self.client.create_order(payload, idempotency_key=idempotency_key)

    def list_orders(self, **criteria: Any) -> dict[str, Any]:
        return self.client.list_orders(**criteria)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self.client.get_order(order_id)

    def append_order_event(self, order_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self.client.append_order_event(order_id, payload, idempotency_key=idempotency_key)
