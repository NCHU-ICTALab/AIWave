# 04・MCP Tool 與統一生活服務 API 規格

> ⚠️ **「按域拆 6 server」已由 [ADR-0017](../adr/0017-llm-plans-rules-execute.md) 取代**。
> 新的作法是**單一工具註冊表、雙重曝露**：規劃器（in-process）與 Lumine one（MCP 協定）
> 呼叫的是同一份工具定義，不必為 demo 與為交付各做一套。下方的工具清單仍是有效的
> **能力藍圖**，但「拆成幾個 server」屬於封裝細節，競賽版以單一 server 承載已實作能力。
>
> MCP Server 為自建、符合標準協定，可同時掛本系統 Agent 與官方 Lumine one 平台的 Agent（命題繳交要求）。
> 兩層關係：**MCP 工具**是對外能力介面（Agent 呼叫）；**統一生活服務 API**是其下的唯一業務資料出入口（模擬層）。

## A. MCP 邊界原則

**MCP＝任何 Agent（含 Lumine one）都能重用的「能力呼叫」。** 回傳結構化 JSON＋人類可讀 `summary`；identity 用 `resident_id`（內部換 `member_hash`，不經手個資原文）；金額 TWD 整數。

### 留在內部、不做 MCP（我們 Agent 的腦與基礎設施）
| 內部元件 | 為何不是 MCP |
| --- | --- |
| 通路 Adapter（LINE／Web） | 通路基礎設施，非能力 |
| 意圖辨識／多意圖拆解 | Agent 的推理本身 |
| 題組引擎「逐題對話」迴圈 | Agent 編排；但「取表單定義」與「送諮詢單」是工具 |
| 生活任務排序與「確認即執行」卡片組裝 | Agent 編排；被排序的可執行動作各自呼叫 MCP 工具 |
| 對話記憶／Session | Agent 基礎設施 |
| 事件推播服務 | 由資料狀態變更觸發，非 Agent 呼叫 |
| 範圍（scope）存取控制 | 跨切關注點，於 API/資料層強制（[ADR-0003](../adr/0003-scope-as-core-attribute.md)） |

### LLM 支援型工具
`generate_reply_draft`、`generate_push_draft`、`design_form`、`ask_uni_qa` 內部呼叫 LLM（經 `LlmClient` 介面，[ADR-0004](../adr/0004-local-first-aws-portable.md)）。仍是標準 MCP 工具。

## B. 六個 MCP Server

### Server 1・life-services-mcp（服務目錄與媒合）
| Tool | 參數 | 回傳 |
| --- | --- | --- |
| `search_services` | query, district? | 服務列表（id, name, vendor, form_id） |
| `list_services` | category?, integration_depth? | 可操作服務與接入深度狀態；不以固定數量作為契約 |
| `get_service_detail` | service_id | 服務詳情 |
| `get_service_form` | service_id | 完整表單定義（題組/題目/選項/跳題/地區限制） |
| `list_districts` | county? | 地區清單 |
| `match_vendors` | service_id, criteria? | 2-3 家廠商比較（報價/評分/時段）＋推薦一家（FR-S-04） |

### Server 2・order-mcp（諮詢單與訂單）
| Tool | 參數 | 回傳 |
| --- | --- | --- |
| `submit_inquiry` | form_id, resident_id, answers, address, preferred_time | feedback_no |
| `create_order` | service_id, order_type, resident_id, order_items, deposit? | order_no |
| `create_reservation` | resident_id, restaurant, party_size, time | order_no（02） |
| `get_order_status` | order_no | 狀態/明細/報價 |
| `list_my_orders` | resident_id, status?, type? | 歷史訂單 |
| `confirm_quote` | order_no | 確認結果 |
| `cancel_order` | order_no, reason | 取消結果 |
| `create_support_ticket` | resident_id, order_no?, issue | ticket_no（FR-S-05） |

