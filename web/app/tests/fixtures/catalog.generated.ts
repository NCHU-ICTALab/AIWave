/**
 * 由後端產生的服務目錄 fixture——**請勿手改**。
 *
 * 重新產生：`uv run python tools/dump_catalog_fixture.py`
 * 來源：core/forms/service_catalog.py + core/forms/dto.py（展示基準日 2026-07-25）
 */
import type { BehaviorSummary, Recommendation, TrailEvent } from '@/api/insightsClient'
import type { CatalogService } from '@/api/serviceCatalogClient'
import type { ServiceFormDefinition } from '@/domain/serviceIntake'

export const catalogServices: CatalogService[] = [
  {
    "id": "service-washer",
    "name": "洗衣機清洗",
    "category": "居家維護",
    "summary": "到府拆洗與基礎檢測",
    "partner": "專業清潔夥伴",
    "glyph": "洗"
  },
  {
    "id": "service-aircon",
    "name": "冷氣清洗",
    "category": "居家維護",
    "summary": "壁掛式冷氣深層清潔",
    "partner": "專業清潔夥伴",
    "glyph": "冷"
  },
  {
    "id": "service-cleaning",
    "name": "專業清潔",
    "category": "居家維護",
    "summary": "居家空間重點清潔",
    "partner": "社區合作夥伴",
    "glyph": "潔"
  },
  {
    "id": "service-housework",
    "name": "計時家事",
    "category": "生活支援",
    "summary": "兩小時計時家事協助",
    "partner": "生活服務夥伴",
    "glyph": "家"
  },
  {
    "id": "service-repair",
    "name": "水電修繕",
    "category": "生活支援",
    "summary": "初步判斷並安排到府",
    "partner": "安心修繕",
    "glyph": "修"
  },
  {
    "id": "service-shipping",
    "name": "寄件服務",
    "category": "生活支援",
    "summary": "黑貓宅急便到店寄件",
    "partner": "黑貓宅急便",
    "glyph": "寄"
  },
  {
    "id": "service-restaurant",
    "name": "餐廳訂位",
    "category": "餐飲購物",
    "summary": "依人數與時段媒合餐廳",
    "partner": "統一集團餐飲",
    "glyph": "訂"
  },
  {
    "id": "service-delivery",
    "name": "美食外送",
    "category": "餐飲購物",
    "summary": "附近餐點與情境推薦",
    "partner": "外送合作夥伴",
    "glyph": "送"
  },
  {
    "id": "service-shopping",
    "name": "商城購物",
    "category": "餐飲購物",
    "summary": "日用品補貨並套用優惠",
    "partner": "iOPEN Mall",
    "glyph": "購"
  }
]

