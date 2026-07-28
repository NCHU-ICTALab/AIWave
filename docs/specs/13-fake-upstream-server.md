# Fake upstream server 與韌性測試

## 不是什麼

Fake server 不取代平台後端，也不重新實作平台的諮詢、訂單、聯合服務或權限規則。這些能力必須繼續在正式 `core/` 模組與 `/api/v1` 執行，否則 Demo 通過不代表產品成立。

## 架構 seam

```text
Vue ── /api/v1 ──> 真實平台 FastAPI ── RetailConnector ─┬─ HttpRetailConnector ─> fake upstream／未來正式 API
                                                       └─ SeedRetailConnector（明示離線 fallback）
```

`RetailConnector` 的介面只暴露：

1. 由自然語言解析商品。
2. 取得該商品的門市能力與庫存快照。

排序、替代門市、候補資格與平台寫入仍由 `RetailService` 決定。

## Fake server 介面

資料面：

- `GET /v1/retail/products/resolve?q=...`
- `GET /v1/retail/inventory/{product_id}`

控制面（需 `X-Fake-Control-Key`）：

- `GET /__fake__/state`
- `PUT /__fake__/faults/next`：對指定資料端點注入一次 status／delay／response body；`status: 200` 可單獨模擬慢但成功的回應。
- `POST /__fake__/reset`：回到 `demo_seed_v1` 並清除故障。

## 不變條件

- 前端永遠只呼叫 `/api/v1`。
- 一次性故障只消耗一次；reset 後故障與計數歸零。
- fake 回應標示 `fake_upstream:demo_seed_v1`，fallback 標示 `competition_seed_offline_fallback`。
- 控制面不得在沒有控制金鑰時可用。
- 正式 connector 失敗時，平台回傳可用的離線結果與 degraded 原因，不把 500 直接丟給使用者。

## 本機啟動

先啟動 fake upstream：

```powershell
$env:FAKE_CONTROL_KEY='local-demo-control'
python -m fake_upstreams.app
```

再讓平台透過 HTTP adapter 連線：

```powershell
$env:RETAIL_UPSTREAM_URL='http://127.0.0.1:8010'
$env:UPSTREAM_TIMEOUT_SECONDS='2.0'
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

注入一次 503 後，下一次相同請求會自動恢復；平台在失敗那次回傳離線備援資料：

```powershell
$headers = @{ 'X-Fake-Control-Key' = 'local-demo-control' }
$body = @{ method='GET'; path='/v1/retail/inventory/limited-cup'; status=503; detail='品牌庫存維護中'; delay_ms=0 } | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri http://127.0.0.1:8010/__fake__/faults/next -Headers $headers -ContentType application/json -Body $body
```
