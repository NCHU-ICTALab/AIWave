"""可重現的台灣廠商情境資料。

品牌名稱是人工維護的公開品牌白名單；Faker 只負責聯絡人、電話、地址、
案件與時間等展示資料，避免把隨機名稱誤認為真實合作廠商。
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker

SEED_VERSION = "vendor_demo_seed_v1"
SEED_NUMBER = 20260728
SOURCE_CHECKED_AT = "2026-07-28"
DATA_SOURCE = f"fake_vendor:{SEED_VERSION}"

TAIWAN_REGIONS = (
    ("01", "臺北市", "002", "大同區", "103"),
    ("01", "臺北市", "007", "信義區", "110"),
    ("01", "臺北市", "010", "內湖區", "114"),
    ("02", "新北市", "004", "永和區", "234"),
    ("02", "新北市", "005", "板橋區", "220"),
    ("02", "新北市", "012", "新店區", "231"),
    ("03", "基隆市", "001", "仁愛區", "200"),
    ("04", "桃園市", "001", "桃園區", "330"),
    ("04", "桃園市", "002", "中壢區", "320"),
    ("08", "臺中市", "001", "中區", "400"),
    ("08", "臺中市", "006", "西屯區", "407"),
    ("14", "臺南市", "001", "中西區", "700"),
    ("15", "高雄市", "001", "新興區", "800"),
    ("15", "高雄市", "011", "左營區", "813"),
)


def _source(label: str, url: str, *, observed_in_openpoint: bool = False) -> dict[str, Any]:
    return {
        "kind": "public_brand_reference",
        "label": label,
        "url": url,
        "checkedAt": SOURCE_CHECKED_AT,
        "observedInOpenpoint": observed_in_openpoint,
        "dataPolicy": "品牌名稱與服務分類有公開依據；價格、評分、時段與案件皆為競賽生成資料。",
    }


# 只在此處人工定義品牌。不得用 Faker 產生 vendor name。
BRAND_ALLOWLIST: tuple[dict[str, Any], ...] = (
    {
        "id": "vendor-prince-property", "name": "太子物業", "legalName": "太子物業管理顧問股份有限公司",
        "summary": "社區物業與生活服務整合窗口，展示情境涵蓋居家清潔、家事與修繕協調。",
        "serviceIds": ["service-cleaning", "service-housework", "service-repair"], "supportsUrgent": False,
        "rating": 4.7, "reviewCount": 862,
        "source": _source("OPENPOINT App 使用者觀察／太子企業公開資訊", "https://www.prince.com.tw/", observed_in_openpoint=True),
    },
    {
        "id": "vendor-prince-electric", "name": "王子水電", "legalName": "王子水電企業股份有限公司",
        "summary": "太子建設集團成員，展示情境提供居家水電修繕與到府檢測。",
        "serviceIds": ["service-repair"], "supportsUrgent": True,
        "rating": 4.8, "reviewCount": 516,
        "source": _source("王子水電公開公司資料／OPENPOINT App 使用者觀察", "https://www.104.com.tw/company/1a2x6bnjwy", observed_in_openpoint=True),
    },
    {
        "id": "vendor-duskin", "name": "DUSKIN 樂清", "legalName": "統一多拿滋股份有限公司樂清事業部",
        "summary": "居家與家電清潔服務，展示情境涵蓋冷氣、洗衣機與全室清潔。",
        "serviceIds": ["service-aircon", "service-washer", "service-cleaning"], "supportsUrgent": False,
        "rating": 4.8, "reviewCount": 1240,
        "source": _source("DUSKIN 樂清官方網站", "https://www.duskin.com.tw/"),
    },
    {
        "id": "vendor-blackcat", "name": "黑貓宅急便", "legalName": "統一速達股份有限公司",
        "summary": "常溫、低溫與到府收件配送服務。",
        "serviceIds": ["service-shipping"], "supportsUrgent": True,
        "rating": 4.7, "reviewCount": 5210,
        "source": _source("黑貓宅急便官方網站", "https://www.t-cat.com.tw/"),
    },
    {
        "id": "vendor-711-c2c", "name": "7-ELEVEN 交貨便", "legalName": "統一超商股份有限公司",
        "summary": "透過 7-ELEVEN 門市完成寄件與取件。",
        "serviceIds": ["service-shipping"], "supportsUrgent": False,
        "rating": 4.5, "reviewCount": 3140,
        "source": _source("7-ELEVEN 交貨便服務條款", "https://www.7-11.com.tw/form/accept.pdf"),
    },
    {
        "id": "vendor-711-myship", "name": "7-ELEVEN 賣貨便", "legalName": "統一數網股份有限公司",
        "summary": "小賣家開店、收款與超商物流整合服務。",
        "serviceIds": ["service-shipping", "service-shopping"], "supportsUrgent": False,
        "rating": 4.6, "reviewCount": 2895,
        "source": _source("7-ELEVEN 賣貨便服務條款", "https://myship.7-11.com.tw/Home/TermsOfServicePolicy"),
    },
    {
        "id": "vendor-foodomo", "name": "foodomo", "legalName": "foodomo 統一集團外送平台",
        "summary": "餐飲與生活用品外送整合服務。",
        "serviceIds": ["service-delivery"], "supportsUrgent": True,
        "rating": 4.4, "reviewCount": 4180,
        "source": _source("foodomo 官方網站", "https://www.foodomo.com/"),
    },
    {
        "id": "vendor-eztable", "name": "EZTABLE 簡單桌", "legalName": "三二三網路科技股份有限公司",
        "summary": "線上餐廳搜尋、優惠與訂位服務。",
        "serviceIds": ["service-restaurant"], "supportsUrgent": True,
        "rating": 4.6, "reviewCount": 2260,
        "source": _source("EZTABLE 官方網站", "https://tw.eztable.com/"),
    },
    {
        "id": "vendor-711-shop", "name": "7-ELEVEN 線上購物中心", "legalName": "統一超商股份有限公司",
        "summary": "商品預購、宅配與門市取貨服務。",
        "serviceIds": ["service-shopping"], "supportsUrgent": False,
        "rating": 4.5, "reviewCount": 6120,
        "source": _source("7-ELEVEN 線上購物中心", "https://www.7-11.com.tw/"),
    },
    {
        "id": "vendor-cosmed", "name": "康是美", "legalName": "統一生活事業股份有限公司",
        "summary": "健康、美妝與日常照護商品通路。",
        "serviceIds": ["service-shopping"], "supportsUrgent": False,
        "rating": 4.6, "reviewCount": 4380,
        "source": _source("康是美官方網站", "https://www.cosmed.com.tw/"),
    },
)

SERVICE_NAMES = {
    "service-aircon": "冷氣清洗",
    "service-washer": "洗衣機清洗",
    "service-cleaning": "專業清潔",
    "service-housework": "計時家事",
    "service-repair": "水電修繕",
    "service-shipping": "寄件服務",
    "service-restaurant": "餐廳訂位",
    "service-delivery": "美食外送",
    "service-shopping": "商城購物",
}

BASE_PRICES = {
    "service-aircon": 1800, "service-washer": 1600, "service-cleaning": 3200,
    "service-housework": 500, "service-repair": 1200, "service-shipping": 70,
    "service-restaurant": 0, "service-delivery": 60, "service-shopping": 0,
}

SLOTS = ["weekday_morning", "weekday_afternoon", "weekend", "evening"]


def build_vendor_seed() -> dict[str, Any]:
    """每次以相同 seed 重建完全相同的 10/30/120 情境。"""
    fake = Faker("zh_TW")
    Faker.seed(SEED_NUMBER)
    fake.seed_instance(SEED_NUMBER)
    now = datetime(2026, 7, 28, 9, 0, tzinfo=timezone(timedelta(hours=8)))

    vendors = deepcopy(list(BRAND_ALLOWLIST))
    locations: list[dict[str, Any]] = []
    offerings: list[dict[str, Any]] = []
    for vendor_index, vendor in enumerate(vendors):
        for branch_index in range(3):
            # 每個品牌至少有一個臺北展示據點，讓 Hero 情境可在同一地區比較；
            # 另外兩個據點再依 seed 分散至不同縣市。
            region_index = 0 if branch_index == 0 else (vendor_index * 2 + branch_index) % len(TAIWAN_REGIONS)
            region = TAIWAN_REGIONS[region_index]
            county_code, county_name, district_code, district_name, postal_code = region
            street = fake.street_address().replace(county_name, "").replace(district_name, "").strip()
            locations.append({
                "id": f"loc-{vendor_index + 1:02d}-{branch_index + 1:02d}",
                "vendorId": vendor["id"],
                "name": f"{vendor['name']} {district_name}服務站",
                "countyCode": county_code, "countyName": county_name,
                "districtCode": district_code, "districtName": district_name,
                "postalCode": postal_code,
                "address": f"{postal_code}{county_name}{district_name}{street}",
                "phone": fake.phone_number(), "contactName": fake.name(), "serviceRadiusKm": 25,
                "dataSource": DATA_SOURCE,
            })
        for service_id in vendor["serviceIds"]:
            adjustment = (vendor_index % 3 - 1) * 100
            base_price = max(0, BASE_PRICES[service_id] + adjustment)
            offerings.append({
                "id": f"off-{vendor['id'].removeprefix('vendor-')}-{service_id.removeprefix('service-')}",
                "vendorId": vendor["id"], "serviceId": service_id,
                "name": f"{vendor['name']}・{SERVICE_NAMES[service_id]}",
                "description": f"{SERVICE_NAMES[service_id]}競賽展示方案，實際價格以廠商報價為準。",
                "basePrice": base_price, "currency": "TWD",
                "pricingUnit": "次" if service_id != "service-housework" else "小時",
                "slots": SLOTS if vendor["supportsUrgent"] else SLOTS[:3],
                "supportsUrgent": vendor["supportsUrgent"], "dataSource": DATA_SOURCE,
            })

    inquiries: list[dict[str, Any]] = []
    quotes: list[dict[str, Any]] = []
    statuses = ["submitted", "reviewing", "quoted", "accepted", "in_service", "completed"]
    for index in range(120):
        offering = offerings[index % len(offerings)]
        vendor = next(item for item in vendors if item["id"] == offering["vendorId"])
        location = locations[(index * 7) % len(locations)]
        created = now - timedelta(days=index % 45, hours=index % 11)
        inquiry_id = f"vinq-20260728-{index + 1:04d}"
        quote_id = f"vqt-20260728-{index + 1:04d}"
        status = statuses[index % len(statuses)]
        total = offering["basePrice"] + (index % 4) * 100
        inquiries.append({
            "id": inquiry_id, "accountId": f"demo-user-{index % 12 + 1:02d}",
            "serviceId": offering["serviceId"], "vendorId": vendor["id"],
            "consumer": {"name": fake.name(), "phone": fake.phone_number(), "email": fake.safe_email()},
            "location": {key: location[key] for key in (
                "countyCode", "countyName", "districtCode", "districtName", "postalCode", "address"
            )},
            "preferredSlots": [SLOTS[index % len(SLOTS)]],
            "budget": max(total, 500), "urgency": "urgent" if index % 9 == 0 else "normal",
            "answers": {"description": fake.sentence(nb_words=10)},
            "summary": f"{location['districtName']}的{SERVICE_NAMES[offering['serviceId']]}需求",
            "status": status, "externalReference": f"DEMO-{index + 1:05d}",
            "version": 1, "createdAt": created.isoformat(), "updatedAt": created.isoformat(),
            "dataSource": DATA_SOURCE,
        })
        quote_status = "accepted" if status in {"accepted", "in_service", "completed"} else "proposed"
        quotes.append({
            "id": quote_id, "inquiryId": inquiry_id, "vendorId": vendor["id"],
            "items": [{"name": SERVICE_NAMES[offering["serviceId"]], "quantity": 1,
                       "unitPrice": total, "amount": total}],
            "subtotal": total, "total": total, "currency": "TWD", "status": quote_status,
            "validUntil": (created + timedelta(days=7)).date().isoformat(),
            "createdAt": (created + timedelta(hours=2)).isoformat(), "dataSource": DATA_SOURCE,
        })

    return {
        "vendors": vendors, "locations": locations, "offerings": offerings,
        "inquiries": inquiries, "quotes": quotes, "orders": [],
    }
