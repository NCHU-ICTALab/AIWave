"""展示住戶：把官方樣本裡零碎的帳號組成少數幾位有完整生活樣貌的住戶。

## 為什麼需要這一層

官方 `mms_order_record` 是**子集**：10 個帳號、99 筆訂單，其中 7 個帳號只用過
單一服務、6 個訂單數不到 3 筆。以這樣的資料 demo，每位住戶看起來都只會用一種服務，
而「AI 生活管家」的價值恰恰在**跨服務**——推薦、行為軌跡、今日摘要全都要有廣度才成立。

## 兩層，而且分得清楚

1. **行為指紋（真）**——`identity.py` 用官方 `member_*_hash` 把帳號認回同一人。
   這不是我們編的，是官方資料本身就指出來的（10 帳號 → 8 身分）。
2. **展示組合（本模組，非推導）**——把解析後的身分再指派給三位展示住戶。
   **這一步沒有資料依據，是我們為了 demo 指定的**，因此每位住戶都帶
   `composed_from` 與 `has_real_resolution`，介面必須標示得出來，
   不可讓人以為系統「算出」這些人是同一個家庭。

先例見 `regions.py` 的 `_DEMO_DISTRICT_EXTENSIONS`：官方樣本不夠時，
補上去的資料要標記清楚，不偽裝成官方原始列。

## 三位住戶

刻意對應命題的雙背景（社區＋樂齡）與不同生活型態，讓評審看得到差異：

| 住戶 | 生活型態 | 訂單 | 服務種類 |
| --- | --- | --- | --- |
| 小圓 | 家庭主力，家電清洗＋修繕＋外食都有 | 27 | 5 |
| 陳伯伯 | 樂齡，重視固定叫修與日用品補貨 | 35 | 4 |
| Vivian | 上班族，以購物與外食為主 | 37 | 3 |
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .identity import resolve_identities

# 官方帳號（完整 id，前 8 碼在資料裡並不唯一——有兩個帳號都以 019a52d3 開頭）
_XIAOYUAN = "019a52d3-7f6b-7da3-b48d-9c9e2522d616"      # 與 019eee3f、019ef24a 由雜湊併為同一人
_CHEN_REPAIR = "019c0464-2d01-73f0-9f9b-d1392fdb941a"
_CHEN_SHOP = "019d7569-19cc-7727-aa60-82644ce67ad7"
_CHEN_AIRCON = "019db86c-201d-700a-ba04-525d90da4b0b"
_CHEN_ONEOFF = "019cb30b-6a86-739a-832b-38225a2b2fdf"
_VIVIAN_SHOP = "019e6c8c-a061-7197-be0f-b7d341dbafdd"
_VIVIAN_DINE = "019a52d3-7f6b-7f5f-8201-98588d5a5b84"
_VIVIAN_DELIVERY = "019c08f2-62e1-76be-a7ac-44b8a2d1d290"


@dataclass(frozen=True)
class Persona:
    """一位展示住戶。"""

    id: str
    name: str
    role_summary: str
    #: 組成這位住戶的**身分 id**（每個身分本身可能已由行為指紋併過帳號）
    identity_ids: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "roleSummary": self.role_summary,
            "identityIds": list(self.identity_ids),
            # 介面據此標示「這是展示組合」，不可省略
            "composedFrom": len(self.identity_ids),
            "source": "demo_composition",
        }


PERSONAS: tuple[Persona, ...] = (
    Persona(
        id=_XIAOYUAN,
        name="小圓",
        role_summary="雙薪家庭，家電清洗、水電修繕與外食都會用",
        identity_ids=(_XIAOYUAN,),
    ),
    Persona(
        id=_CHEN_REPAIR,
        name="陳伯伯",
        role_summary="樂齡住戶，固定叫修與日用品補貨",
        identity_ids=(_CHEN_REPAIR, _CHEN_SHOP, _CHEN_AIRCON, _CHEN_ONEOFF),
    ),
    Persona(
        id=_VIVIAN_SHOP,
        name="Vivian",
        role_summary="上班族，以線上購物與外食為主",
        identity_ids=(_VIVIAN_SHOP, _VIVIAN_DINE, _VIVIAN_DELIVERY),
    ),
)


@lru_cache(maxsize=1)
def _accounts_by_persona() -> dict[str, tuple[str, ...]]:
    """展開成官方帳號清單：展示住戶 → 身分 → 帳號。"""
    by_identity = {identity.id: identity.account_ids for identity in resolve_identities()}
    return {
        persona.id: tuple(
            account
            for identity_id in persona.identity_ids
            for account in by_identity.get(identity_id, (identity_id,))
        )
        for persona in PERSONAS
    }


def list_personas() -> tuple[Persona, ...]:
    return PERSONAS


def get_persona(persona_id: str) -> Persona | None:
    return next((persona for persona in PERSONAS if persona.id == persona_id), None)


def accounts_for_persona(persona_id: str) -> tuple[str, ...]:
    """該住戶底下的所有官方帳號；不是展示住戶時視為單一帳號。"""
    return _accounts_by_persona().get(persona_id, (persona_id,))


def real_resolution_count(persona_id: str) -> int:
    """其中有幾個帳號是**由官方雜湊真的認回來的**（供介面誠實標示）。"""
    persona = get_persona(persona_id)
    if persona is None:
        return 0
    merged = {identity.id: identity for identity in resolve_identities() if identity.is_merged}
    return sum(
        len(merged[identity_id].account_ids)
        for identity_id in persona.identity_ids
        if identity_id in merged
    )
