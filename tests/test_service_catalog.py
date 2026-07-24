"""服務目錄／題組定義／價格試算——後端為單一事實來源。"""

from __future__ import annotations

from datetime import date

import pytest

from core.forms import service_catalog
from core.forms.dto import form_to_dict
from core.forms.models import ServiceAction, TopicType
from core.services.pricing import calculate_quote

TODAY = date(2026, 7, 25)


def _fields(service_id: str) -> dict[str, dict]:
    form = service_catalog.get_service_form(service_id)
    assert form is not None
    return {field["id"]: field for field in form_to_dict(form, today=TODAY)["fields"]}


# ---- 目錄 --------------------------------------------------------------

def test_catalog_has_nine_services():
    """官方主檔八項服務＋商城購物。"""
    services = service_catalog.list_services()
    assert len(services) == 9
    assert {s.id for s in services} == set(service_catalog._BUILDERS)


def test_every_service_has_a_form():
    for service in service_catalog.list_services():
        assert service_catalog.get_service_form(service.id) is not None, service.id


def test_unknown_service_returns_none():
    assert service_catalog.get_service_form("service-nope") is None


# ---- 題型與官方對齊 -----------------------------------------------------

def test_all_topic_types_are_official_codes():
    """題型一律為官方 pms_form_topic.type 1–10，不得自訂。"""
    official = {int(t.value) for t in TopicType}
    for service in service_catalog.list_services():
        form = service_catalog.get_service_form(service.id)
        assert form is not None
        for topic in form.ordered_topics():
            assert int(topic.type.value) in official


def test_actions_cover_official_order_semantics():
    actions = {
        service.id: service_catalog.get_service_form(service.id).action  # type: ignore[union-attr]
        for service in service_catalog.list_services()
    }
    assert actions["service-aircon"] is ServiceAction.INQUIRY
    assert actions["service-restaurant"] is ServiceAction.RESERVATION
    assert actions["service-shipping"] is ServiceAction.SHIPMENT
    assert actions["service-shopping"] is ServiceAction.ORDER


# ---- DTO：跳題與日期換算 ------------------------------------------------

def test_repair_detail_field_is_conditional_on_other():
    """『問題說明』只在修繕項目選「其他」時出現。"""
    detail = _fields("service-repair")["detail"]
    assert detail["visibleWhen"] == {"fieldId": "repairType", "equals": "other"}


def test_fields_without_skip_logic_have_no_visible_when():
    assert "visibleWhen" not in _fields("service-repair")["urgency"]


def test_date_offsets_become_absolute_dates():
    """相對偏移在 DTO 換算成絕對日期，前端拿到即可用。"""
    date_field = _fields("service-aircon")["date"]
    assert date_field["type"] == 9
    assert date_field["minDate"] == "2026-07-26"   # 明日
    assert date_field["maxDate"] == "2026-08-08"   # 14 天後


def test_number_field_carries_bounds():
    quantity = _fields("service-aircon")["quantity"]
    assert quantity["numberOnly"] is True
    assert (quantity["min"], quantity["max"]) == (1, 5)


def test_options_expose_stable_values():
    options = _fields("service-aircon")["airconType"]["options"]
    assert [o["value"] for o in options] == ["split", "window"]
    assert [o["label"] for o in options] == ["分離式", "窗型"]


# ---- 價格試算 -----------------------------------------------------------

def test_quantity_multiplies_base_price():
    assert calculate_quote("service-aircon", {"quantity": 3}).final_amount == 5400


def test_shopping_discount_chain_order():
    """券 → 點數 → 支付加碼；日用品補貨組 699。"""
    quote = calculate_quote(
        "service-shopping",
        {"bundle": "restock", "coupon": "apply", "points": "50", "payment": "icash-pay"},
    )
    assert (quote.base_amount, quote.coupon_discount, quote.point_discount, quote.payment_discount) == (699, 50, 50, 20)
    assert quote.final_amount == 579
    assert len(quote.rule_summary) == 3


def test_points_never_exceed_remaining_amount():
    """咖啡券組 240，券折 30 後剩 210，點數最多折 50。"""
    quote = calculate_quote("service-shopping", {"bundle": "coffee", "coupon": "apply", "points": "50"})
    assert quote.point_discount == 50
    assert quote.final_amount == 160


def test_non_shopping_services_have_no_discount_chain():
    quote = calculate_quote("service-shipping", {"parcelSize": "large", "speed": "chilled"})
    assert quote.base_amount == 290  # 210 + 80 低溫
    assert (quote.coupon_discount, quote.point_discount, quote.payment_discount) == (0, 0, 0)
    assert quote.final_amount == 290


@pytest.mark.parametrize("bad_quantity", ["", "abc", None])
def test_invalid_quantity_falls_back_to_one(bad_quantity):
    assert calculate_quote("service-washer", {"quantity": bad_quantity}).final_amount == 1600
