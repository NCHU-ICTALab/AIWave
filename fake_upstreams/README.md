# Fake upstream servers

這些是可獨立啟動的 HTTP 上游系統，不是 Vue fixture，也不內嵌在 Platform API。瀏覽器只
呼叫 AIWave Platform API；平台依後端環境變數選擇 ProviderConnector。

## 現行 Partner fake upstream（M3/M4）

唯一現行契約是 [contracts/vendor-openapi.yaml](../contracts/vendor-openapi.yaml)，內容為
OpenAPI 3.0.3、Partner API v2。檔名為了相容既有工具暫時保留；舊版 Vendor 契約已移至
[contracts/legacy/](../contracts/legacy/)。

Partner fake 的固定 seed version 是 `partner-demo-v5`（M4，依產品負責人 2026-07-30 提供的
`廠商and表單.md` 正式名單），資料使用台灣中文情境並涵蓋六大生活場景的多個 Provider
（seed 定義在 [partner_seed.py](partner_seed.py)）：

| 場景 | Provider | Demo API key |
| --- | --- | --- |
| 住(修繕) | 王子水電 `vendor-prince-electric` | `aiwave-partner` |
| 住(清潔/家事) | DUSKIN 樂清 `vendor-duskin` | `aiwave-partner-duskin` |
| 食(訂位) | 21PLUS `vendor-21plus` | `aiwave-partner-21plus` |
| 行(洗車預約) | 速邁樂加油站 Smile `vendor-smile` | `aiwave-partner-smile` |
| 行(宅配) | 黑貓宅急便 `vendor-blackcat` | `aiwave-partner-blackcat` |
| 醫(處方箋領藥) | 康是美 `vendor-cosmed` | `aiwave-partner-cosmed` |
| 預(i 預購/EC) | 7-ELEVEN 線上購物中心 `vendor-711-shop` | `aiwave-partner-711shop` |
| 樂(訂房) | 統一渡假村 Uni Resort `vendor-uni-resort` | `aiwave-partner-resort` |

品牌名稱皆有公開依據(統一集團官方名單);價格、評分、時段與案件皆為競賽生成的展示
資料。時段以 `PARTNER_SEED_BASE_DATE`(預設 2026-07-30)為基準生成未來 7 天;建單會
消耗 slot 容量,取消/婉拒會釋放。它提供：

- catalog、availability、bookings、snapshot 與選配 webhook subscription。
- Bearer API key、Provider 綁定與細粒度 scopes。
- API key 與 webhook signing secret 的雜湊保存。
- 寫入端點的 payload-bound `Idempotency-Key`；相同 key 換內容會被拒絕。
- 固定 seed、reset、seed version、延遲、503、timeout／504、malformed response。
- `after_commit=true` 的狀態未知故障，可驗證安全重試與查詢復原。

### 啟動與查詢

```bash
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export VENDOR_FAKE_PORT="8020"
export PARTNER_FAKE_API_KEY="aiwave-partner"
uv run python -m fake_upstreams.partner_app
```

```bash
curl --fail --silent --show-error http://127.0.0.1:8020/healthz

curl --fail --silent --show-error \
  -H "Authorization: Bearer aiwave-partner" \
  http://127.0.0.1:8020/partner/v1/catalog

curl --fail --silent --show-error \
  -H "Authorization: Bearer aiwave-partner" \
  http://127.0.0.1:8020/partner/v1/availability
```

互動文件位於 `http://127.0.0.1:8020/__fake__/docs`。控制面一律要求
`X-Fake-Control-Key`：

```bash
curl --fail --silent --show-error \
  -H "X-Fake-Control-Key: local-demo-key" \
  http://127.0.0.1:8020/__fake__/state

curl --fail --silent --show-error \
  -X POST \
  -H "X-Fake-Control-Key: local-demo-key" \
  http://127.0.0.1:8020/__fake__/reset
```

### 故障注入

下一次建立 booking 在上游完成寫入後回傳 504，模擬呼叫端不知道是否成功：

```bash
curl --fail --silent --show-error \
  -X PUT \
  -H "X-Fake-Control-Key: local-demo-key" \
  -H "Content-Type: application/json" \
  --data '{
    "method": "POST",
    "path": "/partner/v1/bookings",
    "status": 504,
    "detail": "已寫入，但呼叫端未收到成功回應",
    "delay_ms": 0,
    "after_commit": true
  }' \
  http://127.0.0.1:8020/__fake__/faults/next
```

`body` 可指定任意 malformed success body；`delay_ms` 可模擬慢速與 client timeout。fault 只被
第一個方法及路徑完全相符的 request 消耗。

## Platform API 使用 Partner fake

```bash
export PROVIDER_MODE="standard"
export PARTNER_MODE="fake"
export PARTNER_FAKE_URL="http://127.0.0.1:8020"
export PARTNER_API_KEY="aiwave-partner"
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export DEMO_RESET_ENABLED="true"
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

`POST /api/v1/platform/demo/reset` 使用 `Bearer aiwave-admin` 時，會協調重置平台資料與
Partner fake，重新同步平台目錄投影並驗證 seed version。一般會員只能重置自己的隔離
DemoWorkspace。

M4 起平台對每個場景 Provider 各建一個 Standard connector(對同一 Partner API 端點使用
各廠商的 key;對應表可用 `PARTNER_PROVIDER_KEYS="vendor-a:key-a,vendor-b:key-b"` 覆蓋)。
平台啟動時會把各 Provider 的 catalog/availability 同步進本地目錄投影
(`CATALOG_SYNC_ON_STARTUP`,預設開);之後可隨時 `POST /api/v1/platform/catalog/sync`
(operator 同步全部、partner 只同步自己),`GET /api/v1/platform/catalog/health` 檢查
各 Provider 的 seed version 與同步時間。

## 切換正式 Partner API

Fake／Real 只由後端環境變數切換，Vue 不能選模式：

```bash
export PROVIDER_MODE="standard"
export PARTNER_MODE="real"
export PARTNER_REAL_URL="https://partner-api.example.com"
export PARTNER_API_KEY="由合作方安全提供的 API key"
export PARTNER_TIMEOUT_SECONDS="2.0"
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

正式端點必須實作同一份 OpenAPI。連線、契約或寫入失敗會明確回報，平台不會改成前端假
成功。`PROVIDER_MODE` 另可選 `adapter` 或 `workbench`，但三種模式都實作相同的
`ProviderConnector` 邊界。

## Legacy Vendor fake（相容舊流程）

既有 LifeTask／報價流程尚使用舊 Vendor HTTP API。為避免與 Partner fake 搶 port，手動測試
固定使用 8021：

```bash
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export VENDOR_FAKE_PORT="8021"
uv run python -m fake_upstreams.vendor_app
```

Platform API 同時設定：

```bash
export VENDOR_MODE="fake"
export VENDOR_FAKE_URL="http://127.0.0.1:8021"
```

這是明確標示的 compatibility path，不是現行 Partner OpenAPI 的證據，也不能用來宣稱 M4
正式服務閉環已完成。

## Retail fake upstream

既有商品／門市庫存 server 預設使用 8010：

```bash
export FAKE_CONTROL_KEY="local-retail-key"
uv run python -m fake_upstreams.app
```
