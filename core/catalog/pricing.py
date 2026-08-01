"""確定性的價格與點數試算(Demo 規則,不涉及 LLM)。

Demo 換算規則:1 點 = NT$1;可折抵上限 = min(會員可用點數, 應付金額)。
正式規則由產品負責人提供後替換此模組,呼叫端不變。
"""

from __future__ import annotations

from typing import Any

POINT_VALUE_TWD = 1


class QuoteError(ValueError):
    pass


def estimate(
    *,
    offering: dict[str, Any],
    quantity: int = 1,
    points_to_redeem: int = 0,
    points_balance: int = 0,
) -> dict[str, Any]:
    if quantity < 1:
        raise QuoteError("數量至少為 1")
    if points_to_redeem < 0:
        raise QuoteError("折抵點數不可為負")
    base_price = int(offering.get("basePrice", 0))
    subtotal = base_price * quantity
    max_redeemable = min(points_balance, subtotal // POINT_VALUE_TWD)
    if points_to_redeem > max_redeemable:
        raise QuoteError(
            f"點數折抵超過上限(可折抵 {max_redeemable} 點)"
        )
    discount = points_to_redeem * POINT_VALUE_TWD
    return {
        "offeringId": offering["id"],
        "offeringName": offering.get("name"),
        "currency": offering.get("currency", "TWD"),
        "unitPrice": base_price,
        "quantity": quantity,
        "subtotal": subtotal,
        "pointsBalance": points_balance,
        "maxRedeemablePoints": max_redeemable,
        "pointsToRedeem": points_to_redeem,
        "pointsDiscount": discount,
        "payable": subtotal - discount,
        "ruleSummary": f"Demo 規則:1 點折抵 NT${POINT_VALUE_TWD};"
                       f"最多折抵至應付 NT$0,不可超過可用點數。",
    }