export const catalogForms: Record<string, ServiceFormDefinition> = {
  "service-washer": {
    "serviceId": "service-washer",
    "formId": 101,
    "action": "inquiry",
    "actionLabel": "建立清洗諮詢",
    "dataUse": "設備類型、數量與時段只用於估價及安排到府服務",
    "fields": [
      {
        "id": "machineType",
        "topicId": 1,
        "label": "洗衣機類型",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "top",
            "label": "直立式",
            "optionId": 1010
          },
          {
            "value": "drum",
            "label": "滾筒式",
            "optionId": 1011
          }
        ]
      },
      {
        "id": "quantity",
        "topicId": 2,
        "label": "清洗台數",
        "type": 1,
        "required": true,
        "numberOnly": true,
        "min": 1,
        "max": 5
      },
      {
        "id": "date",
        "topicId": 93,
        "label": "希望日期",
        "type": 9,
        "required": true,
        "hint": "可預約展示基準日後 14 天內的時段",
        "minDate": "2026-07-26",
        "maxDate": "2026-08-08"
      },
      {
        "id": "slot",
        "topicId": 94,
        "label": "希望時段",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "morning",
            "label": "上午 09:00–12:00",
            "optionId": 9100
          },
          {
            "value": "afternoon",
            "label": "下午 13:00–17:00",
            "optionId": 9101
          },
          {
            "value": "evening",
            "label": "晚上 18:00–21:00",
            "optionId": 9102
          }
        ]
      }
    ]
  },
  "service-aircon": {
    "serviceId": "service-aircon",
    "formId": 102,
    "action": "inquiry",
    "actionLabel": "建立冷氣清洗諮詢",
    "dataUse": "機型、數量與時段只用於估價及媒合清潔夥伴",
    "fields": [
      {
        "id": "airconType",
        "topicId": 1,
        "label": "冷氣類型",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "split",
            "label": "分離式",
            "optionId": 1020
          },
          {
            "value": "window",
            "label": "窗型",
            "optionId": 1021
          }
        ]
      },
      {
        "id": "quantity",
        "topicId": 2,
        "label": "清洗台數",
        "type": 1,
        "required": true,
        "numberOnly": true,
        "min": 1,
        "max": 5
      },
      {
        "id": "date",
        "topicId": 93,
        "label": "希望日期",
        "type": 9,
        "required": true,
        "hint": "可預約展示基準日後 14 天內的時段",
        "minDate": "2026-07-26",
        "maxDate": "2026-08-08"
      },
      {
        "id": "slot",
        "topicId": 94,
        "label": "希望時段",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "morning",
            "label": "上午 09:00–12:00",
            "optionId": 9100
          },
          {
            "value": "afternoon",
            "label": "下午 13:00–17:00",
            "optionId": 9101
          },
          {
            "value": "evening",
            "label": "晚上 18:00–21:00",
            "optionId": 9102
          }
        ]
      }
    ]
  },
  "service-cleaning": {
    "serviceId": "service-cleaning",
    "formId": 103,
    "action": "inquiry",
    "actionLabel": "建立居家清潔諮詢",
    "dataUse": "空間與清潔重點只用於估算工時及媒合服務人員",
    "fields": [
      {
        "id": "homeSize",
        "topicId": 1,
        "label": "居家坪數",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "small",
            "label": "20 坪以下",
            "optionId": 1030
          },
          {
            "value": "medium",
            "label": "21–35 坪",
            "optionId": 1031
          },
          {
            "value": "large",
            "label": "36 坪以上",
            "optionId": 1032
          }
        ]
      },
      {
        "id": "focusArea",
        "topicId": 2,
        "label": "主要清潔區域",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "kitchen",
            "label": "廚房",
            "optionId": 1040
          },
          {
            "value": "bathroom",
            "label": "浴室",
            "optionId": 1041
          },
          {
            "value": "whole",
            "label": "全屋重點",
            "optionId": 1042
          }
        ]
      },
      {
        "id": "date",
        "topicId": 93,
        "label": "希望日期",
        "type": 9,
        "required": true,
        "hint": "可預約展示基準日後 14 天內的時段",
        "minDate": "2026-07-26",
        "maxDate": "2026-08-08"
      },
      {
        "id": "slot",
        "topicId": 94,
        "label": "希望時段",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "morning",
            "label": "上午 09:00–12:00",
            "optionId": 9100
          },
          {
            "value": "afternoon",
            "label": "下午 13:00–17:00",
            "optionId": 9101
          },
          {
            "value": "evening",
            "label": "晚上 18:00–21:00",
            "optionId": 9102
          }
        ]
      }
    ]
  },
  "service-housework": {
    "serviceId": "service-housework",
    "formId": 104,
    "action": "reservation",
    "actionLabel": "預約計時家事",
    "dataUse": "工作內容與時段只用於安排合適的服務人員",
    "fields": [
      {
        "id": "hours",
        "topicId": 1,
        "label": "服務時數",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "2",
            "label": "2 小時",
            "optionId": 1050
          },
          {
            "value": "3",
            "label": "3 小時",
            "optionId": 1051
          },
          {
            "value": "4",
            "label": "4 小時",
            "optionId": 1052
          }
        ]
      },
      {
        "id": "task",
        "topicId": 2,
        "label": "主要工作",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "clean",
            "label": "日常清潔",
            "optionId": 1060
          },
          {
            "value": "organize",
            "label": "收納整理",
            "optionId": 1061
          },
          {
            "value": "laundry",
            "label": "洗曬衣物",
            "optionId": 1062
          }
        ]
      },
      {
        "id": "date",
        "topicId": 93,
        "label": "希望日期",
        "type": 9,
        "required": true,
        "hint": "可預約展示基準日後 14 天內的時段",
        "minDate": "2026-07-26",
        "maxDate": "2026-08-08"
      },
      {
        "id": "slot",
        "topicId": 94,
        "label": "希望時段",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "morning",
            "label": "上午 09:00–12:00",
            "optionId": 9100
          },
          {
            "value": "afternoon",
            "label": "下午 13:00–17:00",
            "optionId": 9101
          },
          {
            "value": "evening",
            "label": "晚上 18:00–21:00",
            "optionId": 9102
          }
        ]
      }
    ]
  },
  "service-repair": {
    "serviceId": "service-repair",
    "formId": 105,
    "action": "inquiry",
    "actionLabel": "建立修繕諮詢",
    "dataUse": "問題類型與說明只提供給媒合後的修繕夥伴判斷",
    "fields": [
      {
        "id": "repairType",
        "topicId": 1,
        "label": "修繕項目",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "plumbing",
            "label": "水管／馬桶",
            "optionId": 1070
          },
          {
            "value": "lighting",
            "label": "燈具／開關",
            "optionId": 1071
          },
          {
            "value": "outlet",
            "label": "插座",
            "optionId": 1072
          },
          {
            "value": "other",
            "label": "其他",
            "optionId": 1073
          }
        ]
      },
      {
        "id": "detail",
        "topicId": 2,
        "label": "問題說明",
        "type": 2,
        "required": true,
        "hint": "請簡述現象，不要填寫門牌或其他敏感資料",
        "visibleWhen": {
          "fieldId": "repairType",
          "equals": "other"
        }
      },
      {
        "id": "urgency",
        "topicId": 3,
        "label": "緊急程度",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "normal",
            "label": "一般，可安排時段",
            "optionId": 1080
          },
          {
            "value": "soon",
            "label": "希望 48 小時內",
            "optionId": 1081
          }
        ]
      }
    ]
  },
  "service-shipping": {
    "serviceId": "service-shipping",
    "formId": 106,
    "action": "shipment",
    "actionLabel": "建立寄件單",
    "dataUse": "包裹規格與寄件門市只用於產生黑貓寄件流程",
    "fields": [
      {
        "id": "parcelSize",
        "topicId": 1,
        "label": "包裹尺寸",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "small",
            "label": "60 公分",
            "optionId": 1090
          },
          {
            "value": "medium",
            "label": "90 公分",
            "optionId": 1091
          },
          {
            "value": "large",
            "label": "120 公分",
            "optionId": 1092
          }
        ]
      },
      {
        "id": "speed",
        "topicId": 2,
        "label": "配送溫層",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "normal",
            "label": "常溫",
            "optionId": 1100
          },
          {
            "value": "chilled",
            "label": "低溫",
            "optionId": 1101
          }
        ]
      },
      {
        "id": "store",
        "topicId": 3,
        "label": "寄件門市",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "qingchuan",
            "label": "7-ELEVEN 晴川門市",
            "optionId": 1110
          },
          {
            "value": "zhongxing",
            "label": "7-ELEVEN 中興門市",
            "optionId": 1111
          }
        ]
      }
    ]
  },
  "service-restaurant": {
    "serviceId": "service-restaurant",
    "formId": 107,
    "action": "reservation",
    "actionLabel": "送出訂位需求",
    "dataUse": "人數與時段只提供給所選餐廳確認座位",
    "fields": [
      {
        "id": "people",
        "topicId": 1,
        "label": "用餐人數",
        "type": 1,
        "required": true,
        "numberOnly": true,
        "min": 1,
        "max": 12
      },
      {
        "id": "date",
        "topicId": 2,
        "label": "用餐日期",
        "type": 9,
        "required": true,
        "minDate": "2026-07-26",
        "maxDate": "2026-08-08"
      },
      {
        "id": "slot",
        "topicId": 3,
        "label": "用餐時段",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "lunch",
            "label": "午餐 12:00",
            "optionId": 1120
          },
          {
            "value": "dinner",
            "label": "晚餐 18:30",
            "optionId": 1121
          },
          {
            "value": "late",
            "label": "晚餐 20:00",
            "optionId": 1122
          }
        ]
      }
    ]
  },
  "service-delivery": {
    "serviceId": "service-delivery",
    "formId": 108,
    "action": "order",
    "actionLabel": "建立外送訂單",
    "dataUse": "餐點、送達位置與時間只用於完成本次外送",
    "fields": [
      {
        "id": "meal",
        "topicId": 1,
        "label": "餐點組合",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "light",
            "label": "輕食組合",
            "optionId": 1130
          },
          {
            "value": "warm",
            "label": "熱食組合",
            "optionId": 1131
          },
          {
            "value": "family",
            "label": "多人分享組合",
            "optionId": 1132
          }
        ]
      },
      {
        "id": "address",
        "topicId": 2,
        "label": "送達位置",
        "type": 1,
        "required": true,
        "hint": "展示資料可填「晴川社區管理室」"
      },
      {
        "id": "slot",
        "topicId": 3,
        "label": "送達時間",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "asap",
            "label": "盡快送達",
            "optionId": 1140
          },
          {
            "value": "noon",
            "label": "12:00–12:30",
            "optionId": 1141
          },
          {
            "value": "evening",
            "label": "18:00–18:30",
            "optionId": 1142
          }
        ]
      }
    ]
  },
  "service-shopping": {
    "serviceId": "service-shopping",
    "formId": 109,
    "action": "order",
    "actionLabel": "建立商城訂單",
    "dataUse": "商品與付款偏好只用於本次試算及建立訂單",
    "fields": [
      {
        "id": "bundle",
        "topicId": 1,
        "label": "補貨組合",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "restock",
            "label": "日用品補貨組 NT$ 699",
            "optionId": 1150
          },
          {
            "value": "coffee",
            "label": "CITY CAFE 咖啡券組 NT$ 240",
            "optionId": 1151
          },
          {
            "value": "snacks",
            "label": "零食分享組 NT$ 399",
            "optionId": 1152
          }
        ]
      },
      {
        "id": "coupon",
        "topicId": 2,
        "label": "優惠券",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "apply",
            "label": "套用目前最佳優惠券",
            "optionId": 1160
          },
          {
            "value": "skip",
            "label": "這次不使用優惠券",
            "optionId": 1161
          }
        ]
      },
      {
        "id": "points",
        "topicId": 3,
        "label": "OPENPOINT 折抵",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "50",
            "label": "使用 50 點折抵 NT$ 50",
            "optionId": 1170
          },
          {
            "value": "0",
            "label": "保留點數，本次不折抵",
            "optionId": 1171
          }
        ]
      },
      {
        "id": "delivery",
        "topicId": 4,
        "label": "取貨方式",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "store",
            "label": "7-ELEVEN 門市取貨",
            "optionId": 1180
          },
          {
            "value": "home",
            "label": "宅配到府",
            "optionId": 1181
          }
        ]
      },
      {
        "id": "payment",
        "topicId": 5,
        "label": "支付方式",
        "type": 3,
        "required": true,
        "options": [
          {
            "value": "icash-pay",
            "label": "icash Pay（本次加碼）",
            "optionId": 1190
          },
          {
            "value": "card",
            "label": "信用卡",
            "optionId": 1191
          }
        ]
      }
    ]
  }
} as unknown as Record<string, ServiceFormDefinition>

