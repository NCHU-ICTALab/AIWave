"""服務媒合（FR-S-04）：命題明列的七項條件，每一項都要真的影響結果。

若某個條件改了卻不影響排序或說明，那條件就只是裝飾——這裡逐項驗證它有作用。
"""

from __future__ import annotations

import pytest

from core.forms.service_catalog import list_services
from core.matching import VENDORS, match

TAIPEI = "01"
HUALIEN = "18"   # 沒有任何廠商涵蓋


class TestSeedDataIntegrity:
    def test_every_offering_points_at_a_real_service(self):
        catalog = {service.id for service in list_services()}
        for vendor in VENDORS:
            for offering in vendor.offerings:
                assert offering.service_id in catalog, f"{vendor.name} 提供了不存在的服務"

    def test_core_services_have_at_least_two_vendors_to_compare(self):
        """命題要求「列 2-3 家比較可改選」，所以主要服務不能只有一家。"""
        for service_id in ("service-aircon", "service-cleaning", "service-repair", "service-shipping"):
            matches = match(service_id, county_code=TAIPEI)
            assert len(matches) >= 2, f"{service_id} 只有 {len(matches)} 家可比較"

    def test_returns_at_most_three_so_the_comparison_stays_readable(self):
        assert len(match("service-repair", county_code=TAIPEI)) <= 3

    def test_results_are_labelled_as_competition_seed_data(self):
        """報價與評分是我們建的，不是品牌實價；介面要標得出來。"""
        for item in match("service-aircon", county_code=TAIPEI):
            assert item.to_dict()["dataSource"] == "competition_seed"
            assert item.to_dict()["computedBy"] == "rules"


class TestCoverageIsAHardCondition:
    def test_excludes_vendors_that_cannot_serve_the_area(self):
        assert match("service-repair", county_code=HUALIEN) == []

    def test_includes_everyone_when_no_area_is_given(self):
        assert match("service-repair", limit=10)


class TestEachCriterionChangesTheOutcome:
    def test_urgency_promotes_vendors_that_support_it(self):
        urgent = match("service-repair", county_code=TAIPEI, urgent=True)
        assert urgent[0].vendor.supports_urgent, "說了很急，第一名卻不能加急"

    def test_a_vendor_without_urgency_is_kept_but_flagged(self):
        """不排除、但要講清楚代價——使用者要的是選擇，不是沒有替代方案的結論。"""
        results = match("service-repair", county_code=TAIPEI, urgent=True, limit=10)
        slow = next(item for item in results if not item.vendor.supports_urgent)
        assert any("不提供加急" in concern for concern in slow.concerns)

    def test_budget_promotes_cheaper_vendors(self):
        results = match("service-repair", county_code=TAIPEI, budget=1000)
        assert results[0].offering.base_price <= 1000

    def test_over_budget_vendors_state_how_much_over(self):
        results = match("service-repair", county_code=TAIPEI, budget=1000, limit=10)
        pricey = next(item for item in results if item.offering.base_price > 1000)
        assert any("超出預算" in concern for concern in pricey.concerns)

    def test_slot_promotes_vendors_that_can_actually_come_then(self):
        results = match("service-cleaning", county_code=TAIPEI, slot="evening")
        assert "evening" in results[0].offering.slots

    def test_rating_breaks_the_tie_when_nothing_else_differs(self):
        results = match("service-shipping", county_code=TAIPEI)
        ratings = [item.vendor.rating for item in results]
        assert ratings == sorted(ratings, reverse=True)


class TestExplainability:
    def test_every_match_explains_itself(self):
        results = match("service-repair", county_code=TAIPEI, budget=1500, slot="evening", urgent=True)
        for item in results:
            assert item.reasons, f"{item.vendor.name} 沒有任何理由"
            for reason in item.reasons:
                assert reason.label and reason.code

    def test_the_reasons_name_the_criteria_that_were_supplied(self):
        item = match("service-repair", county_code=TAIPEI, budget=2000, slot="evening", urgent=True)[0]
        codes = {reason.code for reason in item.reasons}
        assert {"coverage", "rating", "budget", "slot", "urgent"} <= codes

    def test_criteria_not_supplied_produce_no_reasons(self):
        """沒問的條件不該憑空出現在理由裡——那會讓解釋變成話術。"""
        item = match("service-repair", county_code=TAIPEI)[0]
        codes = {reason.code for reason in item.reasons}
        assert "budget" not in codes
        assert "slot" not in codes
        assert "urgent" not in codes


def test_matching_is_deterministic():
    """同樣的輸入必須得到同樣的排序，否則「為什麼推薦這家」就無法解釋。"""
    first = [item.vendor.id for item in match("service-cleaning", county_code=TAIPEI, budget=3000)]
    second = [item.vendor.id for item in match("service-cleaning", county_code=TAIPEI, budget=3000)]
    assert first == second
