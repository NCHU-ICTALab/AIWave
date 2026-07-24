"""三份 seed 題組定義（對齊 docs/specs/03-form-engine.md 的 F1/F2/F3）。

供引擎測試與後續 MCP `get_service_form` 種子使用。option / topic id 與官方一致採整數。
"""

from __future__ import annotations

from .models import Form, Group, Option, SkipLogic, Topic, TopicType

# 選項 id 常數（方便跳題與測試引用）
OPT_MST_UNCLOG = 101   # 馬桶-不通
OPT_MST_NOFLUSH = 102  # 馬桶-無法沖水
OPT_LAMP_OFF = 111     # 燈具-不亮
OPT_LAMP_BLINK = 112   # 燈具-閃爍
OPT_SOCKET = 120       # 插座
OPT_AC_WASH = 130      # 冷氣清洗（可填台數）
OPT_AC_SPLIT = 141     # 分離式
OPT_AC_WINDOW = 142    # 窗型


def repair_form() -> Form:
    """F1・水電修繕諮詢。"""
    return Form(
        id=901,
        name="水電修繕諮詢",
        groups=[
            Group(
                id=1,
                name="修繕需求",
                sort=1,
                topics=[
                    Topic(
                        id=1,
                        type=TopicType.MULTI,
                        title="需要修繕的項目",
                        is_required=True,
                        sort=1,
                        options=[
                            Option(id=100, option_name="馬桶"),  # 父
                            Option(id=OPT_MST_UNCLOG, option_name="不通", parent_id=100),
                            Option(id=OPT_MST_NOFLUSH, option_name="無法沖水", parent_id=100),
                            Option(id=110, option_name="燈具"),  # 父
                            Option(id=OPT_LAMP_OFF, option_name="不亮", parent_id=110),
                            Option(id=OPT_LAMP_BLINK, option_name="閃爍", parent_id=110),
                            Option(id=OPT_SOCKET, option_name="插座"),
                            Option(
                                id=OPT_AC_WASH,
                                option_name="冷氣清洗",
                                is_quantity=True,
                                min_quantity=1,
                                max_quantity=5,
                            ),
                        ],
                    ),
                    Topic(
                        id=2,
                        type=TopicType.SINGLE,
                        title="冷氣型式",
                        is_required=True,
                        sort=2,
                        options=[
                            Option(id=OPT_AC_SPLIT, option_name="分離式"),
                            Option(id=OPT_AC_WINDOW, option_name="窗型"),
                        ],
                        skip_logic=SkipLogic(topic_id=1, answer_in=[OPT_AC_WASH]),
                    ),
                    Topic(
                        id=3,
                        type=TopicType.PHOTO,
                        title="現場照片",
                        is_required=False,
                        sort=3,
                        max_media=3,
                    ),
                ],
            ),
            Group(
                id=2,
                name="時間與聯絡",
                sort=2,
                topics=[
                    Topic(
                        id=4,
                        type=TopicType.REGION,
                        title="服務地址（縣市/行政區）",
                        is_required=True,
                        sort=1,
                    ),
                    Topic(
                        id=5,
                        type=TopicType.DATE,
                        title="方便的日期",
                        is_required=True,
                        sort=2,
                        start_date_offset_days=1,
                        end_date_offset_days=14,
                    ),
                    Topic(
                        id=6,
                        type=TopicType.SINGLE,
                        title="方便時段",
                        is_required=True,
                        sort=3,
                        options=[
                            Option(id=161, option_name="上午"),
                            Option(id=162, option_name="下午"),
                            Option(id=163, option_name="晚上"),
                        ],
                    ),
                    Topic(
                        id=7,
                        type=TopicType.CONTACT,
                        title="聯絡資料",
                        is_required=True,
                        sort=4,
                    ),
                ],
            ),
        ],
    )


def group_buy_form(item_name: str = "團購品項", max_qty: int = 10) -> Form:
    """F2・團購跟團。"""
    return Form(
        id=902,
        name="團購跟團",
        groups=[
            Group(
                id=1,
                sort=1,
                topics=[
                    Topic(
                        id=1,
                        type=TopicType.SINGLE,
                        title="品項",
                        is_required=True,
                        sort=1,
                        options=[
                            Option(
                                id=201,
                                option_name=item_name,
                                is_quantity=True,
                                min_quantity=1,
                                max_quantity=max_qty,
                            )
                        ],
                    ),
                    Topic(
                        id=2,
                        type=TopicType.SINGLE,
                        title="取貨方式",
                        is_required=True,
                        sort=2,
                        options=[
                            Option(id=211, option_name="社區管理室"),
                            Option(id=212, option_name="7-ELEVEN 門市"),
                        ],
                    ),
                    Topic(
                        id=3,
                        type=TopicType.CONTACT_NO_ADDR,
                        title="聯絡資料",
                        is_required=True,
                        sort=3,
                    ),
                ],
            )
        ],
    )


def facility_form() -> Form:
    """F3・公設預約（demo 現場載入的新服務）。"""
    return Form(
        id=903,
        name="公設預約",
        groups=[
            Group(
                id=1,
                sort=1,
                topics=[
                    Topic(
                        id=1,
                        type=TopicType.SINGLE,
                        title="公設",
                        is_required=True,
                        sort=1,
                        options=[
                            Option(id=301, option_name="交誼廳"),
                            Option(id=302, option_name="健身房"),
                            Option(id=303, option_name="KTV 室"),
                        ],
                    ),
                    Topic(
                        id=2,
                        type=TopicType.DATE,
                        title="使用日期",
                        is_required=True,
                        sort=2,
                        start_date_offset_days=0,
                        end_date_offset_days=7,
                    ),
                    Topic(
                        id=3,
                        type=TopicType.SINGLE,
                        title="使用時段",
                        is_required=True,
                        sort=3,
                        options=[
                            Option(id=311, option_name="上午"),
                            Option(id=312, option_name="下午"),
                            Option(id=313, option_name="晚上"),
                        ],
                    ),
                    Topic(
                        id=4,
                        type=TopicType.SHORT_TEXT,
                        title="使用人數",
                        is_required=True,
                        sort=4,
                        is_number_only=True,
                    ),
                ],
            )
        ],
    )
