"""行為軌跡與消費摘要（全部由官方訂單資料算出，無寫死數字）。

詞彙（見 CONTEXT.md）：
- **行為指紋**＝把散落訂單認回同一個人的身分解析（此處用官方 `inbr_account_id`）。
- **行為軌跡**＝解析後依時間排出的跨服務事件序列。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from core.data.official_orders import OfficialOrder, orders_for


@dataclass(frozen=True)
class TrailEvent:
    """行為軌跡上的一個事件。"""

    occurred_on: date | None
    service_name: str
    catalog_service_id: str | None
    order_no: str
    record_id: int
    status: str
    amount: float
    item_name: str
    outcome: str  # completed | open | cancelled

    def to_dict(self) -> dict:
        return {
            "occurredOn": self.occurred_on.isoformat() if self.occurred_on else None,
            "serviceName": self.service_name,
            "serviceId": self.catalog_service_id,
            "orderNo": self.order_no,
            "recordId": self.record_id,
            "status": self.status,
            "amount": round(self.amount),
            "itemName": self.item_name,
            "outcome": self.outcome,
        }


@dataclass(frozen=True)
class ServiceUsage:
    """單一服務的使用情形。"""

    catalog_service_id: str | None
    service_name: str
    count: int
    last_used_on: date | None
    days_since_last: int | None
    total_amount: float

    def to_dict(self) -> dict:
        return {
            "serviceId": self.catalog_service_id,
            "serviceName": self.service_name,
            "count": self.count,
            "lastUsedOn": self.last_used_on.isoformat() if self.last_used_on else None,
            "daysSinceLast": self.days_since_last,
            "totalAmount": round(self.total_amount),
        }


@dataclass
class BehaviorSummary:
    """一位使用者的跨服務行為摘要。"""

    account_id: str
    total_orders: int = 0
    completed_orders: int = 0
    open_orders: int = 0
    cancelled_orders: int = 0
    total_spend: float = 0.0
    earned_points: float = 0.0
    first_activity: date | None = None
    last_activity: date | None = None
    services: list[ServiceUsage] = field(default_factory=list)

    @property
    def distinct_services(self) -> int:
        return len(self.services)

    def to_dict(self) -> dict:
        return {
            "accountId": self.account_id,
            "totalOrders": self.total_orders,
            "completedOrders": self.completed_orders,
            "openOrders": self.open_orders,
            "cancelledOrders": self.cancelled_orders,
            "distinctServices": self.distinct_services,
            "totalSpend": round(self.total_spend),
            "earnedPoints": round(self.earned_points),
            "firstActivity": self.first_activity.isoformat() if self.first_activity else None,
            "lastActivity": self.last_activity.isoformat() if self.last_activity else None,
            "services": [usage.to_dict() for usage in self.services],
            "source": "official_order_record",
        }


def _as_date(value: datetime | None) -> date | None:
    return value.astimezone(timezone.utc).date() if value else None


def _outcome(order: OfficialOrder) -> str:
    if order.is_completed:
        return "completed"
    if order.is_cancelled:
        return "cancelled"
    return "open"


def build_trail(account_id: str) -> list[TrailEvent]:
    """回傳該帳號的行為軌跡（舊到新）。"""
    return [
        TrailEvent(
            occurred_on=_as_date(order.order_time),
            service_name=order.service_name,
            catalog_service_id=order.catalog_service_id,
            order_no=order.order_no,
            record_id=order.record_id,
            status=order.order_status,
            amount=order.final_amount,
            item_name=order.item_name,
            outcome=_outcome(order),
        )
        for order in orders_for(account_id)
    ]


def summarize(account_id: str, *, today: date) -> BehaviorSummary:
    """由官方訂單算出跨服務摘要；`today` 用於計算距上次使用天數。"""
    orders = orders_for(account_id)
    summary = BehaviorSummary(account_id=account_id, total_orders=len(orders))

    grouped: dict[str, list[OfficialOrder]] = {}
    for order in orders:
        occurred = _as_date(order.order_time)
        if order.is_completed:
            summary.completed_orders += 1
            # 只把已完成訂單計入消費，取消/退款不算
            summary.total_spend += order.final_amount
            summary.earned_points += order.earn_points
        elif order.is_cancelled:
            summary.cancelled_orders += 1
        else:
            summary.open_orders += 1

        if occurred:
            if summary.first_activity is None or occurred < summary.first_activity:
                summary.first_activity = occurred
            if summary.last_activity is None or occurred > summary.last_activity:
                summary.last_activity = occurred

        grouped.setdefault(order.service_name, []).append(order)

    usages: list[ServiceUsage] = []
    for service_name, service_orders in grouped.items():
        dates = [d for d in (_as_date(o.order_time) for o in service_orders) if d is not None]
        last_used = max(dates) if dates else None
        usages.append(
            ServiceUsage(
                catalog_service_id=service_orders[0].catalog_service_id,
                service_name=service_name,
                count=len(service_orders),
                last_used_on=last_used,
                days_since_last=(today - last_used).days if last_used else None,
                total_amount=sum(o.final_amount for o in service_orders if o.is_completed),
            )
        )
    usages.sort(key=lambda usage: (-usage.count, usage.service_name))
    summary.services = usages
    return summary
