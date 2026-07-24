# MCP 交付地圖

> 原則：MCP 是 transport adapter，不承載另一套業務邏輯。Web API、平台 Agent、LINE 與 MCP 都呼叫 `core/services/` 的 application service。

| MCP server | 核心工具 | 核心實作狀態 | MCP adapter 狀態 |
| --- | --- | --- | --- |
| `life-services` | `list_services`、`search_services`、`get_service_form`、`calc_discount`、`submit_inquiry`、`match_vendors` | 題組、驗證、SQLite inquiry 與 `LifeServicesService.submit_inquiry` 已完成第一條真閉環 | 待包裝 |
| `order` | `create_order`、`list_my_orders`、`get_order_status`、`create_quote`、`update_order_status`、`create_support_ticket` | 前端種子狀態機；後端事件模型待辦 | 待包裝 |
| `community` | `create_joint_service`、`get_joint_service_summary`、`match_vendors`、`assign_joint_service_vendor`、團購工具 | 前端跨角色流程存在；後端持久化待辦 | 待包裝 |
| `retail` | 門市能力、商品庫存、優惠、點數、候補 | 確定性前端優惠試算存在；資料 repository 待辦 | 待包裝 |
| `personal-intelligence` | `get_behavior_summary`、`get_recommendations`、`record_recommendation_feedback`、提醒與儀表板 | 前端種子推薦與回饋存在；後端特徵／推薦服務待辦 | 待包裝 |
| `backoffice` | 廠商 connector、契約測試、方案管理、推播、服務缺口 | 前端工作區外殼存在；connector service 待辦 | 待包裝 |

## 不做成 MCP 的內部能力

- LINE／Web 通路 adapter 與 webhook。
- 意圖路由、對話 session、題組逐題編排、短期記憶。
- 授權、稽核、通知排程、重試與 idempotency guard。
- 資料庫 repository 與廠商密鑰管理。

這些能力由平台內部 orchestration 控制，MCP tool 只能在既有權限與確認規則下呼叫 application service。

## 下一個 MCP 實作切點

1. 以 `LifeServicesService` 包裝 `get_service_form` 與 `submit_inquiry`。
2. MCP tool schema 沿用官方題組及統一 inquiry contract。
3. 用同一份 contract test 同時驗證 HTTP adapter 與 MCP adapter。
4. 再依序完成 `order` 與 `community`，支撐兩條五分鐘主線。
