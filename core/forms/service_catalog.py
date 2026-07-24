"""服務目錄與題組定義——**單一事實來源**。

九項服務＝官方 `raw_data/相關主檔設定.json` 八項＋商城購物。Web 表單、AI 對話引導、
（未來）LINE 與 MCP 都讀這一份；新增服務只要在這裡加一筆，不必改前端程式。

題型全數沿用官方 `pms_form_topic.type`（1–10）；跳題放 `feature.skipLogic`（ADR-0002）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    Form,
    Group,
    Option,
    ServiceAction,
    SkipLogic,
    Topic,
    TopicType,
)


@dataclass(frozen=True)
class ServiceInfo:
    """服務目錄項目（對齊 cms_homepage_service）。"""

    id: str
    name: str
    category: str
    summary: str
    partner: str
    glyph: str


SERVICES: tuple[ServiceInfo, ...] = (
    ServiceInfo("service-washer", "洗衣機清洗", "居家維護", "到府拆洗與基礎檢測", "專業清潔夥伴", "洗"),
    ServiceInfo("service-aircon", "冷氣清洗", "居家維護", "壁掛式冷氣深層清潔", "專業清潔夥伴", "冷"),
    ServiceInfo("service-cleaning", "專業清潔", "居家維護", "居家空間重點清潔", "社區合作夥伴", "潔"),
    ServiceInfo("service-housework", "計時家事", "生活支援", "兩小時計時家事協助", "生活服務夥伴", "家"),
    ServiceInfo("service-repair", "水電修繕", "生活支援", "初步判斷並安排到府", "安心修繕", "修"),
    ServiceInfo("service-shipping", "寄件服務", "生活支援", "黑貓宅急便到店寄件", "黑貓宅急便", "寄"),
    ServiceInfo("service-restaurant", "餐廳訂位", "餐飲購物", "依人數與時段媒合餐廳", "統一集團餐飲", "訂"),
    ServiceInfo("service-delivery", "美食外送", "餐飲購物", "附近餐點與情境推薦", "外送合作夥伴", "送"),
    ServiceInfo("service-shopping", "商城購物", "餐飲購物", "日用品補貨並套用優惠", "iOPEN Mall", "購"),
)

# 到府服務共用的日期／時段題（可預約範圍：明日起 14 天內）
_VISIT_DATE_OFFSET = (1, 14)
_SLOTS = (("morning", "上午 09:00–12:00"), ("afternoon", "下午 13:00–17:00"), ("evening", "晚上 18:00–21:00"))


def _options(items: tuple[tuple[str, str], ...], base: int) -> list[Option]:
    return [Option(id=base + i, value=value, option_name=label) for i, (value, label) in enumerate(items)]


def _visit_topics(start_sort: int) -> list[Topic]:
    """到府服務的『希望日期＋希望時段』。"""
    return [
        Topic(
            id=90 + start_sort, key="date", type=TopicType.DATE, title="希望日期",
            is_required=True, sort=start_sort,
            start_date_offset_days=_VISIT_DATE_OFFSET[0], end_date_offset_days=_VISIT_DATE_OFFSET[1],
            hint="可預約展示基準日後 14 天內的時段",
        ),
        Topic(
            id=91 + start_sort, key="slot", type=TopicType.SINGLE, title="希望時段",
            is_required=True, sort=start_sort + 1, options=_options(_SLOTS, 9100),
        ),
    ]


def _form(
    *, form_id: int, service_id: str, name: str, action: ServiceAction,
    action_label: str, data_use: str, topics: list[Topic],
) -> Form:
    return Form(
        id=form_id, name=name, service_id=service_id, action=action,
        action_label=action_label, data_use=data_use,
        groups=[Group(id=form_id * 10, name=name, sort=1, topics=topics)],
    )


def _washer_form() -> Form:
    return _form(
        form_id=101, service_id="service-washer", name="洗衣機清洗",
        action=ServiceAction.INQUIRY, action_label="建立清洗諮詢",
        data_use="設備類型、數量與時段只用於估價及安排到府服務",
        topics=[
            Topic(id=1, key="machineType", type=TopicType.SINGLE, title="洗衣機類型",
                  is_required=True, sort=1,
                  options=_options((("top", "直立式"), ("drum", "滾筒式")), 1010)),
            Topic(id=2, key="quantity", type=TopicType.SHORT_TEXT, title="清洗台數",
                  is_required=True, sort=2, is_number_only=True, min_value=1, max_value=5),
            *_visit_topics(3),
        ],
    )


def _aircon_form() -> Form:
    return _form(
        form_id=102, service_id="service-aircon", name="冷氣清洗",
        action=ServiceAction.INQUIRY, action_label="建立冷氣清洗諮詢",
        data_use="機型、數量與時段只用於估價及媒合清潔夥伴",
        topics=[
            Topic(id=1, key="airconType", type=TopicType.SINGLE, title="冷氣類型",
                  is_required=True, sort=1,
                  options=_options((("split", "分離式"), ("window", "窗型")), 1020)),
            Topic(id=2, key="quantity", type=TopicType.SHORT_TEXT, title="清洗台數",
                  is_required=True, sort=2, is_number_only=True, min_value=1, max_value=5),
            *_visit_topics(3),
        ],
    )


def _cleaning_form() -> Form:
    return _form(
        form_id=103, service_id="service-cleaning", name="專業清潔",
        action=ServiceAction.INQUIRY, action_label="建立居家清潔諮詢",
        data_use="空間與清潔重點只用於估算工時及媒合服務人員",
        topics=[
            Topic(id=1, key="homeSize", type=TopicType.SINGLE, title="居家坪數",
                  is_required=True, sort=1,
                  options=_options((("small", "20 坪以下"), ("medium", "21–35 坪"), ("large", "36 坪以上")), 1030)),
            Topic(id=2, key="focusArea", type=TopicType.SINGLE, title="主要清潔區域",
                  is_required=True, sort=2,
                  options=_options((("kitchen", "廚房"), ("bathroom", "浴室"), ("whole", "全屋重點")), 1040)),
            *_visit_topics(3),
        ],
    )


def _housework_form() -> Form:
    return _form(
        form_id=104, service_id="service-housework", name="計時家事",
        action=ServiceAction.RESERVATION, action_label="預約計時家事",
        data_use="工作內容與時段只用於安排合適的服務人員",
        topics=[
            Topic(id=1, key="hours", type=TopicType.SINGLE, title="服務時數",
                  is_required=True, sort=1,
                  options=_options((("2", "2 小時"), ("3", "3 小時"), ("4", "4 小時")), 1050)),
            Topic(id=2, key="task", type=TopicType.SINGLE, title="主要工作",
                  is_required=True, sort=2,
                  options=_options((("clean", "日常清潔"), ("organize", "收納整理"), ("laundry", "洗曬衣物")), 1060)),
            *_visit_topics(3),
        ],
    )


# 修繕「其他」選項 id——跳題條件要引用它
_REPAIR_OTHER = 1073


def _repair_form() -> Form:
    return _form(
        form_id=105, service_id="service-repair", name="水電修繕",
        action=ServiceAction.INQUIRY, action_label="建立修繕諮詢",
        data_use="問題類型與說明只提供給媒合後的修繕夥伴判斷",
        topics=[
            Topic(id=1, key="repairType", type=TopicType.SINGLE, title="修繕項目",
                  is_required=True, sort=1,
                  options=_options((("plumbing", "水管／馬桶"), ("lighting", "燈具／開關"),
                                    ("outlet", "插座"), ("other", "其他")), 1070)),
            # 只有選「其他」才追問細節——跳題規則存 feature.skipLogic
            Topic(id=2, key="detail", type=TopicType.LONG_TEXT, title="問題說明",
                  is_required=True, sort=2,
                  hint="請簡述現象，不要填寫門牌或其他敏感資料",
                  skip_logic=SkipLogic(topic_id=1, answer_in=[_REPAIR_OTHER])),
            Topic(id=3, key="urgency", type=TopicType.SINGLE, title="緊急程度",
                  is_required=True, sort=3,
                  options=_options((("normal", "一般，可安排時段"), ("soon", "希望 48 小時內")), 1080)),
        ],
    )


def _shipping_form() -> Form:
    return _form(
        form_id=106, service_id="service-shipping", name="寄件服務",
        action=ServiceAction.SHIPMENT, action_label="建立寄件單",
        data_use="包裹規格與寄件門市只用於產生黑貓寄件流程",
        topics=[
            Topic(id=1, key="parcelSize", type=TopicType.SINGLE, title="包裹尺寸",
                  is_required=True, sort=1,
                  options=_options((("small", "60 公分"), ("medium", "90 公分"), ("large", "120 公分")), 1090)),
            Topic(id=2, key="speed", type=TopicType.SINGLE, title="配送溫層",
                  is_required=True, sort=2,
                  options=_options((("normal", "常溫"), ("chilled", "低溫")), 1100)),
            Topic(id=3, key="store", type=TopicType.SINGLE, title="寄件門市",
                  is_required=True, sort=3,
                  options=_options((("qingchuan", "7-ELEVEN 晴川門市"), ("zhongxing", "7-ELEVEN 中興門市")), 1110)),
        ],
    )


def _restaurant_form() -> Form:
    return _form(
        form_id=107, service_id="service-restaurant", name="餐廳訂位",
        action=ServiceAction.RESERVATION, action_label="送出訂位需求",
        data_use="人數與時段只提供給所選餐廳確認座位",
        topics=[
            Topic(id=1, key="people", type=TopicType.SHORT_TEXT, title="用餐人數",
                  is_required=True, sort=1, is_number_only=True, min_value=1, max_value=12),
            Topic(id=2, key="date", type=TopicType.DATE, title="用餐日期",
                  is_required=True, sort=2,
                  start_date_offset_days=_VISIT_DATE_OFFSET[0], end_date_offset_days=_VISIT_DATE_OFFSET[1]),
            Topic(id=3, key="slot", type=TopicType.SINGLE, title="用餐時段",
                  is_required=True, sort=3,
                  options=_options((("lunch", "午餐 12:00"), ("dinner", "晚餐 18:30"), ("late", "晚餐 20:00")), 1120)),
        ],
    )


def _delivery_form() -> Form:
    return _form(
        form_id=108, service_id="service-delivery", name="美食外送",
        action=ServiceAction.ORDER, action_label="建立外送訂單",
        data_use="餐點、送達位置與時間只用於完成本次外送",
        topics=[
            Topic(id=1, key="meal", type=TopicType.SINGLE, title="餐點組合",
                  is_required=True, sort=1,
                  options=_options((("light", "輕食組合"), ("warm", "熱食組合"), ("family", "多人分享組合")), 1130)),
            Topic(id=2, key="address", type=TopicType.SHORT_TEXT, title="送達位置",
                  is_required=True, sort=2, hint="展示資料可填「晴川社區管理室」"),
            Topic(id=3, key="slot", type=TopicType.SINGLE, title="送達時間",
                  is_required=True, sort=3,
                  options=_options((("asap", "盡快送達"), ("noon", "12:00–12:30"), ("evening", "18:00–18:30")), 1140)),
        ],
    )


def _shopping_form() -> Form:
    return _form(
        form_id=109, service_id="service-shopping", name="商城購物",
        action=ServiceAction.ORDER, action_label="建立商城訂單",
        data_use="商品與付款偏好只用於本次試算及建立訂單",
        topics=[
            Topic(id=1, key="bundle", type=TopicType.SINGLE, title="補貨組合",
                  is_required=True, sort=1,
                  options=_options((("restock", "日用品補貨組 NT$ 699"), ("coffee", "CITY CAFE 咖啡券組 NT$ 240"),
                                    ("snacks", "零食分享組 NT$ 399")), 1150)),
            Topic(id=2, key="coupon", type=TopicType.SINGLE, title="優惠券",
                  is_required=True, sort=2,
                  options=_options((("apply", "套用目前最佳優惠券"), ("skip", "這次不使用優惠券")), 1160)),
            Topic(id=3, key="points", type=TopicType.SINGLE, title="OPENPOINT 折抵",
                  is_required=True, sort=3,
                  options=_options((("50", "使用 50 點折抵 NT$ 50"), ("0", "保留點數，本次不折抵")), 1170)),
            Topic(id=4, key="delivery", type=TopicType.SINGLE, title="取貨方式",
                  is_required=True, sort=4,
                  options=_options((("store", "7-ELEVEN 門市取貨"), ("home", "宅配到府")), 1180)),
            Topic(id=5, key="payment", type=TopicType.SINGLE, title="支付方式",
                  is_required=True, sort=5,
                  options=_options((("icash-pay", "icash Pay（本次加碼）"), ("card", "信用卡")), 1190)),
        ],
    )


_BUILDERS = {
    "service-washer": _washer_form,
    "service-aircon": _aircon_form,
    "service-cleaning": _cleaning_form,
    "service-housework": _housework_form,
    "service-repair": _repair_form,
    "service-shipping": _shipping_form,
    "service-restaurant": _restaurant_form,
    "service-delivery": _delivery_form,
    "service-shopping": _shopping_form,
}


def list_services() -> list[ServiceInfo]:
    return list(SERVICES)


def get_service(service_id: str) -> ServiceInfo | None:
    return next((s for s in SERVICES if s.id == service_id), None)


def get_service_form(service_id: str) -> Form | None:
    builder = _BUILDERS.get(service_id)
    return builder() if builder else None