export const insightSummary: BehaviorSummary = {
  "accountId": "019a52d3-7f6b-7da3-b48d-9c9e2522d616",
  "totalOrders": 10,
  "completedOrders": 7,
  "openOrders": 2,
  "cancelledOrders": 1,
  "distinctServices": 3,
  "totalSpend": 2218,
  "earnedPoints": 0,
  "firstActivity": "2026-06-02",
  "lastActivity": "2026-06-16",
  "services": [
    {
      "serviceId": "service-shopping",
      "serviceName": "商城購物",
      "count": 7,
      "lastUsedOn": "2026-06-16",
      "daysSinceLast": 39,
      "totalAmount": 1970
    },
    {
      "serviceId": "service-repair",
      "serviceName": "水電修繕",
      "count": 2,
      "lastUsedOn": "2026-06-05",
      "daysSinceLast": 50,
      "totalAmount": 0
    },
    {
      "serviceId": "service-delivery",
      "serviceName": "美食外送",
      "count": 1,
      "lastUsedOn": "2026-06-04",
      "daysSinceLast": 51,
      "totalAmount": 248
    }
  ],
  "source": "official_order_record"
} as unknown as BehaviorSummary

export const insightRecommendations: Recommendation[] = [
  {
    "id": "resume-1878",
    "kind": "resume_open",
    "title": "接續處理水電修繕",
    "serviceId": "service-repair",
    "serviceName": "水電修繕",
    "reasonCodes": [
      "open_order",
      "status_11"
    ],
    "reasonText": "你有一筆水電修繕尚未完成（訂單 26052200000612）。",
    "evidence": [
      {
        "recordId": 1878,
        "orderNo": "26052200000612",
        "serviceName": "水電修繕",
        "occurredOn": "2026-06-02",
        "detail": "官方訂單狀態 11"
      }
    ],
    "score": 100,
    "computedBy": "rules"
  },
  {
    "id": "revisit-service-shopping",
    "kind": "revisit",
    "title": "該安排商城購物了",
    "serviceId": "service-shopping",
    "serviceName": "商城購物",
    "reasonCodes": [
      "days_since_last",
      "threshold_30d"
    ],
    "reasonText": "上次商城購物是 2026-06-16，距今 39 天。",
    "evidence": [
      {
        "recordId": 2003,
        "orderNo": "PIC20260616000001",
        "serviceName": "商城購物",
        "occurredOn": "2026-06-16",
        "detail": "共使用 7 次"
      }
    ],
    "score": 71,
    "computedBy": "rules"
  }
] as unknown as Recommendation[]

