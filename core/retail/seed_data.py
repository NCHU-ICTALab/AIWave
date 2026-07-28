"""`demo_seed_v1` 的門市商品／庫存情境；fake upstream 與離線 adapter 共用。"""

STORES = (
    {
        "id": "qingchuan",
        "storeName": "7-ELEVEN 晴川門市",
        "district": "大同區",
        "address": "台北市大同區民權西路 100 號",
        "capabilities": ["列印", "取貨", "寄件", "ATM", "CITY CAFE"],
        "distanceMeters": 280,
        "inventory": {"limited-cup": 0, "tissue-pack": 8},
    },
    {
        "id": "zhongxing",
        "storeName": "7-ELEVEN 中興門市",
        "district": "中山區",
        "address": "台北市中山區中山北路二段 88 號",
        "capabilities": ["列印", "取貨", "寄件", "ATM", "CITY CAFE"],
        "distanceMeters": 920,
        "inventory": {"limited-cup": 12, "tissue-pack": 4},
    },
    {
        "id": "minsheng",
        "storeName": "7-ELEVEN 民生門市",
        "district": "大同區",
        "address": "台北市大同區民生西路 210 號",
        "capabilities": ["取貨", "ATM", "CITY CAFE"],
        "distanceMeters": 510,
        "inventory": {"limited-cup": 3, "tissue-pack": 10},
    },
)

PRODUCTS = {
    "limited-cup": {"name": "吉伊卡哇限定杯", "keywords": ("吉伊卡哇", "限定杯", "聯名杯")},
    "tissue-pack": {"name": "舒適衛生紙補貨組", "keywords": ("衛生紙", "補貨", "日用品")},
}
