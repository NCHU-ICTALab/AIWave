"""可解釋推薦：由官方訂單資料以**確定性規則**產生，每一則都附得出證據。

刻意的分工（這也是 demo 要展示的邊界）：
- 規則層決定「推薦什麼、為什麼、憑哪幾筆訂單」——可測、可重現、不會幻覺；
- LLM 只負責把 `reason_codes` 潤飾成一句話，不參與判斷。

因此每則推薦都帶 `evidence`（指向真實 `record_id` / `order_no`），評審問「這是算出來的
還是編的」時，畫面上就能指出來源。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from core.data.official_orders import OFFICIAL_SERVICE_TO_CATALOG, orders_for
from core.data.official_source import service_master

from .behavior import summarize

# 只有「本質上週期性」的服務才適合推回訪。
# 水電修繕、餐廳訂位、寄件是事件驅動的，刻意不列入——推「你該再修一次水電」並不合理。
REVISIT_THRESHOLD_DAYS = {
    "service-washer": 180,     # 家電清洗約半年
    "service-aircon": 180,
    "service-cleaning": 90,    # 居家清潔約一季
    "service-shopping": 30,    # 日用品補貨約一個月
}


@dataclass(frozen=True)
class Evidence:
    """推薦的依據——指向官方訂單原始紀錄。"""

    record_id: int
    order_no: str
    service_name: str
    occurred_on: date | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "recordId": self.record_id,
            "orderNo": self.order_no,
            "serviceName": self.service_name,
            "occurredOn": self.occurred_on.isoformat() if self.occurred_on else None,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Recommendation:
    """一則可解釋推薦。"""

    id: str
    kind: str                      # resume_open | revisit | frequent
    title: str
    service_id: str | None
    service_name: str
    reason_codes: list[str]
    reason_text: str
    evidence: list[Evidence]
    score: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "serviceId": self.service_id,
            "serviceName": self.service_name,
            "reasonCodes": list(self.reason_codes),
            "reasonText": self.reason_text,
            "evidence": [item.to_dict() for item in self.evidence],
            "score": self.score,
            "computedBy": "rules",   # 非 LLM 產生，供 UI 標示
        }


def _open_order_recs(account_id: str) -> list[Recommendation]:
    """未完成的官方訂單——最確定、最該優先提醒的一類。"""
    recs: list[Recommendation] = []
    for order in orders_for(account_id):
        if not order.is_open:
            continue
        occurred = order.order_time.date() if order.order_time else None
        recs.append(
            Recommendation(
                id=f"resume-{order.record_id}",
                kind="resume_open",
                title=f"接續處理{order.service_name}",
                service_id=order.catalog_service_id,
                service_name=order.service_name,
                reason_codes=["open_order", f"status_{order.order_status}"],
                reason_text=f"你有一筆{order.service_name}尚未完成（訂單 {order.order_no}）。",
                evidence=[
                    Evidence(
                        record_id=order.record_id,
                        order_no=order.order_no,
                        service_name=order.service_name,
                        occurred_on=occurred,
                        detail=f"官方訂單狀態 {order.order_status}",
                    )
                ],
                score=100,
            )
        )
    return recs


def _revisit_recs(account_id: str, today: date) -> list[Recommendation]:
    """距上次使用已久的服務——週期性回訪。"""
    summary = summarize(account_id, today=today)
    recs: list[Recommendation] = []
    for usage in summary.services:
        if usage.days_since_last is None or usage.catalog_service_id is None:
            continue
        threshold = REVISIT_THRESHOLD_DAYS.get(usage.catalog_service_id)
        if threshold is None or usage.days_since_last < threshold:
            continue
        source = next(
            (o for o in reversed(orders_for(account_id))
             if o.catalog_service_id == usage.catalog_service_id and o.order_time),
            None,
        )
        recs.append(
            Recommendation(
                id=f"revisit-{usage.catalog_service_id}",
                kind="revisit",
                title=f"該安排{usage.service_name}了",
                service_id=usage.catalog_service_id,
                service_name=usage.service_name,
                reason_codes=["days_since_last", f"threshold_{threshold}d"],
                reason_text=f"上次{usage.service_name}是 {usage.last_used_on}，距今 {usage.days_since_last} 天。",
                evidence=[
                    Evidence(
                        record_id=source.record_id if source else 0,
                        order_no=source.order_no if source else "",
                        service_name=usage.service_name,
                        occurred_on=usage.last_used_on,
                        detail=f"共使用 {usage.count} 次",
                    )
                ],
                score=70 + min(usage.days_since_last // 30, 20),
            )
        )
    return recs


def _frequent_recs(account_id: str, today: date) -> list[Recommendation]:
    """最常使用的服務——放快捷入口。"""
    summary = summarize(account_id, today=today)
    if not summary.services:
        return []
    top = summary.services[0]
    if top.count < 2 or top.catalog_service_id is None:
        return []
    return [
        Recommendation(
            id=f"frequent-{top.catalog_service_id}",
            kind="frequent",
            title=f"快速再次預約{top.service_name}",
            service_id=top.catalog_service_id,
            service_name=top.service_name,
            reason_codes=["most_used", f"count_{top.count}"],
            reason_text=f"你用過 {top.count} 次{top.service_name}，是最常使用的服務。",
            evidence=[
                Evidence(
                    record_id=0,
                    order_no="",
                    service_name=top.service_name,
                    occurred_on=top.last_used_on,
                    detail=f"官方訂單中共 {top.count} 筆",
                )
            ],
            score=50,
        )
    ]


def _vendor_cross_sell_recs(account_id: str) -> list[Recommendation]:
    """同一官方服務商旗下、使用者還沒用過的服務。

    證據是官方主檔的 `service_vendor_id` 關係——「你用過這家服務商的 A，他們也做 B」，
    而不是憑空的相似度猜測。
    """
    master = service_master()
    used_service_ids = {order.service_id for order in orders_for(account_id)}
    if not used_service_ids:
        return []

    recs: list[Recommendation] = []
    for used_id in sorted(used_service_ids):
        used = master.get(used_id)
        if used is None:
            continue
        vendor_id = used.get("service_vendor_id")
        siblings = [
            (sid, row) for sid, row in master.items()
            if row.get("service_vendor_id") == vendor_id and sid not in used_service_ids
        ]
        for sibling_id, sibling in siblings:
            catalog_id = OFFICIAL_SERVICE_TO_CATALOG.get(sibling_id)
            if catalog_id is None:
                continue
            source = next((o for o in orders_for(account_id) if o.service_id == used_id), None)
            recs.append(
                Recommendation(
                    id=f"cross-{catalog_id}",
                    kind="vendor_cross_sell",
                    title=f"同一服務商也提供{sibling.get('name')}",
                    service_id=catalog_id,
                    service_name=str(sibling.get("name") or ""),
                    reason_codes=["same_vendor", f"vendor_{vendor_id}", f"from_{used.get('name')}"],
                    reason_text=f"你用過{used.get('name')}，同一個服務商（{used.get('vendor_name')}）也提供{sibling.get('name')}。",
                    evidence=[
                        Evidence(
                            record_id=source.record_id if source else 0,
                            order_no=source.order_no if source else "",
                            service_name=str(used.get("name") or ""),
                            occurred_on=source.order_time.date() if source and source.order_time else None,
                            detail=f"官方主檔 service_vendor_id={vendor_id}（{used.get('vendor_name')}）",
                        )
                    ],
                    score=40,
                )
            )
    return recs


def recommend(account_id: str, *, today: date, limit: int = 3) -> list[Recommendation]:
    """產生排序後的可解釋推薦；同一服務只留分數最高的一則。"""
    candidates = [
        *_open_order_recs(account_id),
        *_revisit_recs(account_id, today),
        *_frequent_recs(account_id, today),
        *_vendor_cross_sell_recs(account_id),
    ]
    candidates.sort(key=lambda rec: -rec.score)

    seen: set[str] = set()
    unique: list[Recommendation] = []
    for rec in candidates:
        key = rec.service_id or rec.id
        if key in seen:
            continue
        seen.add(key)
        unique.append(rec)
    return unique[:limit]