export const insightTrail: TrailEvent[] = [
  {
    "occurredOn": "2026-06-02",
    "serviceName": "水電修繕",
    "serviceId": "service-repair",
    "orderNo": "26052200000612",
    "recordId": 1878,
    "status": "11",
    "amount": 0,
    "itemName": "",
    "outcome": "open"
  },
  {
    "occurredOn": "2026-06-04",
    "serviceName": "美食外送",
    "serviceId": "service-delivery",
    "orderNo": "1026-006d",
    "recordId": 1918,
    "status": "80",
    "amount": 248,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-05",
    "serviceName": "水電修繕",
    "serviceId": "service-repair",
    "orderNo": "26060500000212",
    "recordId": 1929,
    "status": "12",
    "amount": 300,
    "itemName": "",
    "outcome": "open"
  },
  {
    "occurredOn": "2026-06-15",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260615000001",
    "recordId": 1977,
    "status": "80",
    "amount": 100,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-15",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260615000002",
    "recordId": 1980,
    "status": "80",
    "amount": 100,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-15",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260612000016",
    "recordId": 1999,
    "status": "80",
    "amount": 590,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-15",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260613000015",
    "recordId": 1998,
    "status": "80",
    "amount": 590,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-15",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260615000015",
    "recordId": 1993,
    "status": "80",
    "amount": 590,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-15",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260615000017",
    "recordId": 1995,
    "status": "80",
    "amount": 0,
    "itemName": "",
    "outcome": "completed"
  },
  {
    "occurredOn": "2026-06-16",
    "serviceName": "商城購物",
    "serviceId": "service-shopping",
    "orderNo": "PIC20260616000001",
    "recordId": 2003,
    "status": "99",
    "amount": 250,
    "itemName": "",
    "outcome": "cancelled"
  }
] as unknown as TrailEvent[]

