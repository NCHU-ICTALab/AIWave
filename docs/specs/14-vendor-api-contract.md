# 14・Vendor OpenAPI、獨立 Fake Server 與 Client Adapter

> 狀態：已實作並通過契約、生命週期與故障測試
> 更新日期：2026-07-28
> 決策依據：[ADR-0021](../adr/0021-vendor-api-contract-and-fake-server.md)

## 1. 目的

建立一條可被正式廠商 API 取代的 integration seam，證明 AIWave 不是只在前端播放 mock data。Fake server、未來真實 API、平台後端、MCP 與測試必須共用同一份 OpenAPI 3.0 契約。

## 2. 邏輯架構

```text
Vue / AI UI
    │ 只呼叫 /api/v1
    ▼
AIWave FastAPI ── VendorService ── VendorClient
                                      ├─ MockVendorClient ── HTTP ── Fake Vendor Server
                                      └─ RealVendorClient ── HTTP ── Future Vendor API

MCP Server ── 共用 VendorService，不重寫媒合與訂單規則
```

`VENDOR_MODE` 只由平台後端組裝依賴時讀取：

- `fake`：使用 `MockVendorClient` 連到獨立 fake server。
- `real`：使用 `RealVendorClient` 連到正式 API base URL。

前端 bundle 不包含切換開關、控制金鑰或廠商憑證。

## 3. OpenAPI 3.0 範圍

規格檔建議位置：`contracts/vendor-openapi.yaml`。

### Data plane

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/v1/vendors` | 依服務、地區、時段查詢廠商 |
| GET | `/v1/vendors/{vendorId}` | 廠商公開資料與能力 |
| GET | `/v1/vendors/{vendorId}/locations` | 台灣格式服務據點及服務範圍 |
| GET | `/v1/offerings` | 查詢服務方案、價格規則與限制 |
| GET | `/v1/availability` | 查詢指定方案及區域可用時段 |
| POST | `/v1/inquiries` | 建立留資需求並取得上游編號 |
| GET | `/v1/inquiries/{inquiryId}` | 查詢需求及聯繫狀態 |
| POST | `/v1/inquiries/{inquiryId}/quotes` | 廠商建立報價 |
| GET | `/v1/inquiries/{inquiryId}/quotes` | 取得可比較報價 |
| POST | `/v1/orders` | 接受方案後建立履約訂單 |
| GET | `/v1/orders/{orderId}` | 取得狀態與履約摘要 |
| POST | `/v1/orders/{orderId}/events` | 回報接單、排程、到場、完成或異常 |

### Fake control plane

控制面只能存在於 fake server，且所有端點要求 `X-Fake-Control-Key`：

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/__fake__/state` | 查看 seed、請求計數與待觸發故障 |
| PUT | `/__fake__/faults/next` | 對 method＋path 注入一次 delay/status/body |
| POST | `/__fake__/reset` | 回到固定 seed，清空案件、故障與計數 |

沒有設定非空控制金鑰時，控制面必須停用或拒絕，不可使用公開預設值。

## 4. 核心 Schema

### Vendor

- `id`, `name`, `legal_name`
- `brand_source`, `source_url`, `source_checked_at`
- `service_codes[]`
- `rating`, `review_count`
- `contact_channels[]`
- `status`

### VendorLocation

- `id`, `vendor_id`, `name`
- `postal_code`, `county`, `district`, `address_line`
- `latitude`, `longitude`
- `service_districts[]`
- `business_hours[]`

### Offering

- `id`, `vendor_id`, `service_code`, `name`, `description`
- `pricing_model`, `base_price`, `currency`
- `duration_minutes`, `constraints[]`
- `point_eligible`, `status`

### Inquiry / Quote / VendorOrder

- 以平台 `external_reference` 維持冪等與追蹤。
- 聯絡資料另以授權狀態表示；LLM 與媒合排序預設不取得明文。
- 金額使用整數最小貨幣單位或明確 decimal schema，不使用浮點近似。
- 狀態使用版本化 enum，未知新值須被安全保存並標記 unsupported，不能直接 500。
- 每個寫入回應包含 `id`, `version`, `created_at`／`updated_at`, `trace_id`。

### Error

所有非成功回應使用一致 envelope：

```json
{
  "code": "VENDOR_TEMPORARILY_UNAVAILABLE",
  "message": "廠商服務暫時無法使用",
  "retryable": true,
  "traceId": "trace-...",
  "details": {}
}
```

## 5. `VendorClient` 介面

介面只暴露 domain 所需能力，不把 HTTP response 或 fake control plane 洩漏到業務層。最低方法：

- `search_vendors(criteria)`
- `list_offerings(criteria)`
- `get_availability(offering_id, window, location)`
- `create_inquiry(command, idempotency_key)`
- `get_inquiry(inquiry_id)`
- `list_quotes(inquiry_id)`
- `create_order(command, idempotency_key)`
- `get_order(order_id)`

`MockVendorClient` 和 `RealVendorClient` 都是 HTTP adapter；差異只能是 base URL、認證與少量正式 API 映射。真實 adapter 不可匯入 fake seed。上游 contract 驗證、缺欄位、型別錯誤及未知 enum 要轉成 domain error，交由平台降級處理。

## 6. Seed 計畫

使用 Faker `zh_TW` 並以固定 random seed 產生可重現資料：

| 資料 | 第一版目標 |
| --- | --- |
| 品牌／廠商 | 8–12 |
| 服務據點 | 約 30 |
| 案件、報價及狀態事件 | 約 120 |

名稱不能由 Faker 任意拼湊。品牌名稱使用人工維護、附公開來源的 allowlist；Faker 只產生台灣姓名、電話、時間、門牌、案件內容與非品牌欄位。優先情境包含太子物業、王子水電及其他可公開驗證的統一體系／合作服務。

每個 seed scenario 至少涵蓋：

- 正常可媒合與可下單。
- 無符合時段或超出服務區。
- 多家報價有價格／評分／時間取捨。
- 報價過期、廠商拒單與履約異常。
- 慢速成功、503、逾時、格式錯誤及重試成功。

## 7. README 必備內容

- 安裝依賴與啟動 fake server。
- 啟動平台並設定 `VENDOR_MODE=fake`。
- control key、reset 與故障注入範例。
- seed 數量及資料來源說明。
- 切換 `VENDOR_MODE=real` 所需 base URL、認證及 migration checklist。
- 明確聲明競賽 fake API 不代表品牌正式 API 或合作串接。

## 8. 安全與韌性

- 控制面不部署至 production，或由 network policy 完全隔離。
- 廠商金鑰只存在 server-side secret store，不進前端或 LLM context。
- 所有寫入使用 idempotency key，避免重試重複建單。
- timeout、retry、circuit breaker、fallback 與 degraded reason 有一致政策。
- malformed 2xx response 也視為 connector failure，不可穿透為平台 500。
- PII 在媒合階段保持最小化；只有履約必要且已同意時交付指定廠商。

## 9. 驗收條件

- [x] OpenAPI lint／schema 驗證通過，fake server 回應符合契約。
- [x] fake server 可不啟動平台而獨立執行及查詢。
- [x] 固定 seed 每次 reset 產生相同識別碼與統計。
- [x] `VENDOR_MODE=fake|real` 只改環境變數，不改 Vue 或 domain service。
- [x] 正常、慢速成功、503、逾時、格式錯誤及恢復皆有 integration test。
- [x] reset 後故障、資料變更及請求計數歸零。
- [x] Web、Agent、MCP 對同一案件讀到相同狀態。
- [x] README 能讓未參與開發者依步驟啟動並理解如何換接正式 API。
