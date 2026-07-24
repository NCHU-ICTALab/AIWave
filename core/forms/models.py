"""題組（表單）定義的資料模型。

對齊官方 `pms_form / pms_form_group / pms_form_topic / pms_topic_option` schema
（見 docs/specs/02-data-model.md、03-form-engine.md）。題型代碼全數沿用官方
`pms_form_topic.type`，不自訂。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TopicType(str, Enum):
    """官方 pms_form_topic.type 題型代碼。"""

    SHORT_TEXT = "1"        # 簡答
    LONG_TEXT = "2"         # 詳答
    SINGLE = "3"            # 單選
    MULTI = "4"             # 複選（可含雙層子選項）
    REGION = "5"            # 地區選單
    PHOTO = "6"             # 上傳照片
    NOTE = "7"              # 備註說明
    CONTACT = "8"           # 聯絡資料（含地址）
    DATE = "9"              # 日期
    CONTACT_NO_ADDR = "10"  # 聯絡資料（不含地址）


TEXT_TYPES = {TopicType.SHORT_TEXT, TopicType.LONG_TEXT, TopicType.NOTE}
CHOICE_TYPES = {TopicType.SINGLE, TopicType.MULTI}
CONTACT_TYPES = {TopicType.CONTACT, TopicType.CONTACT_NO_ADDR}


class Option(BaseModel):
    """題目選項（對齊 pms_topic_option）。"""

    id: int
    option_name: str
    unit_price: int | None = None
    unit: str | None = None
    is_quantity: bool = False          # 是否可填數量（如冷氣台數、團購份數）
    min_quantity: int | None = None
    max_quantity: int | None = None
    is_quoted_separately: bool = False
    parent_id: int | None = None       # 雙層子選項：子選項指向父選項 id
    # 呈現用穩定字串值（供 Web 表單 <option value>）。官方 schema 以 id 為主，
    # 此欄不對應官方欄位；未給時序列化會退回 str(id)。
    value: str | None = None


class SkipLogic(BaseModel):
    """跳題規則，放官方 pms_form_topic.feature.skipLogic（不改 DDL，見 ADR-0002）。

    語意：僅當 `topic_id` 的答案含 `answer_in` 中任一 option id 時，本題才出現。
    """

    topic_id: int
    answer_in: list[int]


class Topic(BaseModel):
    """表單題目（對齊 pms_form_topic）。"""

    id: int
    type: TopicType
    title: str
    is_required: bool = False
    sort: int = 0
    is_number_only: bool = False       # 簡答限數字
    min_media: int | None = None       # 照片題最少張數
    max_media: int | None = None       # 照片題最多張數
    start_date_offset_days: int | None = None  # 日期題可選起日相對今日偏移
    end_date_offset_days: int | None = None    # 日期題可選迄日相對今日偏移
    min_value: int | None = None       # 數字簡答下限
    max_value: int | None = None       # 數字簡答上限
    hint: str | None = None            # 題目說明（對齊 pms_form_topic.remark）
    options: list[Option] = Field(default_factory=list)
    skip_logic: SkipLogic | None = None
    # 呈現用穩定字串鍵（供 Web 表單 field id 與 AI prompt）。非官方欄位。
    key: str | None = None

    @property
    def field_key(self) -> str:
        return self.key or f"topic-{self.id}"

    def option(self, option_id: int) -> Option | None:
        return next((o for o in self.options if o.id == option_id), None)


class Group(BaseModel):
    """表單題組（對齊 pms_form_group）。"""

    id: int
    name: str = ""
    sort: int = 0
    topics: list[Topic] = Field(default_factory=list)


class ServiceAction(str, Enum):
    """送出後的落地流程；對應官方 order_type 語意（諮詢單／訂單／訂位／寄件）。"""

    INQUIRY = "inquiry"          # 諮詢單 → pms_form_feedback
    ORDER = "order"              # 商品/外送訂單 → order_type 05/07
    RESERVATION = "reservation"  # 訂位/預約 → order_type 02/03
    SHIPMENT = "shipment"        # 寄件 → 物流服務


class Form(BaseModel):
    """表單主檔（對齊 pms_form）。"""

    id: int
    name: str
    groups: list[Group] = Field(default_factory=list)
    # 服務層 metadata：把「這張表單屬於哪個服務、送出後做什麼」綁在定義上，
    # 讓 Web／AI／MCP 三個通路讀同一份來源。非官方欄位。
    service_id: str | None = None
    action: ServiceAction = ServiceAction.INQUIRY
    action_label: str = "送出需求"
    data_use: str = ""

    def ordered_topics(self) -> list[Topic]:
        """依題組 sort、再依題目 sort 攤平成引導順序。"""
        out: list[Topic] = []
        for g in sorted(self.groups, key=lambda x: x.sort):
            out.extend(sorted(g.topics, key=lambda x: x.sort))
        return out

    def topic(self, topic_id: int) -> Topic | None:
        return next((t for t in self.ordered_topics() if t.id == topic_id), None)


class Selection(BaseModel):
    """單選/複選的一筆選擇（含數量）。"""

    option_id: int
    quantity: int | None = None


class Region(BaseModel):
    """地區選單答案。"""

    county_code: str
    district_code: str
    county_name: str | None = None
    district_name: str | None = None