export const insightAccounts = [
  {
    "accountId": "019eee3f-841e-7048-ae67-0955b144f4f8",
    "orderCount": 16,
    "serviceCount": 4,
    "openCount": 0,
    "topService": "餐廳訂位",
    "topServiceCount": 5,
    "isDefault": false
  },
  {
    "accountId": "019a52d3-7f6b-7da3-b48d-9c9e2522d616",
    "orderCount": 10,
    "serviceCount": 3,
    "openCount": 2,
    "topService": "商城購物",
    "topServiceCount": 7,
    "isDefault": true
  },
  {
    "accountId": "019db86c-201d-700a-ba04-525d90da4b0b",
    "orderCount": 3,
    "serviceCount": 2,
    "openCount": 2,
    "topService": "餐廳訂位",
    "topServiceCount": 2,
    "isDefault": false
  },
  {
    "accountId": "019e6c8c-a061-7197-be0f-b7d341dbafdd",
    "orderCount": 31,
    "serviceCount": 1,
    "openCount": 0,
    "topService": "商城購物",
    "topServiceCount": 31,
    "isDefault": false
  },
  {
    "accountId": "019d7569-19cc-7727-aa60-82644ce67ad7",
    "orderCount": 23,
    "serviceCount": 1,
    "openCount": 0,
    "topService": "商城購物",
    "topServiceCount": 23,
    "isDefault": false
  },
  {
    "accountId": "019c0464-2d01-73f0-9f9b-d1392fdb941a",
    "orderCount": 8,
    "serviceCount": 1,
    "openCount": 8,
    "topService": "水電修繕",
    "topServiceCount": 8,
    "isDefault": false
  },
  {
    "accountId": "019a52d3-7f6b-7f5f-8201-98588d5a5b84",
    "orderCount": 5,
    "serviceCount": 1,
    "openCount": 0,
    "topService": "餐廳訂位",
    "topServiceCount": 5,
    "isDefault": false
  },
  {
    "accountId": "019c08f2-62e1-76be-a7ac-44b8a2d1d290",
    "orderCount": 1,
    "serviceCount": 1,
    "openCount": 0,
    "topService": "美食外送",
    "topServiceCount": 1,
    "isDefault": false
  },
  {
    "accountId": "019cb30b-6a86-739a-832b-38225a2b2fdf",
    "orderCount": 1,
    "serviceCount": 1,
    "openCount": 0,
    "topService": "水電修繕",
    "topServiceCount": 1,
    "isDefault": false
  },
  {
    "accountId": "019ef24a-424e-776e-854c-a1cf7b2b3ed9",
    "orderCount": 1,
    "serviceCount": 1,
    "openCount": 0,
    "topService": "洗衣機清洗",
    "topServiceCount": 1,
    "isDefault": false
  }
]
