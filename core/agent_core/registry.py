"""Service Registry(spec 15 §4.2):服務同義詞、能力與必要欄位的確定性登錄表。

職責:把口語需求詞對應到 domain 與目錄中的 offering 候選;
模糊需求(如「洗衣服」)回傳需要釐清的選項,不硬答也不回「沒有服務」。
LLM 只負責從使用者語句抽關鍵詞;詞 → 服務的裁決在這裡,完全確定性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RegistryResolution:
    """一次詞彙解析的結果。

    - ``matched``:唯一命中的 domain(可直接進入目錄查詢)。
    - ``ambiguous``:命中多個 domain,需要向使用者釐清;``clarify`` 是釐清問題與選項。
    - 都空:登錄表不認得,Agent 應追問而不是宣稱沒有服務。
    """

    query: str
    matched: str | None = None
    ambiguous: tuple[str, ...] = ()
    clarify: str | None = None
    options: tuple[dict[str, str], ...] = field(default_factory=tuple)


#: domain → 同義詞(比對採「包含」;全部小寫)。與 core/catalog/domains.py 一一對應。
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "home_repair": (
        "修繕", "水電", "漏水", "跳電", "沒電", "插座", "電燈", "燈不亮", "馬桶",
        "水管", "門鎖", "修理", "維修", "冷氣不冷", "冷氣壞", "排水",
    ),
    "home_cleaning": (
        "清潔", "打掃", "掃除", "大掃除", "家事", "冷氣清洗", "洗冷氣", "洗衣機清洗",
        "居家清潔", "全室", "整理家裡", "環境整理",
    ),
    "dining_reservation": (
        "訂位", "餐廳", "訂餐廳", "聚餐", "吃飯", "晚餐", "午餐", "訂桌", "慶生聚餐",
        "家庭聚餐", "會餐", "圍爐",
    ),
    "food_delivery": ("外送", "外賣", "送餐", "點餐", "外帶"),
    "car_wash": ("洗車", "汽車美容", "鍍膜"),
    "shipping_pickup": ("宅配", "收件", "寄大件", "到府收"),
    "c2c_shipping": ("寄件", "寄包裹", "交貨便", "店到店", "寄東西"),
    "pharmacy_pickup": ("領藥", "處方箋", "藥局", "慢箋", "拿藥"),
    "ec_preorder": ("購物", "買", "預購", "補貨", "下單", "商城", "日用品"),
    "resort_booking": ("訂房", "住宿", "渡假", "度假", "溫泉", "旅館", "飯店"),
    "ticket_purchase": ("門票", "票券", "買票", "車票", "聯票"),
}

#: 已知的模糊詞:一個詞同時指向多個 domain 時,固定的釐清問題與選項。
_AMBIGUOUS: dict[str, dict[str, Any]] = {
    "洗衣服": {
        "domains": ("home_cleaning",),
        "clarify": "「洗衣服」是想找人到府做家事(含洗衣),還是洗衣機本身要清洗?",
        "options": (
            {"domain": "home_cleaning", "label": "到府家事服務(含洗衣)"},
            {"domain": "home_cleaning", "label": "洗衣機清洗"},
        ),
    },
    "洗衣": {
        "domains": ("home_cleaning",),
        "clarify": "「洗衣」是想找人到府做家事(含洗衣),還是洗衣機本身要清洗?",
        "options": (
            {"domain": "home_cleaning", "label": "到府家事服務(含洗衣)"},
            {"domain": "home_cleaning", "label": "洗衣機清洗"},
        ),
    },
    "冷氣": {
        "domains": ("home_repair", "home_cleaning"),
        "clarify": "冷氣是壞了要修(不冷、漏水、異音),還是要定期清洗保養?",
        "options": (
            {"domain": "home_repair", "label": "冷氣故障維修"},
            {"domain": "home_cleaning", "label": "冷氣清洗保養"},
        ),
    },
    "寄": {
        "domains": ("c2c_shipping", "shipping_pickup"),
        "clarify": "要寄的是小包裹(超商店到店),還是大件需要宅配到府收件?",
        "options": (
            {"domain": "c2c_shipping", "label": "超商店到店寄件"},
            {"domain": "shipping_pickup", "label": "宅配到府收件"},
        ),
    },
}


#: 節慶／家庭場合 → 平台真的做得到的服務組合(確定性建議,不是 LLM 想像)。
#:
#: 住戶說「父親節那個交給你安排」時,句子裡沒有任何服務名詞,登錄表當然解析不出
#: domain,舊行為就變成「我還不確定對應哪一類服務」——看起來像「找不到服務」。
#: 這張表把常見場合對應到已存在的 domain,讓 Agent 能提出可確認的組合;它只決定
#: **要提哪幾類服務**,日期、價格、店家一律仍由使用者與目錄決定。
_OCCASION_BUNDLES: tuple[dict[str, Any], ...] = (
    {
        "keywords": ("父親節", "母親節", "爸媽來", "爸媽要來", "家人來訪", "親戚來",
                     "爸爸來", "媽媽來", "長輩來"),
        "label": "家人來訪／節日聚會",
        "services": (("家裡先做一次清潔", "清潔"), ("家庭聚餐的餐廳", "餐廳")),
    },
    {
        "keywords": ("過年", "春節", "除夕", "年夜飯", "圍爐"),
        "label": "過年準備",
        "services": (("年前大掃除", "大掃除"), ("年夜飯餐廳", "餐廳")),
    },
    {
        "keywords": ("尾牙", "春酒", "謝師宴"),
        "label": "聚餐活動",
        "services": (("聚餐餐廳", "餐廳"),),
    },
    {
        "keywords": ("生日", "慶生"),
        "label": "生日慶祝",
        "services": (("慶生餐廳", "餐廳"),),
    },
    {
        "keywords": ("搬家", "入厝", "新家"),
        "label": "搬家入厝",
        "services": (("新居清潔", "清潔"), ("大件物品宅配", "宅配")),
    },
)


@dataclass(frozen=True)
class OccasionSuggestion:
    """一個場合對應到的單一服務建議(仍需使用者確認)。"""

    occasion: str
    goal: str
    service_hint: str


class ServiceRegistry:
    """確定性詞彙解析。與目錄投影一起用:matched domain 再去查真實 offering。"""

    def __init__(self, *, extra_synonyms: dict[str, tuple[str, ...]] | None = None) -> None:
        self._synonyms = dict(_SYNONYMS)
        for domain, words in (extra_synonyms or {}).items():
            self._synonyms[domain] = tuple({*self._synonyms.get(domain, ()), *words})

    def known_domains(self) -> tuple[str, ...]:
        return tuple(self._synonyms)

    def vocabulary(self) -> dict[str, list[str]]:
        """domain → 這個 domain 認得的說法。

        給 LLM 當 bounded context 用:模型抽 serviceHint 時應該挑這裡出現過的詞,
        它就不會產生一個登錄表解不開、最後看起來像「沒有這個服務」的關鍵詞。
        """

        return {domain: list(words) for domain, words in self._synonyms.items()}

    def suggest_for_occasion(self, query: str) -> tuple[OccasionSuggestion, ...]:
        """把「父親節那個交給你安排」這種只有場合、沒有服務名詞的句子接住。

        只有在句子完全解析不出 domain 時才該呼叫;句中已經出現服務名詞時,
        使用者說的永遠優先。
        """

        text = query.strip().lower()
        if not text:
            return ()
        for bundle in _OCCASION_BUNDLES:
            if not any(keyword in text for keyword in bundle["keywords"]):
                continue
            return tuple(
                OccasionSuggestion(occasion=bundle["label"], goal=goal, service_hint=hint)
                for goal, hint in bundle["services"]
            )
        return ()

    def resolve(self, query: str) -> RegistryResolution:
        text = query.strip().lower()
        if not text:
            return RegistryResolution(query=query)

        # 先看固定的模糊詞(較長的詞先比,避免「洗衣服」被「洗衣」搶走)
        for keyword in sorted(_AMBIGUOUS, key=len, reverse=True):
            if keyword in text:
                entry = _AMBIGUOUS[keyword]
                # 若語句同時含有能消歧的詞(例如「冷氣不冷」),讓精確同義詞優先
                exact = self._match_domains(text, skip_words=(keyword,))
                if len(exact) == 1:
                    return RegistryResolution(query=query, matched=next(iter(exact)))
                return RegistryResolution(
                    query=query,
                    ambiguous=tuple(entry["domains"]),
                    clarify=entry["clarify"],
                    options=tuple(entry["options"]),
                )

        matches = self._match_domains(text)
        if len(matches) == 1:
            return RegistryResolution(query=query, matched=next(iter(matches)))
        if len(matches) > 1:
            ordered = tuple(sorted(matches))
            return RegistryResolution(
                query=query,
                ambiguous=ordered,
                clarify="你的需求可能對應多種服務,想找的是哪一種?",
                options=tuple({"domain": item, "label": item} for item in ordered),
            )
        return RegistryResolution(query=query)

    def _match_domains(self, text: str, *, skip_words: tuple[str, ...] = ()) -> set[str]:
        matches: set[str] = set()
        for domain, words in self._synonyms.items():
            for word in words:
                if word in skip_words:
                    continue
                if word in text:
                    matches.add(domain)
                    break
        return matches
