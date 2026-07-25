"""官方訂單範例資料（`mms_order_record`）載入與正規化。

這是命題方提供的真實交易紀錄，用來支撐行為軌跡與可解釋推薦——推薦必須指得出
是哪幾筆official 訂單造成的，而不是模型憑空生成。

**行為指紋**（身分解析）與**行為軌跡**（時間序列）在此分離：
- 指紋鍵優先用 `inbr_account_id`（官方資料 100% 有值）；
- `member_name_hash` 是官方跨表比對用的雜湊，資料中有部分為空，僅作輔助。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from .official_source import RAW_DATA, load_rows, service_master

_ORDERS = RAW_DATA / "order_record範例資料.json"

# 官方 cms_homepage_service.id → 本專案服務目錄 id
OFFICIAL_SERVICE_TO_CATALOG: dict[int, str] = {
    1: "service-washer",      # 洗衣機清洗
    2: "service-aircon",      # 冷氣清洗
    3: "service-shipping",    # 寄件服務
    4: "service-cleaning",    # 專業清潔
    5: "service-housework",   # 計時家事服務
    9: "service-restaurant",  # 餐廳訂位
    16: "service-delivery",   # 美食外送
    17: "service-repair",     # 水電修繕
    18: "service-shopping",   # 商城購物（官方主檔未列，訂單資料以 18 出現）
}

# 官方 order_status：尚未完成、等待使用者或廠商動作的階段
OPEN_STATUSES = {"11", "12", "13", "01", "02", "03", "04"}
COMPLETED_STATUSES = {"70", "80"}
CANCELLED_STATUSES = {"90", "98", "99"}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _item_name(order_items: object) -> str:
    """訂單品項名稱因服務類型而異（官方各服務商自訂 JSON 結構）。"""
    if isinstance(order_items, list) and order_items:
        first = order_items[0]
        if isinstance(first, dict):
            return str(first.get("item_name") or first.get("name") or first.get("itemName") or "")
    if isinstance(order_items, dict):
        nested = order_items.get("orderItems")
        if isinstance(nested, list) and nested and isinstance(nested[0], dict):
            return str(nested[0].get("itemName") or nested[0].get("item_name") or "")
        goods = order_items.get("goods")
        if isinstance(goods, list) and goods and isinstance(goods[0], dict):
            return str(goods[0].get("title") or "")
    return ""


@dataclass(frozen=True)
class OfficialOrder:
    """一筆官方訂單紀錄（正規化後）。"""

    record_id: int
    order_no: str
    account_id: str
    member_hash: str | None
    service_id: int
    service_name: str
    catalog_service_id: str | None
    order_type: str
    order_status: str
    order_time: datetime | None
    final_amount: float
    earn_points: float
    item_name: str

    @property
    def is_open(self) -> bool:
        return self.order_status in OPEN_STATUSES

    @property
    def is_completed(self) -> bool:
        return self.order_status in COMPLETED_STATUSES

    @property
    def is_cancelled(self) -> bool:
        return self.order_status in CANCELLED_STATUSES


def _to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


@lru_cache(maxsize=1)
def load_orders() -> tuple[OfficialOrder, ...]:
    """讀入官方訂單範例，依時間排序。"""
    master = service_master()
    orders: list[OfficialOrder] = []
    for row in load_rows(_ORDERS):
        if row.get("is_deleted"):
            continue
        service_id = row.get("service_id")
        if not isinstance(service_id, int):
            continue
        orders.append(
            OfficialOrder(
                record_id=int(row.get("record_id", 0)),
                order_no=str(row.get("order_no") or ""),
                account_id=str(row.get("inbr_account_id") or ""),
                member_hash=row.get("member_name_hash") or None,
                service_id=service_id,
                service_name=str(master.get(service_id, {}).get("name") or _fallback_name(service_id)),
                catalog_service_id=OFFICIAL_SERVICE_TO_CATALOG.get(service_id),
                order_type=str(row.get("order_type") or ""),
                order_status=str(row.get("order_status") or ""),
                order_time=_parse_time(row.get("order_time")),
                final_amount=_to_float(row.get("final_amount")),
                earn_points=_to_float(row.get("earn_points")),
                item_name=_item_name(row.get("order_items")),
            )
        )
    orders.sort(key=lambda o: o.order_time or datetime.min.replace(tzinfo=timezone.utc))
    return tuple(orders)


def _fallback_name(service_id: int) -> str:
    """官方主檔未列的服務（如商城購物 18）用目錄名補上。"""
    return {18: "商城購物"}.get(service_id, f"服務 {service_id}")


def list_accounts() -> list[str]:
    """官方資料中出現過的帳號（行為指紋鍵）。"""
    seen: dict[str, None] = {}
    for order in load_orders():
        if order.account_id:
            seen.setdefault(order.account_id, None)
    return list(seen)


def orders_for(account_id: str) -> list[OfficialOrder]:
    """某帳號的訂單，時間由舊到新（＝行為軌跡的原始序列）。"""
    return [order for order in load_orders() if order.account_id == account_id]
