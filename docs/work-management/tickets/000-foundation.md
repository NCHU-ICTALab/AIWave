# Vue 第一條垂直切片

- 類型：task（AFK）
- 狀態：完成
- 完成日期：2026-07-25

## Question

如何建立能承接兩條 P0 主線的 Vue、狀態與測試骨架，而不把前端耦合到尚未取得的廠商 API？

## Resolution

採 Vue Router＋Pinia＋fixture state，另以 API client 固定同源 `/api/v1` 契約。所有寫入先確認；瀏覽器不保存廠商密鑰，也不自行宣告授權角色。

> 2026-07-26 後續：當初的 `lifeServicesClient` 從未被畫面使用（只有自己的測試引用），已移除。
> 實際生效的 client 是 `serviceCatalogClient`、`aiInquiryClient` 與 `insightsClient`；
> fixture state 也已改由後端提供定義與金額。

驗證結果：5 個測試檔、15 項測試、typecheck、production build 全數通過。

