"""Partner API fake 的多 Provider 情境資料(六大生活場景)。

品牌依產品負責人 2026-07-30 提供的「廠商and表單.md」正式名單(統一集團公開名單,
出處 https://www.pecos.com.tw/group.html)與既有 vendor_seed 核准 allowlist。
價格、評分、時段與案件皆為競賽生成的展示資料,實際以各品牌官方為準。

時段以 ``PARTNER_SEED_BASE_DATE``(預設 2026-07-30,與 DEMO_TODAY 對齊)為基準
相對生成,確保「明天有空檔」永遠成立且完全可重現。
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fake_upstreams.vendor_seed import BRAND_ALLOWLIST

SEED_VERSION = "partner-demo-v5"
TAIPEI = timezone(timedelta(hours=8))

#: 場景代碼(可擴充,不寫死六格):food 食 / med 醫 / home 住 / move 行 / pre 預 / fun 樂
SCENES = ("food", "med", "home", "move", "pre", "fun")


def _base_date() -> date:
    raw = os.environ.get("PARTNER_SEED_BASE_DATE", "2026-07-30")
    return date.fromisoformat(raw)


def _source(label: str, url: str) -> dict[str, Any]:
    return {
        "kind": "public_brand_reference", "label": label, "url": url,
        "checkedAt": "2026-07-30",
        "dataPolicy": "品牌名稱與服務分類有公開依據;價格、評分、時段與案件皆為競賽生成資料。",
    }


#: 廠商and表單.md 補充的統一集團品牌(不在 vendor_seed 舊 allowlist 中)。
EXTRA_BRANDS: tuple[dict[str, Any], ...] = (
    {
        "id": "vendor-21plus", "name": "21PLUS",
        "summary": "二十一世紀生活事業(統一超商 100%)的休閒餐廳店型,展示情境提供線上訂位。",
        "rating": 4.5, "reviewCount": 1860,
        "source": _source("統一集團官方名單(二十一世紀生活事業)", "https://www.pecos.com.tw/click/group-18.html"),
    },
    {
        "id": "vendor-smile", "name": "速邁樂加油站 Smile",
        "summary": "統一精工加油站通路,展示情境提供精緻洗車線上預約(原線下 APP/現場模式)。",
        "rating": 4.4, "reviewCount": 980,
        "source": _source("統一精工速邁樂官方網站", "https://www.mech-smile.com.tw/"),
    },
    {
        "id": "vendor-uni-resort", "name": "統一渡假村 Uni Resort",
        "summary": "統合開發渡假村體系,展示情境提供馬武督/谷關線上訂房。",
        "rating": 4.6, "reviewCount": 2140,
        "source": _source("統一渡假村官方網站", "https://ma.uni-resort.com.tw/"),
    },
    {
        "id": "vendor-iopenmall", "name": "iOPEN Mall",
        "summary": "統一超商建置的網路開店平台,展示情境提供商城購物與門市取貨。",
        "rating": 4.5, "reviewCount": 3560,
        "source": _source("iOPEN Mall 官方網站", "https://www.iopenmall.tw/"),
    },
    {
        "id": "vendor-ibon-ticket", "name": "ibon 售票",
        "summary": "展演賽事與景點/交通票券售票系統,展示情境提供非劃位票券購買。",
        "rating": 4.4, "reviewCount": 5120,
        "source": _source("ibon 售票系統(景點/交通)", "https://tour.ibon.com.tw/"),
    },
)


def _brand(vendor_id: str) -> dict[str, Any]:
    for item in (*BRAND_ALLOWLIST, *EXTRA_BRANDS):
        if item["id"] == vendor_id:
            return item
    raise KeyError(vendor_id)


#: 每個 Provider 的場景定義。offerings 的 domainType 對應 core/catalog/domains.py。
#: fulfillmentKind: booking(有時段/資源)或 commerce(商品下單,無時段)。
PROVIDER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "vendor-prince-electric", "scene": "home", "brand": True,
        "resources": [
            {"suffix": "team-a", "name": "水電一組", "kind": "service_team"},
            {"suffix": "team-b", "name": "水電二組", "kind": "service_team"},
        ],
        "offerings": [
            {
                "id": "off-prince-electric-repair", "name": "水電修繕・到府檢測",
                "domainType": "home_repair", "fulfillmentKind": "booking",
                "basePrice": 1200, "pricingUnit": "次", "cancelPolicyHours": 24,
                "description": "含 30 分鐘檢測與簡易維修;零件另計並事前報價。",
            },
            {
                "id": "off-prince-electric-repair-urgent", "name": "急件修繕・4 小時內到府",
                "domainType": "home_repair", "fulfillmentKind": "booking",
                "basePrice": 1800, "pricingUnit": "次", "cancelPolicyHours": 4,
                "description": "漏水、跳電等急件;夜間 22:00 後不提供。",
            },
        ],
        "slot_hours": ((9, 2), (14, 2), (16, 2)),
    },
    {
        "id": "vendor-duskin", "scene": "home", "brand": True,
        "resources": [
            {"suffix": "clean-a", "name": "清潔一組", "kind": "service_team"},
        ],
        "offerings": [
            {
                "id": "off-duskin-cleaning", "name": "全室清潔",
                "domainType": "home_cleaning", "fulfillmentKind": "booking",
                "basePrice": 3200, "pricingUnit": "次", "cancelPolicyHours": 24,
                "description": "3 小時全室清潔,含浴廁與廚房。",
            },
            {
                "id": "off-duskin-aircon", "name": "冷氣清洗",
                "domainType": "home_cleaning", "fulfillmentKind": "booking",
                "basePrice": 1800, "pricingUnit": "台", "cancelPolicyHours": 24,
                "description": "分離式冷氣機體與濾網深層清洗。",
            },
            {
                "id": "off-duskin-housework", "name": "計時家事服務",
                "domainType": "home_cleaning", "fulfillmentKind": "booking",
                "basePrice": 500, "pricingUnit": "小時", "cancelPolicyHours": 24,
                "description": "打掃、洗衣、購物、澆花等家務可組合,依鐘點計費。",
            },
        ],
        "slot_hours": ((9, 3), (14, 3)),
    },
    {
        "id": "vendor-21plus", "scene": "food", "brand": True,
        "resources": [
            {"suffix": "table-2", "name": "2 人桌", "kind": "table"},
            {"suffix": "table-4", "name": "4 人桌", "kind": "table"},
            {"suffix": "room", "name": "包廂", "kind": "table"},
        ],
        "offerings": [
            {
                "id": "off-21plus-dinner", "name": "21PLUS 晚餐訂位",
                "domainType": "dining_reservation", "fulfillmentKind": "booking",
                "basePrice": 0, "pricingUnit": "位", "cancelPolicyHours": 2,
                "description": "訂位免費;餐費依店內消費。座位偏好與特殊需求可於表單填寫。",
            },
            {
                "id": "off-21plus-lunch", "name": "21PLUS 午餐訂位",
                "domainType": "dining_reservation", "fulfillmentKind": "booking",
                "basePrice": 0, "pricingUnit": "位", "cancelPolicyHours": 2,
                "description": "訂位免費;餐費依店內消費。",
            },
            {
                # 店型=方案(2026-07-31 拍板):21TOGO 為 7-ELEVEN 店中店外帶型態
                "id": "off-21togo-takeout", "name": "21TOGO 外帶餐盒(門市自取)",
                "domainType": "food_delivery", "fulfillmentKind": "commerce",
                "basePrice": 139, "pricingUnit": "份", "cancelPolicyHours": 0,
                "description": "外帶/外送預訂(C 型);製作前可取消。",
            },
        ],
        "slot_hours": ((12, 2), (18, 2), (19, 2)),
    },
    {
        # 行(洗車):廠商and表單.md 指出線上化程度最低的差異化切入點;
        # 原服務走 APP/現場,本平台示範線上預約表單(A 型:車牌/車種/項目/據點/時段)。
        "id": "vendor-smile", "scene": "move", "brand": True,
        "resources": [
            {"suffix": "bay-1", "name": "洗車機位一", "kind": "wash_bay"},
            {"suffix": "bay-2", "name": "洗車機位二", "kind": "wash_bay"},
        ],
        "offerings": [
            {
                "id": "off-smile-wash-sedan", "name": "精緻洗車(轎車)",
                "domainType": "car_wash", "fulfillmentKind": "booking",
                "basePrice": 450, "pricingUnit": "次", "cancelPolicyHours": 2,
                "description": "展示價格;OPENPOINT 可折抵(官方兌換轎車 150 點)。",
            },
            {
                "id": "off-smile-wash-suv", "name": "精緻洗車(休旅車)",
                "domainType": "car_wash", "fulfillmentKind": "booking",
                "basePrice": 520, "pricingUnit": "次", "cancelPolicyHours": 2,
                "description": "展示價格;OPENPOINT 可折抵(官方兌換休旅車 170 點)。",
            },
        ],
        "slot_hours": ((10, 1), (14, 1), (16, 1)),
    },
    {
        "id": "vendor-blackcat", "scene": "move", "brand": True,
        "resources": [
            {"suffix": "pickup", "name": "到府收件車班", "kind": "pickup_route"},
        ],
        "offerings": [
            {
                "id": "off-blackcat-pickup", "name": "宅配到府收件(常溫)",
                "domainType": "shipping_pickup", "fulfillmentKind": "booking",
                "basePrice": 130, "pricingUnit": "件", "cancelPolicyHours": 2,
                "description": "司機於選定時段到府收件,常溫 60 才內。",
            },
            {
                "id": "off-blackcat-pickup-cold", "name": "宅配到府收件(低溫)",
                "domainType": "shipping_pickup", "fulfillmentKind": "booking",
                "basePrice": 190, "pricingUnit": "件", "cancelPolicyHours": 2,
                "description": "低溫冷藏收件;需自備保冷包裝。",
            },
        ],
        "slot_hours": ((10, 3), (14, 3), (17, 3)),
    },
    {
        "id": "vendor-cosmed", "scene": "med", "brand": True,
        "resources": [
            {"suffix": "pharmacist", "name": "門市藥師", "kind": "pharmacist"},
        ],
        "offerings": [
            {
                "id": "off-cosmed-rx-pickup", "name": "處方箋門市領藥預約",
                "domainType": "pharmacy_pickup", "fulfillmentKind": "booking",
                "basePrice": 0, "pricingUnit": "次", "cancelPolicyHours": 2,
                "description": "上傳處方箋辨識結果經本人確認後,預約門市藥師領藥時段。"
                               "僅提供辨識與領藥媒合展示,不提供診斷或用藥建議。",
            },
        ],
        "slot_hours": ((10, 1), (15, 1), (19, 1)),
    },
    {
        "id": "vendor-711-shop", "scene": "pre", "brand": True,
        "resources": [],
        "offerings": [
            {
                "id": "off-711-shop-preorder-coffee", "name": "i 預購・咖啡寄杯 10 杯組",
                "domainType": "ec_preorder", "fulfillmentKind": "commerce",
                "basePrice": 450, "pricingUnit": "組", "cancelPolicyHours": 0,
                "description": "門市取貨;出貨前可取消。",
            },
            {
                "id": "off-711-shop-preorder-rice", "name": "i 預購・良食米 5kg",
                "domainType": "ec_preorder", "fulfillmentKind": "commerce",
                "basePrice": 320, "pricingUnit": "包", "cancelPolicyHours": 0,
                "description": "門市取貨或宅配;出貨前可取消。",
            },
        ],
        "slot_hours": (),
    },
    {
        # 食(外送):foodomo,表單文件 C 型(外帶/外送預訂)。
        "id": "vendor-foodomo", "scene": "food", "brand": True,
        "resources": [],
        "offerings": [
            {
                "id": "off-foodomo-meal", "name": "foodomo・熱食外送",
                "domainType": "food_delivery", "fulfillmentKind": "commerce",
                "basePrice": 259, "pricingUnit": "餐", "cancelPolicyHours": 0,
                "description": "合作餐廳熱食外送;店家接單前可取消。展示價格。",
            },
            {
                "id": "off-foodomo-grocery", "name": "foodomo・生活用品外送",
                "domainType": "food_delivery", "fulfillmentKind": "commerce",
                "basePrice": 199, "pricingUnit": "單", "cancelPolicyHours": 0,
                "description": "日用品快送;店家接單前可取消。展示價格。",
            },
        ],
        "slot_hours": (),
    },
    {
        # 行(寄件):7-ELEVEN 交貨便,表單文件 預 3(C2C 寄件單)。
        "id": "vendor-711-c2c", "scene": "move", "brand": True,
        "resources": [],
        "offerings": [
            {
                "id": "off-711-c2c-standard", "name": "交貨便・店到店(常溫)",
                "domainType": "c2c_shipping", "fulfillmentKind": "commerce",
                "basePrice": 60, "pricingUnit": "件", "cancelPolicyHours": 0,
                "description": "門市寄件、門市取件;門市收件前可取消。",
            },
            {
                "id": "off-711-c2c-frozen", "name": "交貨便・店到店(冷凍)",
                "domainType": "c2c_shipping", "fulfillmentKind": "commerce",
                "basePrice": 150, "pricingUnit": "件", "cancelPolicyHours": 0,
                "description": "冷凍店到店;門市收件前可取消。",
            },
        ],
        "slot_hours": (),
    },
    {
        # 預(EC):iOPEN Mall,表單文件 預 1(一般購物結帳)。
        "id": "vendor-iopenmall", "scene": "pre", "brand": True,
        "resources": [],
        "offerings": [
            {
                "id": "off-iopenmall-home", "name": "iOPEN Mall・居家小物組",
                "domainType": "ec_preorder", "fulfillmentKind": "commerce",
                "basePrice": 690, "pricingUnit": "組", "cancelPolicyHours": 0,
                "description": "門市取貨或宅配;出貨前可取消。展示商品。",
            },
        ],
        "slot_hours": (),
    },
    {
        # 樂(票券):ibon 售票,非劃位型(B 型:景點/交通票券)。劃位型列後續,不虛構。
        "id": "vendor-ibon-ticket", "scene": "fun", "brand": True,
        "resources": [],
        "offerings": [
            {
                "id": "off-ibon-attraction", "name": "景點門票・傳藝中心全票",
                "domainType": "ticket_purchase", "fulfillmentKind": "commerce",
                "basePrice": 150, "pricingUnit": "張", "cancelPolicyHours": 0,
                "description": "非劃位電子票;出票前可取消。展示票價。",
            },
            {
                "id": "off-ibon-transport", "name": "交通票券・高鐵國旅聯票",
                "domainType": "ticket_purchase", "fulfillmentKind": "commerce",
                "basePrice": 1490, "pricingUnit": "張", "cancelPolicyHours": 0,
                "description": "非劃位聯票;出票前可取消。展示票價。",
            },
        ],
        "slot_hours": (),
    },
    {
        # 樂:統一渡假村線上訂房(C 型訂房表單;展示以一晚為單位)。
        "id": "vendor-uni-resort", "scene": "fun", "brand": True,
        "locations": (
            ("04", "桃園市", "090", "復興區", "336", "馬武督渡假會議中心"),
            ("08", "臺中市", "029", "和平區", "424", "谷關溫泉養生會館"),
        ),
        "resources": [
            {"suffix": "room-double", "name": "標準雙人房", "kind": "room"},
            {"suffix": "room-family", "name": "家庭四人房", "kind": "room"},
        ],
        "offerings": [
            {
                "id": "off-uniresort-stay", "name": "渡假村住宿(一晚)",
                "domainType": "resort_booking", "fulfillmentKind": "booking",
                "basePrice": 4200, "pricingUnit": "晚", "cancelPolicyHours": 72,
                "description": "展示價格;含早餐,加購溫泉/接駁可於備註填寫。入住 15:00、退房 11:00。",
            },
            {
                "id": "off-uniresort-spring", "name": "溫泉湯屋(2 小時)",
                "domainType": "resort_booking", "fulfillmentKind": "booking",
                "basePrice": 1200, "pricingUnit": "次", "cancelPolicyHours": 24,
                "description": "展示價格;谷關館溫泉湯屋時段預約。",
            },
        ],
        "slot_hours": ((15, 20), (10, 2)),
    },
)

#: fake 與平台共用的 Demo API key 對應(fake 端驗 key、平台端拿同一把 key 呼叫)。
DEFAULT_PARTNER_KEYS: dict[str, str] = {
    "vendor-prince-electric": "aiwave-partner",
    "vendor-duskin": "aiwave-partner-duskin",
    "vendor-21plus": "aiwave-partner-21plus",
    "vendor-smile": "aiwave-partner-smile",
    "vendor-blackcat": "aiwave-partner-blackcat",
    "vendor-cosmed": "aiwave-partner-cosmed",
    "vendor-711-shop": "aiwave-partner-711shop",
    "vendor-uni-resort": "aiwave-partner-resort",
    "vendor-foodomo": "aiwave-partner-foodomo",
    "vendor-711-c2c": "aiwave-partner-711c2c",
    "vendor-iopenmall": "aiwave-partner-iopenmall",
    "vendor-ibon-ticket": "aiwave-partner-ibonticket",
}


def _locations_for(spec: dict[str, Any]) -> list[dict[str, Any]]:
    provider_id = spec["id"]
    name = _brand(provider_id)["name"]
    # 與 vendor_seed 相同的據點生成規則不可重用(它綁 Faker 全域序),
    # 這裡改為固定據點,維持完全可重現;spec 可自帶具名據點(如渡假村各館)。
    districts = spec.get("locations") or (
        ("01", "臺北市", "007", "信義區", "110"),
        ("01", "臺北市", "010", "內湖區", "114"),
        ("02", "新北市", "005", "板橋區", "220"),
    )
    rows = []
    for index, entry in enumerate(districts):
        county_code, county, district_code, district, postal = entry[:5]
        site_name = entry[5] if len(entry) > 5 else f"{name} {district}服務點"
        rows.append({
            "id": f"loc-{provider_id.removeprefix('vendor-')}-{index + 1:02d}",
            "providerId": provider_id,
            "name": site_name,
            "countyCode": county_code, "countyName": county,
            "districtCode": district_code, "districtName": district,
            "postalCode": postal,
            "address": f"{postal}{county}{district}示範路 {index + 1} 號",
            "phone": f"02-2726-{1000 + index:04d}",
        })
    return rows


def build_partner_seed() -> dict[str, dict[str, Any]]:
    """回傳 provider_id → {catalog, availability, bookings, webhook}。"""
    base = _base_date()
    providers: dict[str, dict[str, Any]] = {}
    for spec in PROVIDER_SPECS:
        provider_id = spec["id"]
        brand = _brand(provider_id)
        provider_info = {
            "id": provider_id, "name": brand["name"], "scene": spec["scene"],
            "summary": brand["summary"], "rating": brand["rating"],
            "reviewCount": brand["reviewCount"], "placeholder": False,
            "source": brand["source"],
        }
        locations = _locations_for(spec)
        resources = [
            {
                "id": f"resource-{provider_id.removeprefix('vendor-')}-{item['suffix']}",
                "providerId": provider_id, "name": item["name"], "kind": item["kind"],
            }
            for item in spec["resources"]
        ]
        offerings = []
        for offering in spec["offerings"]:
            offerings.append({
                **offering,
                "providerId": provider_id, "currency": "TWD",
                "locationIds": [item["id"] for item in locations],
                "dataSource": f"fake_partner:{SEED_VERSION}",
            })
        slots: list[dict[str, Any]] = []
        bookable = [item for item in offerings if item["fulfillmentKind"] == "booking"]
        if bookable and spec["slot_hours"]:
            for day in range(1, 8):  # 明天起 7 天
                slot_date = base + timedelta(days=day)
                for hour_index, (hour, duration) in enumerate(spec["slot_hours"]):
                    offering = bookable[(day + hour_index) % len(bookable)]
                    resource = resources[(day + hour_index) % len(resources)] if resources else None
                    location = locations[hour_index % len(locations)]
                    start = datetime.combine(slot_date, time(hour, 0), tzinfo=TAIPEI)
                    slots.append({
                        "id": f"slot-{provider_id.removeprefix('vendor-')}-{day}-{hour_index + 1}",
                        "providerId": provider_id,
                        "offeringId": offering["id"],
                        "locationId": location["id"],
                        "resourceId": resource["id"] if resource else None,
                        "startsAt": start.isoformat(),
                        "endsAt": (start + timedelta(hours=duration)).isoformat(),
                        "status": "available", "capacity": 1,
                    })
        providers[provider_id] = {
            "catalog": {
                "seedVersion": SEED_VERSION,
                "provider": provider_info,
                "locations": locations,
                "offerings": offerings,
                "resources": resources,
            },
            "availability": slots,
            "bookings": [],
            "webhook": None,
        }
    return providers
