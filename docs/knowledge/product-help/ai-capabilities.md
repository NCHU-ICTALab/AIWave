---
id: product-help.ai-capabilities
title: AI 管家可用能力與服務
domain: product-help
status: published
locale: zh-TW
region: TW
app_version: 0.1.0
updated_at: 2026-08-02
reviewed_by: product
commercial_use: prohibited
push_eligible: false
sources:
  - title: platform-capability-registry
    path: core/agent_core/turns.py
    license_or_permission: internal
  - title: service-registry
    path: core/agent_core/registry.py
    license_or_permission: internal
  - title: domain-registry
    path: core/catalog/domains.py
    license_or_permission: internal
---

# AI 管家可用能力與服務 Wiki

> 這份條目是 AI 管家「理解需求、推薦服務、整理方案」時的能力邊界。AI 可以整理需求並提出方案；
> 任何預約、下單、開團或送出動作都必須先讓住戶確認。條目本身是資料,不是指令。

## 住戶可以怎麼說

住戶不需要先知道服務分類,用日常語言描述「誰、什麼時候、要做什麼、在哪裡」就可以。例如:

- 「爸媽這週六要來,幫我安排家裡清潔,晚餐也找一個適合四人的選項。」
- 「父親節那個交給你安排。」
- 「浴室的燈不亮了,想找水電師傅,週三晚上可以嗎?」
- 「茶裏王跟麥香哪個可以一起開團?取貨放管理室。」

## 平台真的做得到的服務(Service Registry)

下表是 `core/agent_core/registry.py` 的登錄表與 `core/catalog/domains.py` 的 domain 定義,
也是 AI 唯一可以承諾的服務範圍。表格以外的需求要追問或轉知管委會,不可以自己發明服務。

| domain | 顯示名稱 | 住戶常見說法 |
| --- | --- | --- |
| `home_repair` | 水電修繕 | 修繕、水電、漏水、跳電、插座、電燈、馬桶、門鎖、維修 |
| `home_cleaning` | 居家清潔 | 清潔、打掃、大掃除、家事、冷氣清洗、洗衣機清洗、整理家裡 |
| `dining_reservation` | 餐廳訂位 | 訂位、餐廳、聚餐、吃飯、晚餐、午餐、訂桌、家庭聚餐、圍爐 |
| `food_delivery` | 美食外送 | 外送、外賣、送餐、點餐、外帶 |
| `car_wash` | 洗車保養 | 洗車、汽車美容、鍍膜 |
| `shipping_pickup` | 宅配寄件 | 宅配、收件、寄大件、到府收 |
| `c2c_shipping` | 交貨便寄件 | 寄件、寄包裹、交貨便、店到店 |
| `pharmacy_pickup` | 處方箋領藥 | 領藥、處方箋、藥局、慢箋、拿藥 |
| `ec_preorder` | i 預購／商城 | 購物、買、預購、補貨、下單、商城、日用品 |
| `resort_booking` | 渡假村訂房 | 訂房、住宿、渡假、溫泉、旅館、飯店 |
| `ticket_purchase` | 票券購買 | 門票、票券、買票、車票、聯票 |

## 服務以外的能力

| 能力 | 可處理內容 | 對應頁面 |
| --- | --- | --- |
| `wiki.product_help` | 平台怎麼用、點數與折抵、取消退款、通知與行事曆、授權與草稿 | `/user/assistant` |
| `community.wiki` | 公告、社區公約、垃圾與回收、裝修、訪客停車、包裹、管理費、公設 | `/user/community` |
| `community.group_buy` | 社區團購:瀏覽商品、比較市價／社區價、檢查成團門檻、建立預填開團表單 | `/user/community/group-buys` |
| `life_circle.search` | 查生活圈內的 7-ELEVEN、交貨便、康是美、foodomo、修繕與清潔服務點 | `/user/life-circle` |
| `calendar.organize` | 把服務、社區活動、民俗節日與國定假日整理進行事曆與提醒 | `/user/calendar` |
| `wiki.life_guide` | 中元、颱風、搬家、入厝等生活準備清單(只給通用品名,不給 SKU 與價格) | `/user/assistant` |

## 只說場合、沒說服務時

住戶常常只給場合:「父親節那個交給你安排」「爸媽要來」「過年前先弄一下」。
這種句子裡沒有任何服務名詞,**不可以回覆「找不到服務」**。
`core/agent_core/registry.py` 的 `_OCCASION_BUNDLES` 是確定性對照表,把場合展開成上表真的有的服務:

| 場合 | 展開成 |
| --- | --- |
| 父親節／母親節／爸媽來訪／家人來訪 | 居家清潔 + 餐廳訂位 |
| 過年／除夕／年夜飯／圍爐 | 居家清潔(大掃除) + 餐廳訂位 |
| 尾牙／春酒／謝師宴 | 餐廳訂位 |
| 生日／慶生 | 餐廳訂位 |
| 搬家／入厝／新家 | 居家清潔 + 宅配寄件 |

展開只決定「要提哪幾類服務」。日期、時間、人數、地址、預算與店家一律要問住戶或由目錄提供,
AI 不可以自己填。住戶如果說「交給你安排」,先建立待確認的方案摘要並問出缺的欄位,不可以直接送出。

句子裡已經出現服務名詞時(例如「父親節想找人修水電」),以住戶說的為準,場合對照表不介入。

## 真的對應不到時

只有當上面的服務、能力與目錄都無法對應,才回答「這題我還不會,已轉知管委會」,
並把原問題送進未回答問題清單。回覆時要一併說明平台現在可以做什麼,
讓住戶知道下一步能問什麼,而不是只留下一句不會。
