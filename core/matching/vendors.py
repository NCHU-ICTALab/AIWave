"""服務媒合（FR-S-04，命題明列的核心能力）。

命題把媒合條件寫死了：**服務類型／地區／時段／預算／緊急程度／服務商可服務範圍／評分**。
這裡就照這七項做，一項不多一項不少，且每一項都對應得到程式碼中的一條規則。

兩個延續既有決策的設計：

- **可解釋**（同 [ADR-0011]）：媒合不是一個黑箱分數。每家廠商都回傳 `reasons`，
  逐條說明「符合哪個條件、加了幾分」，介面上可以直接攤開給使用者看。
  LLM 不參與評分，只在上層把結果講成一句話。
- **官方服務來源 ≠ 履約廠商**（[ADR-0009]）：官方 `cms_homepage_service_vendor` 裡的
  「清潔／寄件／修繕服務」是服務分類，不是公司。真正的廠商是本模組的擴充資料。

**資料誠實性**：下方廠商的報價、評分、可服務時段皆為**競賽建置資料**
（`data_source="competition_seed"`），不是這些品牌的真實營業數據。品牌名稱取自官方
素材中出現、且服務項目確實相符者；介面顯示時必須標示資料來源，不可讓人誤以為是實價。
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 時段代碼——與題組的時段選項一致
SLOTS = {
    "weekday_morning": "平日上午",
    "weekday_afternoon": "平日下午",
    "weekend": "假日",
    "evening": "夜間",
}


@dataclass(frozen=True)
class Offering:
    """一家廠商對一項服務的報價與可服務時段。"""

    service_id: str
    base_price: int
    slots: frozenset[str]


@dataclass(frozen=True)
class Vendor:
    """實際履約的合作廠商（擴充資料，非官方表）。"""

    id: str
    name: str
    intro: str
    rating: float
    review_count: int
    supports_urgent: bool
    #: 可服務縣市代碼；`districts` 留空表示整個縣市都服務
    counties: frozenset[str]
    districts: frozenset[str] = field(default_factory=frozenset)
    offerings: tuple[Offering, ...] = ()

    def offering_for(self, service_id: str) -> Offering | None:
        return next((offering for offering in self.offerings if offering.service_id == service_id), None)

    def covers(self, county_code: str | None, district_code: str | None) -> bool:
        if county_code is None:
            return True
        if county_code not in self.counties:
            return False
        if not self.districts or district_code is None:
            return True
        return district_code in self.districts


def _offering(service_id: str, price: int, *slots: str) -> Offering:
    return Offering(service_id=service_id, base_price=price, slots=frozenset(slots))


# 北北基桃 + 台中，涵蓋官方樣本資料出現的活動範圍
_NORTH = frozenset({"01", "02", "03", "04"})
_TAICHUNG = frozenset({"08"})
_WIDE = _NORTH | _TAICHUNG | frozenset({"14", "15"})

VENDORS: tuple[Vendor, ...] = (
    # ---- 清潔類（官方素材出現：DUSKIN） ----
    Vendor(
        id="vendor-duskin",
        name="DUSKIN 樂清",
        intro="日系清潔品牌，家電清洗與居家清潔皆有專職技師。",
        rating=4.8,
        review_count=1240,
        supports_urgent=False,
        counties=_NORTH,
        offerings=(
            _offering("service-aircon", 1800, "weekday_morning", "weekday_afternoon"),
            _offering("service-washer", 1600, "weekday_morning", "weekday_afternoon"),
            _offering("service-cleaning", 3200, "weekday_morning", "weekday_afternoon", "weekend"),
        ),
    ),
    Vendor(
        id="vendor-cleanpro",
        name="潔沛家事服務",
        intro="在地中小型清潔團隊，可配合平日夜間與假日。",
        rating=4.5,
        review_count=386,
        supports_urgent=True,
        counties=_NORTH | _TAICHUNG,
        offerings=(
            _offering("service-aircon", 1500, "weekday_afternoon", "weekend", "evening"),
            _offering("service-washer", 1350, "weekday_afternoon", "weekend", "evening"),
            _offering("service-cleaning", 2600, "weekend", "evening"),
            _offering("service-housework", 420, "weekday_morning", "weekday_afternoon", "weekend"),
        ),
    ),
    Vendor(
        id="vendor-homekeeper",
        name="安家管家",
        intro="以計時家事為主，提供固定管家與長期配合方案。",
        rating=4.3,
        review_count=512,
        supports_urgent=False,
        counties=_WIDE,
        offerings=(
            _offering("service-cleaning", 2900, "weekday_morning", "weekday_afternoon"),
            _offering("service-housework", 380, "weekday_morning", "weekday_afternoon", "weekend"),
        ),
    ),
    # ---- 水電修繕 ----
    Vendor(
        id="vendor-fastfix",
        name="速修水電",
        intro="24 小時叫修，漏水、跳電、馬桶阻塞可當日到場。",
        rating=4.4,
        review_count=903,
        supports_urgent=True,
        counties=_NORTH,
        offerings=(_offering("service-repair", 1200, "weekday_morning", "weekday_afternoon", "weekend", "evening"),),
    ),
    Vendor(
        id="vendor-guanjia",
        name="冠家水電工程行",
        intro="老牌工程行，重視施工品質，需預約排程。",
        rating=4.7,
        review_count=248,
        supports_urgent=False,
        counties=_NORTH | _TAICHUNG,
        offerings=(_offering("service-repair", 950, "weekday_morning", "weekday_afternoon"),),
    ),
    Vendor(
        id="vendor-lightning",
        name="閃電到府維修",
        intro="以速度為主的維修派遣，夜間與假日不加價。",
        rating=4.1,
        review_count=1580,
        supports_urgent=True,
        counties=_WIDE,
        offerings=(_offering("service-repair", 1400, "weekend", "evening", "weekday_afternoon"),),
    ),
    # ---- 寄件（官方素材出現：黑貓） ----
    Vendor(
        id="vendor-blackcat",
        name="黑貓宅急便",
        intro="全台到府收件，冷藏冷凍配送皆可。",
        rating=4.6,
        review_count=5210,
        supports_urgent=True,
        counties=_WIDE,
        offerings=(_offering("service-shipping", 150, "weekday_morning", "weekday_afternoon", "weekend"),),
    ),
    Vendor(
        id="vendor-express711",
        name="7-ELEVEN 交貨便",
        intro="門市寄件取件，適合小件與低成本寄送。",
        rating=4.2,
        review_count=3140,
        supports_urgent=False,
        counties=_WIDE,
        offerings=(_offering("service-shipping", 70, "weekday_morning", "weekday_afternoon", "weekend", "evening"),),
    ),
    # ---- 餐廳訂位（官方素材出現：EZTABLE） ----
    Vendor(
        id="vendor-eztable",
        name="EZTABLE 簡單桌",
        intro="線上即時訂位，合作餐廳涵蓋聚餐與宴席。",
        rating=4.5,
        review_count=2260,
        supports_urgent=True,
        counties=_WIDE,
        offerings=(_offering("service-restaurant", 0, "weekday_afternoon", "weekend", "evening"),),
    ),
    # ---- 美食外送（官方素材出現：foodomo） ----
    Vendor(
        id="vendor-foodomo",
        name="foodomo",
        intro="社區周邊餐飲外送，支援大量訂餐。",
        rating=4.3,
        review_count=4180,
        supports_urgent=True,
        counties=_WIDE,
        offerings=(_offering("service-delivery", 60, "weekday_morning", "weekday_afternoon", "weekend", "evening"),),
    ),
    # ---- 商城購物 ----
    Vendor(
        id="vendor-shop711",
        name="7-ELEVEN 線上購物中心",
        intro="日用品與生鮮，可指定門市取貨。",
        rating=4.4,
        review_count=6120,
        supports_urgent=False,
        counties=_WIDE,
        offerings=(_offering("service-shopping", 0, "weekday_morning", "weekday_afternoon", "weekend", "evening"),),
    ),
)


@dataclass(frozen=True)
class MatchReason:
    """一條媒合理由——說明符合哪個條件、加了幾分。"""

    code: str
    label: str
    points: int

    def to_dict(self) -> dict:
        return {"code": self.code, "label": self.label, "points": self.points}


@dataclass(frozen=True)
class VendorMatch:
    """一家廠商的媒合結果。"""

    vendor: Vendor
    offering: Offering
    score: int
    reasons: list[MatchReason]
    concerns: list[str]

    def to_dict(self) -> dict:
        return {
            "vendorId": self.vendor.id,
            "vendorName": self.vendor.name,
            "intro": self.vendor.intro,
            "rating": self.vendor.rating,
            "reviewCount": self.vendor.review_count,
            "supportsUrgent": self.vendor.supports_urgent,
            "basePrice": self.offering.base_price,
            "slots": sorted(self.offering.slots),
            "slotLabels": [SLOTS.get(slot, slot) for slot in sorted(self.offering.slots)],
            "score": self.score,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "concerns": list(self.concerns),
            "computedBy": "rules",
            "dataSource": "competition_seed",
        }


def match(
    service_id: str,
    *,
    county_code: str | None = None,
    district_code: str | None = None,
    budget: int | None = None,
    slot: str | None = None,
    urgent: bool = False,
    limit: int = 3,
) -> list[VendorMatch]:
    """依命題明列的條件媒合廠商，回傳分數由高到低的 2–3 家比較清單。

    **服務範圍是硬條件**（不能服務就是不能服務），其餘皆為評分項：
    預算超標、無法配合時段、不支援加急都不會讓廠商消失，而是列進 `concerns`——
    使用者需要的是「有哪些選擇、各自的取捨是什麼」，不是一個沒有替代方案的結論。
    """
    results: list[VendorMatch] = []

    for vendor in VENDORS:
        offering = vendor.offering_for(service_id)
        if offering is None:
            continue
        if not vendor.covers(county_code, district_code):
            continue

        reasons: list[MatchReason] = []
        concerns: list[str] = []
        score = 0

        if county_code is not None:
            reasons.append(MatchReason("coverage", "服務範圍涵蓋你的地區", 20))
            score += 20

        # 評分：4.0 起算，每 0.1 分 2 點（滿分 5.0 → 20 點）
        rating_points = max(0, round((vendor.rating - 4.0) * 20))
        reasons.append(MatchReason("rating", f"評價 {vendor.rating}（{vendor.review_count} 則）", rating_points))
        score += rating_points

        if budget is not None:
            if offering.base_price <= budget:
                headroom = budget - offering.base_price
                points = 25 if headroom >= budget * 0.2 else 15
                reasons.append(MatchReason("budget", f"參考價 NT${offering.base_price} 在預算內", points))
                score += points
            else:
                over = offering.base_price - budget
                concerns.append(f"參考價 NT${offering.base_price}，超出預算 NT${over}")
                score -= 15

        if slot is not None:
            if slot in offering.slots:
                reasons.append(MatchReason("slot", f"可配合{SLOTS.get(slot, slot)}", 20))
                score += 20
            else:
                concerns.append(f"無法配合{SLOTS.get(slot, slot)}")
                score -= 20

        if urgent:
            if vendor.supports_urgent:
                reasons.append(MatchReason("urgent", "可加急，當日／隔日到場", 25))
                score += 25
            else:
                concerns.append("不提供加急，需照常排程")
                score -= 25

        results.append(VendorMatch(vendor=vendor, offering=offering, score=score, reasons=reasons, concerns=concerns))

    # 同分時以評價高者優先，讓排序完全確定（避免同樣輸入跑出不同順序）
    results.sort(key=lambda item: (-item.score, -item.vendor.rating, item.vendor.id))
    return results[:limit]
