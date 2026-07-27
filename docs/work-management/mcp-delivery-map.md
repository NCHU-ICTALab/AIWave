# MCP 交付地圖

> 原則：MCP 是 transport adapter，不承載另一套業務邏輯。Web API、平台 Agent、LINE 與 MCP 都呼叫 `core/services/` 的 application service。

> 2026-07-28 更新：六個名稱代表能力領域，不再各自啟動 server。依 ADR-0017，實際交付為
> 單一 `smart-living-butler` MCP Server，共用同一份 30-tool Registry。

| 能力領域 | 已交付核心工具 | 核心實作狀態 | MCP adapter 狀態 |
| --- | --- | --- | --- |
| `life-services` | `list_services`、`search_services`、`get_service_form`、`estimate_price`、`submit_inquiry`、`match_vendors` | 題組驗證、SQLite inquiry、語意相關性與廠商媒合完成 | **已交付** |
| `order` | `create_order`、`list_my_orders` | SQLite 訂單、規則計價與事件完成；客服與品牌履約回呼待辦 | **已交付（部分能力）** |
| `community` | 團購工具；聯合服務工具待辦 | 團購核心與持久化完成；聯合服務／派工待辦 | **團購已交付；聯合服務待包裝** |
| `retail` | `search_store_inventory`、`join_stock_waitlist`、`list_stock_watches` | 能力／庫存 seed connector、替代門市與 SQLite 候補完成 | **已交付** |
| `personal-intelligence` | `get_behavior_summary`、`get_recommendations`、`get_restock_plan`、`record_recommendation_feedback`、`create_restock_reminder`、`list_reminders` | 官方訂單證據、競賽帳本、回饋與 SQLite 提醒完成 | **已交付** |
| `backoffice` | 廠商 connector、契約測試、方案管理、推播、服務缺口 | 前端工作區外殼存在；connector service 待辦 | 待包裝 |

## 不做成 MCP 的內部能力

- LINE／Web 通路 adapter 與 webhook。
- 意圖路由、對話 session、題組逐題編排、短期記憶。
- 授權、稽核、通知排程、重試與 idempotency guard。
- 資料庫 repository 與廠商密鑰管理。

這些能力由平台內部 orchestration 控制，MCP tool 只能在既有權限與確認規則下呼叫 application service。

## 下一個 MCP 實作切點

1. 補 `get_order_status` 與品牌履約 webhook/idempotency。
2. 將 retail seed connector 換成正式門市能力與庫存 API Adapter。
3. 將提醒接到 EventBridge Scheduler／LINE 通知通路。
4. 完成客服工單與社區聯合服務 MCP tools。
