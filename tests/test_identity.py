"""行為指紋與展示住戶。

兩層的界線是這組測試守護的重點：
- **行為指紋**（`identity.py`）：由官方 `member_*_hash` 推導，是真的。
- **展示組合**（`personas.py`）：我們指定的，必須標示，不可偽裝成推導結果。
"""

from __future__ import annotations

from collections import Counter

from core.data.identity import accounts_of, identity_of, resolve_identities
from core.data.official_orders import list_accounts, load_orders, orders_for
from core.data.personas import (
    accounts_for_persona,
    get_persona,
    list_personas,
    real_resolution_count,
)

XIAOYUAN = "019a52d3-7f6b-7da3-b48d-9c9e2522d616"
CHEN = "019c0464-2d01-73f0-9f9b-d1392fdb941a"
VIVIAN = "019e6c8c-a061-7197-be0f-b7d341dbafdd"


class TestIdentityResolution:
    """由官方雜湊做的解析——斷言固定在真實資料上，資料變了測試就該叫。"""

    def test_resolves_ten_accounts_into_eight_identities(self):
        identities = resolve_identities()
        assert sum(len(identity.account_ids) for identity in identities) == len(list_accounts()) == 10
        assert len(identities) == 8

    def test_the_merged_identity_spans_three_accounts(self):
        merged = [identity for identity in identities_merged()]
        assert len(merged) == 1
        assert set(merged[0].account_ids) == {
            "019a52d3-7f6b-7da3-b48d-9c9e2522d616",
            "019eee3f-841e-7048-ae67-0955b144f4f8",
            "019ef24a-424e-776e-854c-a1cf7b2b3ed9",
        }

    def test_records_which_hash_fields_made_the_link(self):
        (merged,) = identities_merged()
        assert set(merged.linked_by) == {"member_name_hash", "member_phone_hash", "member_email_hash"}

    def test_every_account_maps_back_to_exactly_one_identity(self):
        for account in list_accounts():
            assert account in accounts_of(identity_of(account))

    def test_an_unknown_account_is_its_own_identity(self):
        assert identity_of("no-such-account") == "no-such-account"
        assert accounts_of("no-such-account") == ("no-such-account",)


def identities_merged():
    return [identity for identity in resolve_identities() if identity.is_merged]


class TestPersonas:
    def test_three_personas_cover_every_official_account(self):
        """訂單一筆都不能漏掉，也不能被算到兩個人頭上。"""
        all_accounts = [
            account for persona in list_personas() for account in accounts_for_persona(persona.id)
        ]
        assert sorted(all_accounts) == sorted(list_accounts())
        assert len(all_accounts) == len(set(all_accounts)), "同一帳號被指派給兩位住戶"

    def test_every_persona_uses_multiple_services(self):
        """這正是本次整併的目的：一個人本來就會同時用很多服務。"""
        for persona in list_personas():
            orders = orders_for(persona.id)
            services = {order.service_name for order in orders}
            assert len(services) >= 3, f"{persona.name} 只有 {services}"
            assert len(orders) >= 20, f"{persona.name} 只有 {len(orders)} 筆"

    def test_personas_declare_themselves_as_composition_not_inference(self):
        for persona in list_personas():
            payload = persona.to_dict()
            assert payload["source"] == "demo_composition"
            assert payload["composedFrom"] == len(persona.identity_ids)

    def test_reports_how_many_accounts_were_truly_hash_resolved(self):
        # 小圓的三個帳號是官方雜湊真的認回來的；陳伯伯與 Vivian 的組合則沒有雜湊依據
        assert real_resolution_count(XIAOYUAN) == 3
        assert real_resolution_count(CHEN) == 0
        assert real_resolution_count(VIVIAN) == 0

    def test_orders_for_expands_a_persona_to_all_its_accounts(self):
        orders = orders_for(CHEN)
        by_service = Counter(order.service_name for order in orders)
        assert len(orders) == 35
        assert by_service["水電修繕"] == 9   # 8（固定叫修）＋1（單筆帳號）
        assert by_service["商城購物"] == 23

    def test_orders_for_a_plain_account_still_works(self):
        """傳入原始帳號（非住戶）時行為不變——身分隔離仍以帳號為界。"""
        orders = orders_for("019d7569-19cc-7727-aa60-82644ce67ad7")
        assert len(orders) == 23
        assert all(order.account_id == "019d7569-19cc-7727-aa60-82644ce67ad7" for order in orders)

    def test_total_orders_across_personas_equals_the_official_dataset(self):
        assert sum(len(orders_for(p.id)) for p in list_personas()) == len(load_orders()) == 99

    def test_get_persona_returns_none_for_unknown(self):
        assert get_persona("nobody") is None