### Server 3・community-mcp（社區／團購／公設／群組）
| Tool | 參數 | 回傳 |
| --- | --- | --- |
| `create_joint_service` | community_id, service_id, title, close_time | 聯合服務活動與表單草稿（FR-C-06） |
| `join_joint_service` | campaign_id, resident_id, answers, quantity, preferred_slots | request_id、feedback_no |
| `get_joint_service_summary` | campaign_id | 戶數、數量、時段分布、特殊需求、媒合狀態 |
| `assign_joint_service_vendor` | campaign_id, vendor_offering_id | 指派結果與每戶後續成單狀態 |
| `list_group_buys` | community_id, status? | 進行中活動＋截止＋跟團數 |
| `get_campaign` | campaign_id | 活動詳情＋跟團統計 |
| `join_group_buy` | campaign_id, resident_id, quantity | order_no（07，[ADR-0001](../adr/0001-groupbuy-per-household-orders.md)） |
| `parse_group_messages` | text | 由群組 +1/+2 解析出結構化訂單（FR-C-02，LLM） |
| `list_facilities` | community_id, date? | 公設與時段可用性 |
| `book_facility` | facility_id, resident_id, start, end, headcount | 預約單/衝突 |
| `list_my_groups` | resident_id | 所屬群組（[ADR-0003](../adr/0003-scope-as-core-attribute.md)） |
| `split_bill` | campaign_id or order_ids | 每人應付（FR-F-04） |

### Server 4・retail-mcp（超商生態）＊需零售種子層
| Tool | 參數 | 回傳 |
| --- | --- | --- |
| `ask_uni_qa` | question | 回答旗下商店/支付/優惠/ibon（FR-P-40，RAG+LLM） |
| `query_store_inventory` | product, near? | 哪些門市有貨（FR-P-41） |
| `list_store_capabilities` | store_id? / near? | 列印/寄件/ATM/咖啡/取貨（FR-P-42） |
| `find_alternate_store` | product or capability, near? | 鄰近可替代門市（FR-P-43） |
| `track_limited_item` | resident_id, item | 訂閱限量雷達（FR-P-44） |
| `join_waitlist` | resident_id, product, store? | 到貨候補（FR-P-45） |

### Server 5・personal-intelligence-mcp（個人智慧）
| Tool | 參數 | 回傳 |
| --- | --- | --- |
| `get_behavior_summary` | resident_id | 跨服務行為軌跡與可重算特徵摘要（FR-X-06） |
| `get_recommendations` | resident_id, context? | 候選項目、分數、reason_codes、evidence、AI 說明（FR-P-02） |
| `record_recommendation_feedback` | impression_id, action | clicked/accepted/not_interested/undo 回饋；更新可衰減偏好 |
| `get_personalization_settings` | resident_id | 同意狀態、不感興趣清單與硬性限制 |
| `update_personalization_settings` | resident_id, consent?, undo_preference_id?, clear_profile? | 更新同意、復原偏好或清除並重建特徵 |
| `get_consumption_dashboard` | resident_id, month? | 消費/點數/券/取貨聚合（FR-P-01） |
| `list_coupons` | resident_id, filter? | 可用/即將到期券（FR-P-13，帶 scope） |
| `get_point_balance` | resident_id | OPENPOINT 餘額與明細（FR-P-03） |
| `calc_discount` | resident_id, cart/plan | 最划算折抵方案（FR-P-14，真算） |
| `set_reminder` | resident_id, type, schedule, scope | 建提醒（FR-P-10/11，帶 scope） |
| `list_reminders` | resident_id | 提醒清單 |
| `set_preference` | resident_id, allergies/limits | 過敏/禁忌過濾（FR-P-20） |

### Server 6・backoffice-mcp（管理者／廠商／平台 AI）
| Tool | 參數 | 回傳 |
| --- | --- | --- |
| `list_pending_inquiries` | vendor_id | 待處理諮詢單 |
| `create_quote` | order_no, items[] | quote_no（觸發推播） |
| `update_order_status` | order_no, status, note? | 更新結果 |
| `generate_reply_draft` | feedback_no | 廠商回覆草稿 ⭐（LLM） |
| `create_group_buy` | community_id, title, item, unit_price, close_time, min_qty | campaign_id |
| `close_group_buy` | campaign_id | 採購單彙總 |
| `mark_arrived` | campaign_id | 批次到貨推播 |
| `generate_push_draft` | conditions（活動/天氣/節慶/對象） | 推播文案草稿 ⭐（LLM） |
| `send_push` | audience, content | 發送結果 |
| `get_analytics` | community_id, date_range? | 訂單量/金額/完成率 |
| `design_form` | need_description | AI 生成新表單題組＋累積服務缺口 ⭐（FR-S-03，LLM） |
| `generate_service_flow` | service_type | 填表→派單→付款→提醒→評價流程樣板（FR-V-08） |
| `plan_campaign` | goal | 一鍵產活動＋優惠＋文案＋表單（FR-V-07） |
| `handle_support_ticket` | ticket_no, action | 查狀態/轉接（FR-S-05） |
| `list_vendor_connectors` | mode?, status? | 標準/轉接/工作台接入器與健康度 |
| `test_vendor_connector` | connector_id, capability | 統一契約測試輸入、正規化結果與錯誤 |
| `upsert_vendor_offering` | vendor_id, service_id, price, slots, coverage | 服務方案預覽/寫入結果（需確認） |

