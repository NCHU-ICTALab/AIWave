# Fake upstream servers

這裡的服務是可獨立執行的 HTTP 系統，不是 Vue 內的假陣列。前端只呼叫 AIWave
平台 API；平台再透過 adapter 呼叫這些 upstream。

## Vendor fake server

契約：[contracts/vendor-openapi.yaml](../contracts/vendor-openapi.yaml)

固定情境 `vendor_demo_seed_v1` 包含：

- 10 個人工白名單品牌，包含太子物業、王子水電、DUSKIN 樂清、黑貓宅急便、
  7-ELEVEN 交貨便／賣貨便、foodomo、EZTABLE、7-ELEVEN 線上購物中心與康是美。
- 30 個 Faker `zh_TW` 台灣格式服務據點。
- 120 筆諮詢單與 120 筆報價。
- Faker 只生成地址、聯絡人、電話、時間與案件內容；不生成品牌名稱。

### 手動啟動

請各開一個終端機；命令不會由測試自動常駐。

```powershell
# 終端機 1：獨立廠商 API，預設 http://127.0.0.1:8020
$env:VENDOR_FAKE_CONTROL_KEY = "請換成自己的本機測試金鑰"
uv run python -m fake_upstreams.vendor_app

# 終端機 2：AIWave 平台 API，預設 http://127.0.0.1:8000
$env:VENDOR_MODE = "fake"
$env:VENDOR_FAKE_URL = "http://127.0.0.1:8020"
uv run main.py

# 終端機 3：Vue
Set-Location web\app
npm run dev
```

可開啟 `http://127.0.0.1:8020/__fake__/docs` 查看 fake server 的互動文件，
平台 API 文件則在 `http://127.0.0.1:8000/docs`。

### 驗證與重置

```powershell
Invoke-RestMethod http://127.0.0.1:8020/healthz
Invoke-RestMethod http://127.0.0.1:8020/v1/vendors?serviceId=service-repair

$controlHeaders = @{ "X-Fake-Control-Key" = "請換成自己的本機測試金鑰" }
Invoke-RestMethod http://127.0.0.1:8020/__fake__/state -Headers $controlHeaders
Invoke-RestMethod http://127.0.0.1:8020/__fake__/reset -Method Post -Headers $controlHeaders
```

控制面可用 `PUT /__fake__/faults/next` 注入單次慢速、503、逾時或格式錯誤；
下一個相符 request 消耗後即恢復。控制端點一律要求 `X-Fake-Control-Key`。

```powershell
$fault = @{
  method = "POST"; path = "/v1/inquiries"; status = 503
  detail = "廠商接案服務維護中"; delay_ms = 0
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8020/__fake__/faults/next `
  -Method Put -Headers $controlHeaders -ContentType "application/json" -Body $fault
```

接著在 AI 頁確認 Hero 任務：第一次會顯示部分失敗與「安全重試未完成案件」；
同一個故障只觸發一次，再按安全重試不會重複建立已成功的案件。

### 切換正式 API

正式模式不改 Vue、不改 Agent、不改 MCP 工具，也不改媒合規則，只換後端環境變數：

```powershell
$env:VENDOR_MODE = "real"
$env:VENDOR_REAL_URL = "https://partner-api.example.com"
$env:VENDOR_API_TOKEN = "由合作方安全提供的 token"
$env:VENDOR_TIMEOUT_SECONDS = "2.0"
uv run main.py
```

`RealVendorClient` 會送出 Bearer token；正式 API 必須實作同一份 OpenAPI 契約。
讀取失敗時媒合會明確標示 `offline_fallback`；建立諮詢單、報價、訂單等寫入失敗時
絕不假裝成功。

## Retail fake upstream

既有商品／門市庫存 server 預設使用 8010：

```powershell
$env:FAKE_CONTROL_KEY = "請換成自己的本機測試金鑰"
uv run python -m fake_upstreams.app
```
