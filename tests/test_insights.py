"""行為軌跡與可解釋推薦——全部由官方 mms_order_record 算出。

這組測試同時是「畫面數字不是寫死的」的憑證：每個統計都能追回官方訂單。
"""

from __future__ import annotations

from datetime import date

import pytest

from core.data.official_orders import OFFICIAL_SERVICE_TO_CATALOG, list_accounts, load_orders, orders_for
from core.insights import build_trail, recommend, summarize
from core.services import DEMO_ACCOUNT_ID

TODAY = date(2026, 7, 25)
RICH_ACCOUNT = "019eee3f-841e-7048-ae67-0955b144f4f8"  # 16 筆、跨 4 種服務


# ---- 官方資料載入 --------------------------------------------------------

def test_official_orders_are_loaded():
    orders = load_orders()
    assert len(orders) == 99
    assert len(list_accounts()) == 10


def test_every_order_maps_to_a_catalog_service():
    """官方 service_id 全部對得到我們的九項服務，否則軌跡會有斷點。"""
    unmapped = {o.service_id for o in load_orders() if o.catalog_service_id is None}
    assert unmapped == set()


def test_catalog_mapping_covers_official_service_ids():
    assert set(OFFICIAL_SERVICE_TO_CATALOG) >= {o.service_id for o in load_orders()}


def test_orders_are_time_ordered():
    times = [o.order_time for o in load_orders() if o.order_time]
    assert times == sorted(times)


# ---- 行為軌跡 -----------------------------------------------------------

def test_trail_is_cross_service_and_chronological():
    trail = build_trail(RICH_ACCOUNT)
    assert len(trail) == 16
    assert len({event.service_name for event in trail}) == 4
    dates = [event.occurred_on for event in trail if event.occurred_on]
    assert dates == sorted(dates)


def test_trail_events_carry_official_record_ids():
    """軌跡要指得回官方紀錄，才有辦法在畫面上標示來源。"""
    for event in build_trail(RICH_ACCOUNT):
        assert event.record_id > 0
        assert event.outcome in {"completed", "open", "cancelled"}


# ---- 消費摘要 -----------------------------------------------------------

def test_summary_totals_match_underlying_orders():
    summary = summarize(RICH_ACCOUNT, today=TODAY)
    orders = orders_for(RICH_ACCOUNT)
    assert summary.total_orders == len(orders)
    assert summary.completed_orders + summary.open_orders + summary.cancelled_orders == len(orders)


def test_spend_counts_completed_orders_only():
    """取消／退款的訂單不該算進消費金額。"""
    summary = summarize(RICH_ACCOUNT, today=TODAY)
    expected = sum(o.final_amount for o in orders_for(RICH_ACCOUNT) if o.is_completed)
    assert summary.total_spend == pytest.approx(expected)
    assert summary.cancelled_orders > 0  # 這位 persona 確實有取消單，測試才有意義


def test_days_since_last_is_measured_from_given_today():
    summary = summarize(RICH_ACCOUNT, today=TODAY)
    for usage in summary.services:
        assert usage.days_since_last == (TODAY - usage.last_used_on).days


def test_summary_is_serialisable_for_the_dashboard():
    payload = summarize(RICH_ACCOUNT, today=TODAY).to_dict()
    assert payload["source"] == "official_order_record"
    assert payload["totalOrders"] == 16
    assert payload["services"]


# ---- 可解釋推薦 ---------------------------------------------------------

def test_every_recommendation_carries_evidence_and_reasons():
    """核心誠實性保證：沒有證據的推薦不准出現。"""
    for account_id in list_accounts():
        for rec in recommend(account_id, today=TODAY, limit=5):
            assert rec.reason_codes, rec.id
            assert rec.reason_text, rec.id
            assert rec.evidence, rec.id
            assert rec.to_dict()["computedBy"] == "rules"


def test_open_official_order_becomes_the_top_recommendation():
    """展示 persona 有一筆未完成的水電修繕，應排第一。"""
    recs = recommend(DEMO_ACCOUNT_ID, today=TODAY)
    assert recs[0].kind == "resume_open"
    assert recs[0].service_id == "service-repair"
    evidence = recs[0].evidence[0]
    source = next(o for o in orders_for(DEMO_ACCOUNT_ID) if o.record_id == evidence.record_id)
    assert source.is_open


def test_event_driven_services_are_not_recommended_for_revisit():
    """水電修繕、餐廳訂位不是週期性服務，不該推「該再來一次」。"""
    for account_id in list_accounts():
        for rec in recommend(account_id, today=TODAY, limit=10):
            if rec.kind == "revisit":
                assert rec.service_id not in {"service-repair", "service-restaurant", "service-shipping"}


def test_cross_sell_uses_official_vendor_relationship():
    """交叉推薦的依據是官方主檔的服務商關係，不是憑空相似度。"""
    recs = recommend(RICH_ACCOUNT, today=TODAY, limit=10)
    cross = [rec for rec in recs if rec.kind == "vendor_cross_sell"]
    assert cross, "期待有同服務商的未使用服務"
    assert any(code.startswith("vendor_") for code in cross[0].reason_codes)
    used = {o.catalog_service_id for o in orders_for(RICH_ACCOUNT)}
    assert cross[0].service_id not in used  # 只推沒用過的


def test_cross_sell_mentions_each_vendor_relationship_once():
    """同一個服務商關係只講一次。

    實測：清潔商旗下三項未用過的服務各出一張「同一服務商也提供…」，
    把今日摘要整個佔滿——那是排列組合，不是三個獨立的洞察。
    """
    recs = recommend(RICH_ACCOUNT, today=TODAY, limit=10)
    cross = [rec for rec in recs if rec.kind == "vendor_cross_sell"]
    vendors = [next(c for c in rec.reason_codes if c.startswith("vendor_")) for rec in cross]
    assert len(vendors) == len(set(vendors)), "同一服務商出現多張交叉推薦"


def test_recommendations_are_deduped_by_service_and_ranked():
    recs = recommend(RICH_ACCOUNT, today=TODAY, limit=5)
    service_ids = [rec.service_id for rec in recs]
    assert len(service_ids) == len(set(service_ids))
    assert [rec.score for rec in recs] == sorted((rec.score for rec in recs), reverse=True)


def test_unknown_account_yields_no_recommendations():
    assert recommend("no-such-account", today=TODAY) == []
