# Vue 第一條垂直切片

- 類型：task（AFK）
- 狀態：完成
- 完成日期：2026-07-25

## Question

如何建立能承接兩條 P0 主線的 Vue、狀態與測試骨架，而不把前端耦合到尚未取得的廠商 API？

## Resolution

採 Vue Router＋Pinia＋fixture state，另以 `lifeServicesClient` 固定同源 `/api/v1` 契約。所有寫入先確認；瀏覽器不保存廠商密鑰，也不自行宣告授權角色。

驗證結果：5 個測試檔、15 項測試、typecheck、production build 全數通過。

