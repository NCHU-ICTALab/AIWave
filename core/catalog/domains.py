"""六大生活場景的 domain 定義(可擴充,不寫死格數)。

每個 offering 帶 ``domainType``;domain 決定:
- fulfillment 走 Booking(有據點/時段)還是 CommerceOrder(商品下單)
- TaskDraft 送出前的必填欄位
- 對使用者顯示的狀態名稱與時間軸(spec 15 §5:狀態名稱依服務類型定義,
  底層仍是 fulfillment 的單一合法轉移機)

這一層完全確定性,不涉及 LLM。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainSpec:
    domain_type: str
    scene: str                      # food / med / home / move / pre / fun
    display_name: str
    fulfillment_kind: str           # "booking" | "commerce"
    required_fields: tuple[str, ...]
    #: 通用狀態 → 對使用者顯示的名稱
    status_labels: dict[str, str] = field(default_factory=dict)
    #: 正向時間軸(顯示用;取消/例外另計)
    timeline: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


_BOOKING_BASE_LABELS = {
    "pending_provider": "需求送出",
    "confirmed": "已預約",
    "in_service": "服務中",
    "completed": "已完成",
    "cancelled": "已取消",
    "rejected": "廠商婉拒",
    "exception": "履約異常",
}

_COMMERCE_BASE_LABELS = {
    "placed": "收到訂單",
    "accepted": "已接單",
    "preparing": "備貨中",
    "shipped": "已出貨",
    "ready_for_pickup": "可取貨",
    "delivered": "已送達",
    "cancelled": "已取消",
    "payment_failed": "付款失敗",
    "exception": "配送異常",
}


DOMAIN_SPECS: dict[str, DomainSpec] = {
    spec.domain_type: spec
    for spec in (
        DomainSpec(
            domain_type="home_repair", scene="home", display_name="水電修繕",
            fulfillment_kind="booking",
            required_fields=("problem", "address", "phone"),
            status_labels={**_BOOKING_BASE_LABELS, "pending_provider": "需求送出", "confirmed": "已預約"},
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
        ),
        DomainSpec(
            domain_type="home_cleaning", scene="home", display_name="居家清潔",
            fulfillment_kind="booking",
            required_fields=("address", "phone"),
            status_labels=_BOOKING_BASE_LABELS,
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
        ),
        DomainSpec(
            domain_type="dining_reservation", scene="food", display_name="餐廳訂位",
            fulfillment_kind="booking",
            # 參考 E排客/TableCheck 指定日期訂位(B 型):人數(成人/兒童)、訂位人資料;
            # 座位偏好與特殊需求(過敏/兒童座椅/慶生/無障礙)為選填。
            required_fields=("party_size", "contact_name", "phone"),
            status_labels={
                **_BOOKING_BASE_LABELS,
                "pending_provider": "已建立", "confirmed": "店家確認",
                "in_service": "即將到店", "completed": "已完成",
            },
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
        ),
        DomainSpec(
            domain_type="car_wash", scene="move", display_name="洗車保養",
            fulfillment_kind="booking",
            # 速邁樂精緻洗車 A 型:車牌、車種、據點、時段、聯絡人;OPENPOINT 折抵走試算。
            required_fields=("plate_number", "car_type", "phone"),
            status_labels={
                **_BOOKING_BASE_LABELS,
                "pending_provider": "已預約", "confirmed": "站點確認",
                "in_service": "施作中", "completed": "已完成",
            },
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
        ),
        DomainSpec(
            domain_type="resort_booking", scene="fun", display_name="渡假村訂房",
            fulfillment_kind="booking",
            # ibon/渡假村 C 型訂房:入住/退房由時段承載、房型為 Resource、入住人數、加購走備註。
            required_fields=("party_size", "contact_name", "phone"),
            status_labels={
                **_BOOKING_BASE_LABELS,
                "pending_provider": "訂房送出", "confirmed": "訂房確認",
                "in_service": "已入住", "completed": "已退房",
            },
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
        ),
        DomainSpec(
            domain_type="shipping_pickup", scene="move", display_name="宅配寄件",
            fulfillment_kind="booking",
            required_fields=("package_size", "pickup_address", "receiver_address", "phone"),
            status_labels={
                **_BOOKING_BASE_LABELS,
                "pending_provider": "已預約收件", "confirmed": "司機已排班",
                "in_service": "收件中", "completed": "已收件寄出",
            },
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
        ),
        DomainSpec(
            domain_type="pharmacy_pickup", scene="med", display_name="處方箋領藥",
            fulfillment_kind="booking",
            # 參考康是美藥局領藥流程:處方箋類型(慢箋第 N 次/一般)、上傳照片後
            # rx_confirmed 必須經本人逐欄確認、是否本人領取;用藥類別/諮詢為選填。
            required_fields=("rx_confirmed", "rx_type", "patient_name", "phone", "pickup_in_person"),
            status_labels={
                **_BOOKING_BASE_LABELS,
                "pending_provider": "領藥申請送出", "confirmed": "藥局已備藥",
                "in_service": "可前往領藥", "completed": "已領藥",
            },
            timeline=("pending_provider", "confirmed", "in_service", "completed"),
            notes=(
                "處方箋僅提供辨識展示,不提供診斷或用藥建議;辨識結果須本人確認。",
            ),
        ),
        DomainSpec(
            domain_type="ec_preorder", scene="pre", display_name="i 預購/商城",
            fulfillment_kind="commerce",
            # 參考 iOPEN Mall/交貨便結帳:取貨方式(門市/宅配)、取件人須與證件相符;
            # 溫層、發票開立(載具/捐贈碼/統編)為選填。
            required_fields=("receiver_name", "phone", "pickup_method"),
            status_labels=_COMMERCE_BASE_LABELS,
            timeline=("placed", "accepted", "preparing", "shipped", "delivered"),
        ),
        DomainSpec(
            domain_type="food_delivery", scene="food", display_name="美食外送",
            fulfillment_kind="commerce",
            # 參考表單文件 食 C 型(外帶/外送預訂):門市、品項走 offering、備註選填。
            required_fields=("delivery_address", "phone"),
            status_labels={
                **_COMMERCE_BASE_LABELS,
                "accepted": "店家接單", "preparing": "餐點製作中",
                "shipped": "外送中", "delivered": "已送達",
            },
            timeline=("placed", "accepted", "preparing", "shipped", "delivered"),
        ),
        DomainSpec(
            domain_type="c2c_shipping", scene="move", display_name="交貨便寄件",
            fulfillment_kind="commerce",
            # 參考表單文件 預 3(C2C 寄件單):寄件人/收件人/商品名稱;取件門市走據點欄位。
            required_fields=("sender_name", "receiver_name", "item_name", "phone"),
            status_labels={
                **_COMMERCE_BASE_LABELS,
                "accepted": "寄件單成立", "preparing": "門市收件",
                "shipped": "運送中", "ready_for_pickup": "已到店", "delivered": "已取件",
            },
            timeline=("placed", "accepted", "preparing", "shipped", "ready_for_pickup", "delivered"),
        ),
        DomainSpec(
            domain_type="ticket_purchase", scene="fun", display_name="票券購買",
            fulfillment_kind="commerce",
            # 參考 ibon 售票 B 型(非劃位:景點/交通票券):使用日期/票種走 offering、張數=quantity。
            # 劃位型(演唱會/賽事選位)由產品負責人列入後續,不在本輪虛構。
            required_fields=("use_date", "buyer_name", "phone"),
            status_labels={
                **_COMMERCE_BASE_LABELS,
                "accepted": "訂單確認", "preparing": "出票中",
                "ready_for_pickup": "可取票(ibon)", "delivered": "已取票",
            },
            timeline=("placed", "accepted", "preparing", "ready_for_pickup", "delivered"),
        ),
    )
}


class DomainError(ValueError):
    """Draft 內容不符合 domain 的必填規則。"""


def get_domain(domain_type: str) -> DomainSpec:
    spec = DOMAIN_SPECS.get(domain_type)
    if spec is None:
        raise DomainError(f"不支援的服務類型:{domain_type}")
    return spec


def validate_draft_values(domain_type: str, values: dict) -> None:
    spec = get_domain(domain_type)
    missing = [name for name in spec.required_fields if not str(values.get(name) or "").strip()]
    if missing:
        raise DomainError("缺少必填欄位:" + "、".join(missing))
    if domain_type == "pharmacy_pickup" and str(values.get("rx_confirmed")).lower() not in {"true", "1", "yes"}:
        raise DomainError("處方箋辨識結果必須先由本人確認(rx_confirmed)")


def status_label(domain_type: str | None, *, kind: str, status: str) -> str:
    """回傳對使用者顯示的狀態名稱;找不到 domain 時退回通用名稱。"""
    if domain_type and domain_type in DOMAIN_SPECS:
        label = DOMAIN_SPECS[domain_type].status_labels.get(status)
        if label:
            return label
    base = _BOOKING_BASE_LABELS if kind == "booking" else _COMMERCE_BASE_LABELS
    return base.get(status, status)