### 競賽版展示覆蓋檢查
| 展示線 | 用到的工具 |
| --- | --- |
| Hero・跨服務生活任務 | `plan_life_task`→`get_service_form`→`match_vendors`＋`calc_discount`→預覽確認→`submit_inquiry`／`create_order`→`get_order_status` |
| 會員資訊總覽 | `get_behavior_summary`→`get_recommendations`＋`get_consumption_dashboard`＋`list_reminders`＋`list_my_orders` |
| 群組加碼 | `get_active_scope`→取得同意→`create_joint_service`→`get_joint_service_summary`→`match_vendors` |
| 平台接入證明 | `list_vendor_connectors`→`test_vendor_connector`→`upsert_vendor_offering` |
| 延伸情境 | `ask_uni_qa`／`query_store_inventory`／`find_alternate_store`／`list_my_groups`／`split_bill` |

### 工具開發順序（對齊 [SRS §6.1.1](06-system-requirements.md)）
1. **Phase 1**：服務、題組、媒合、點數、訂單與事件的 domain tools。
2. **Phase 2**：Planner 以 capability registry 產生跨服務 task plan，完成 Hero。
3. **Phase 3**：Vendor OpenAPI、fake server 與 Client seam，完成廠商狀態回流。
4. **Phase 4**：群組 scope、同意、聯合服務與通知工具。
5. **Phase 5**：依實際 Demo 需要擴增服務與 LINE／語音通路。

---

## C. 統一生活服務 API（模擬層，MCP 之下）

**唯一業務資料出入口**，MCP 工具與後台都只打這層。與 MCP 工具一對一鏡像；下表列核心族群，retail／personal-intelligence／點數券等新域的端點比照其 MCP 工具命名。

### 通則
- Base URL `/api/v1`，JSON in/out
- 認證 `X-Api-Key` ＋ `X-Role: resident|admin|vendor`（demo 假登入，正式接 OAuth）
- 識別：`resident_id`（內部）／`member_hash`（對官方表）；回應不含個資原文
- 錯誤 `{ "error": { "code", "message" } }`；分頁 `?page=&size=`

### 核心端點
| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/services`、`/services/{id}`、`/services/{id}/form` | 服務目錄與表單定義 |
| GET | `/counties`、`/districts?county=` | 地區代碼 |
| POST/GET | `/inquiries`、`/inquiries/{no}`、`/inquiries?vendor_id=` | 諮詢單提交/查詢/待辦 |
| POST/GET | `/orders`、`/orders/{no}`、`/residents/{id}/orders` | 訂單（01/02/07 共用） |
| POST | `/orders/{no}/quote`、`/confirm-quote`、`/cancel`；PATCH `/status` | 報價/確認/取消/狀態 |
| POST | `/reservations` | 訂位語法糖 → 02 訂單 |
| POST/GET | `/campaigns`、`/campaigns/{id}`、`/join`、`/close`、`/arrived` | 團購生命週期 |
| GET/POST/DELETE | `/facilities`、`/facility-bookings` | 公設預約（衝突回 409） |
| POST/GET | `/push/preview`、`/push`、`/push/history` | 管理者推播（AI 文案/發送/紀錄） |
| GET | `/residents/by-line/{id}`、`/analytics/summary` | 住戶綁定、後台聚合 |

### 事件 → 推播對照
| 事件 | 觸發點 | 對象與文案要素 |
| --- | --- | --- |
| 報價已出 | `POST /orders/{no}/quote` | 住戶：金額＋「回覆確認即可安排」 |
| 報價已確認 | `confirm-quote` | 廠商後台徽章＋住戶回執 |
| 完工 | `status → 80` | 住戶：完工＋評價邀請（＋家人安心通知） |
| 團購結單 | `campaigns/{id}/close` | 管理者：採購單摘要 |
| 團購到貨 | `campaigns/{id}/arrived` | 全體跟團住戶：取貨時間地點 |

> 訂單**事件推播**不走此 API——由狀態變更在服務內部觸發通知服務（見 [01 架構](01-system-architecture.md)）。
