# 廠商能力以 OpenAPI 契約、獨立 fake server 與可替換 Client 接入

> 狀態：Accepted（2026-07-28）

單純在前端放 mock 資料，無法證明廠商 API 可被平台、Agent 或 MCP 真正調用，也無法展示延遲、失敗、重試及未來換接正式 API。決定把模擬廠商做成可獨立啟動的 HTTP server，並讓正式平台只依賴 `VendorClient` 介面。

必要交付如下：

1. OpenAPI 3.0 規格，定義廠商、服務地點、方案、可用時段、諮詢、報價、訂單及狀態事件。
2. 可獨立執行且實作該規格的 fake vendor server，具控制金鑰、reset、固定 seed 及一次性故障注入。
3. Faker `zh_TW` 產生的可重現中文種子資料；第一版以 8–12 個統一體系或公開合作品牌、約 30 個服務據點、約 120 筆案件／報價為目標，再依展示效果決定是否擴增。
4. 平台端 `VendorClient` 介面，提供 `MockVendorClient` 與 `RealVendorClient`；由**平台後端**讀取 `VENDOR_MODE` 切換，瀏覽器永遠只呼叫平台 `/api/v1`。
5. README 說明啟動、reset、故障情境、`VENDOR_MODE` 及正式 API 切換方式。

種子品牌與情境應使用公開可驗證的統一體系或合作服務，不使用競業品牌，也不虛構奇怪的公司名稱。已確認的修繕／物業情境優先使用太子物業與王子水電；文件及介面不需要額外宣稱正式 API 或本專案合作關係。

## Consequences

- fake server 只模擬上游廠商，不重做平台自己的媒合、權限、訂單狀態機或稽核。
- OpenAPI 是 Client、fake server、測試與未來正式接入的單一契約來源。
- Demo 必須能展示正常、慢速成功、錯誤、格式錯誤、重試、降級與 reset。
- `RealVendorClient` 不得匯入 fake seed 或依賴 fake server 內部資料。
- HTTP/API、Agent 與 MCP 共用同一 domain service，不各自複製業務邏輯。
