"""服務價格與折抵試算。

業務規則放後端：Web、AI 對話與 MCP 呼叫得到的金額必然一致。
折抵順序固定為 優惠券 → OPENPOINT → 支付加碼，且點數不會折超過剩餘應付金額。
"""

from __future__ import annotations

from dataclasses import dataclass, field

Answers = dict[str, object]

_BASE_PRICES: dict[str, int] = {
    "service-washer": 1600,
    "service-aircon": 1800,
    "service-cleaning": 1200,
    "service-housework": 900,
    "service-repair": 600,
    "service-shipping": 130,
    "service-restaurant": 0,   # 訂位金額依餐廳結果
    "service-delivery": 199,
    "service-shopping": 699,
}

_HOME_SIZE_SURCHARGE = {"medium": 500, "large": 1100}
_HOUSEWORK_PRICES = {"2": 900, "3": 1200, "4": 1500}
_PARCEL_PRICES = {"small": 130, "medium": 170, "large": 210}
_MEAL_PRICES = {"light": 199, "warm": 259, "family": 499}
_BUNDLE_PRICES = {"restock": 699, "coffee": 240, "snacks": 399}
_BUNDLE_COUPONS = {"restock": 50, "coffee": 30, "snacks": 40}
_BUNDLE_COUPON_LABELS = {"restock": "日用品補貨券", "coffee": "咖啡券組合優惠", "snacks": "零食分享券"}
_CHILLED_SURCHARGE = 80
_ICASH_BONUS = 20


@dataclass
class Quote:
    base_amount: int = 0
    coupon_discount: int = 0
    point_discount: int = 0
    payment_discount: int = 0
    final_amount: int = 0
    rule_summary: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "baseAmount": self.base_amount,
            "couponDiscount": self.coupon_discount,
            "pointDiscount": self.point_discount,
            "paymentDiscount": self.payment_discount,
            "finalAmount": self.final_amount,
            "ruleSummary": list(self.rule_summary),
        }


def _text(answers: Answers, key: str) -> str:
    value = answers.get(key)
    return "" if value is None else str(value)


def _quantity(answers: Answers) -> int:
    try:
        return max(1, int(str(answers.get("quantity", 1))))
    except (TypeError, ValueError):
        return 1


def _base_amount(service_id: str, answers: Answers) -> int:
    amount = _BASE_PRICES.get(service_id, 0)
    if service_id in ("service-washer", "service-aircon"):
        return amount * _quantity(answers)
    if service_id == "service-cleaning":
        return amount + _HOME_SIZE_SURCHARGE.get(_text(answers, "homeSize"), 0)
    if service_id == "service-housework":
        return _HOUSEWORK_PRICES.get(_text(answers, "hours"), 900)
    if service_id == "service-shipping":
        parcel = _PARCEL_PRICES.get(_text(answers, "parcelSize"), 130)
        return parcel + (_CHILLED_SURCHARGE if _text(answers, "speed") == "chilled" else 0)
    if service_id == "service-delivery":
        return _MEAL_PRICES.get(_text(answers, "meal"), 199)
    if service_id == "service-shopping":
        return _BUNDLE_PRICES.get(_text(answers, "bundle"), 699)
    return amount


def calculate_quote(service_id: str, answers: Answers | None = None) -> Quote:
    answers = answers or {}
    base = _base_amount(service_id, answers)
    quote = Quote(base_amount=base)

    # 目前只有商城購物走完整折抵鏈（券／點數／支付加碼）
    if service_id != "service-shopping":
        quote.final_amount = max(0, base)
        return quote

    bundle = _text(answers, "bundle")
    if _text(answers, "coupon") == "apply":
        quote.coupon_discount = _BUNDLE_COUPONS.get(bundle, 50)
        label = _BUNDLE_COUPON_LABELS.get(bundle, "補貨券")
        quote.rule_summary.append(f"{label} −NT$ {quote.coupon_discount}")

    remaining = max(0, base - quote.coupon_discount)
    requested_points = 50 if _text(answers, "points") == "50" else 0
    quote.point_discount = min(requested_points, remaining)
    if quote.point_discount:
        quote.rule_summary.append(f"OPENPOINT 折抵 {quote.point_discount} 點")

    if _text(answers, "payment") == "icash-pay":
        quote.payment_discount = _ICASH_BONUS
        quote.rule_summary.append(f"icash Pay 加碼 −NT$ {_ICASH_BONUS}")

    quote.final_amount = max(0, base - quote.coupon_discount - quote.point_discount - quote.payment_discount)
    return quote
