# P0 競賽展示工作地圖

> 狀態：執行中  
> 最後更新：2026-07-25  
> 規格基線：[競賽 Demo 垂直切片](../specs/07-demo-vertical-slice.md)

## Destination

完成一套可在五分鐘內穩定走完個人與社區兩條主線的 Vue Web：九項服務皆有下一步、跨角色狀態可回流、統一 API 接入價值可見，並通過 P0 測試、RWD 與 WCAG 2.2 AA 驗收。

## Notes

- ~~本地 repository 尚無初始 commit~~ → 2026-07-26 已建立 git 歷史（`4f167a1` 起），
  進度以 commit 為準，本目錄僅保留工作票的驗收條件。
- 使用者已授權在離開期間持續推進；本地工作票同時承載決策與實作，覆寫 wayfinder 預設的「只規劃、不執行」。
- 不需產品選擇的工作直接做；命名、真實合作宣稱、外部帳號／憑證與會改變主線的取捨集中到 [決策佇列](decision-queue.md)。
- 每次修改先更新工作票，再採測試先行；完成後記錄驗證結果與遺留風險。
- 介面不標示 Demo；文件必須明確區分官方服務來源、合作廠商與自建種子資料。

## Decisions so far

- [Web-first 與 LINE 延伸](../adr/0014-line-deep-link-first-liff-optional.md) — P0 不依賴 LIFF；LINE 以深層連結回到同一套 RWD Web。
- [四工作區共用平台](../adr/0006-single-web-platform-four-workspaces.md) — 個人、社區、廠商、平台營運共用核心實體與 API。
- [統一服務接入三模式](../adr/0007-three-vendor-onboarding-modes.md) — 標準接入、Adapter、工作台接入都必須可展示。
- [前端與無障礙基線](../adr/0013-vue-responsive-accessible-line-ready-frontend.md) — Vue 3、RWD、WCAG 2.2 AA 從共用元件開始落實。
- [Vue 第一條垂直切片](tickets/000-foundation.md) — 六路由、九項目錄、個人下單、社區報價回流與 API client 已建立。
- [九項服務題組與報價規則](tickets/001-service-forms-and-pricing.md) — 九項服務共用官方題型 schema、條件驗證、確定性報價與四類提交 seam。

## Frontier

> ⚠️ 2026-07-26：[08 產品體驗](../specs/08-product-experience.md) 指出目前動線是
> 「為 demo 而做」，使用者無法自行上手。**下方順序在該文件的三項分岔決定前暫緩**，
> 屆時需重新排序（首次使用旅程、零狀態、身分入口會插隊到前面）。

| 順序 | 工作票 | 狀態 | 阻擋 |
| --- | --- | --- | --- |
| 1 | [真 AI 諮詢閉環](tickets/007-real-ai-inquiry-loop.md) | **完成** | — |
| 2 | [九項服務題組與報價規則](tickets/001-service-forms-and-pricing.md) | 完成 | — |
| 3 | [訂單事件、異常與客服閉環](tickets/002-order-events-and-support.md) | 待辦 | 真 AI 諮詢閉環 |
| 4 | [社區與廠商 Hero 深化](tickets/003-community-vendor-hero.md) | 待辦 | 真 AI 諮詢閉環 |
| 5 | [三種廠商接入與測試主控台](tickets/004-connector-console.md) | 待辦 | 社區與廠商 Hero 深化 |
| 6 | [種子資料、離線與錯誤狀態](tickets/005-resilience-and-seed.md) | 待辦 | 前五項 |
| 7 | [RWD、鍵盤與 WCAG 驗收](tickets/006-quality-gate.md) | 待辦 | 種子資料、離線與錯誤狀態 |

## Not yet specified

- P0 完成後，依剩餘工時決定家庭共享、正式團購、超商庫存與情境模板的實作次序。
- 真實後端接上後，fixture repository 如何切換到 `/api/v1` 而不改畫面狀態模型。
- 正式 LINE Login／LIFF、OPENPOINT OIDC 與外部支付的申請及安全流程。

## Out of scope

- 正式付款、正式廠商 API、真實庫存與正式合作關係不屬於本輪 P0；競賽版只使用一致、可重算且有來源說明的種子資料。
- 語音、旅遊、考試週、ibon 文件處理與小賣家寄件保留產品範圍，但不阻塞兩條展示主線。
