# 社區小統・生活服務作業系統

2026 雲湧智生：臺灣生成式 AI 應用黑客松——統一資訊命題。

> 產品對外名稱是**社區小統**。程式碼、Bearer 憑證（`aiwave-*`）、帳號與 workspace id
> 裡的 `aiwave` **刻意不改名**——那些是識別碼與憑證，不是給人看的名字，改了會直接壞掉。

社區小統以個人會員為主體，讓手動 Web、未來 Agent、MCP 與合作方工作台共用同一套
Platform API、身分權限、交易狀態、點數、通知與行事曆。它不是第二個 OPENPOINT、純聊天
機器人或只有畫面的 mock demo。

目前已落地的 M0～M3 包含 Account／RoleMembership／Workspace、Group 與獨立 Community、
共用交易核心、Demo points ledger、DemoPaymentAdapter、通知、行事曆、Partner OpenAPI、
ProviderConnector 與可獨立執行的 Partner fake upstream。

M4 完成了**六大生活場景的手動閉環**（不經 Agent）：後端有平台服務目錄投影（`core/catalog/`）、
正式廠商 seed（`partner-demo-v5`，依產品負責人提供的 `廠商and表單.md` **兩層制**：12 家可
交易 Provider＋34 個目錄陳列品牌，見[完成矩陣](docs/status/2026-07-31-direction-a-and-vendor-matrix.md)）、
TaskDraft 送出銜接、價格與點數試算、會員取消＋自動退款與點數沖銷、付款失敗恢復與狀態未知
安全重試（`tests/test_m4_scenarios.py` 端到端驗證）；前端依核准的方向 A 完成全部 11 項：
公開首頁、登入、Dashboard、兩層服務探索與詳情頁、TaskDraft 預約精靈（重新整理續填）、
訂單詳情（取消/改期/重付）、行事曆（月/週/列表）、Group、Community（公告＋審核）、
廠商工作台（案件/需求/時段）與平台管理台（personas 重置/故障注入/健康）。價目與時段為
展示資料，正式費率待產品負責人確認後替換。

## 快速開始

需求：Python 3.13、[uv](https://docs.astral.sh/uv/)、Node.js 20+。

先安裝依賴：

```bash
uv sync --dev
cd web/app
npm install
cd ../..
```

接著在四個 Bash 終端機啟動；這些命令不會由測試自動常駐。

```bash
# 終端機 1：現行 Partner API fake upstream，預設 http://127.0.0.1:8020
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export VENDOR_FAKE_PORT="8020"
export PARTNER_FAKE_API_KEY="aiwave-partner"
uv run python -m fake_upstreams.partner_app
```

```bash
# 終端機 2：既有 LifeTask 相容用 Vendor fake upstream，預設 http://127.0.0.1:8021
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export VENDOR_FAKE_PORT="8021"
uv run python -m fake_upstreams.vendor_app
```

```bash
# 終端機 3：Platform API，預設 http://127.0.0.1:8000
export PROVIDER_MODE="standard"
export PARTNER_MODE="fake"
export PARTNER_FAKE_URL="http://127.0.0.1:8020"
export PARTNER_API_KEY="aiwave-partner"
export VENDOR_MODE="fake"
export VENDOR_FAKE_URL="http://127.0.0.1:8021"
export VENDOR_FAKE_CONTROL_KEY="local-demo-key"
export DEMO_RESET_ENABLED="true"
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
```

```bash
# 終端機 4：Vue，預設 http://127.0.0.1:5173
cd web/app
npm run dev
```

M0～M3 的確定性流程與自動測試不需要 LLM。若要測既有 AI 對話，再於 `.env` 提供 OpenAI
相容端點：

```dotenv
API_URL=...
API_KEY=...
MODEL=...
```

## 固定 Demo 身分

Platform API 使用 Bearer token，不接受瀏覽器自行宣告 `X-Account-Id` 或 `X-Role`：

| token | 身分 |
| --- | --- |
| `aiwave` | 會員小圓 |
| `aiwave-chen` | 會員陳伯伯 |
| `aiwave-vivian` | 會員 Vivian |
| `aiwave-new` | 無歷史資料的新會員 |
| `aiwave-demo-resident` | 住戶王小明（`household-wang-xiaoming`） |
| `aiwave-partner` | 王子水電合作方人員 |
| `aiwave-partner-duskin` | DUSKIN 樂清合作方人員 |
| `aiwave-partner-21plus` | 21PLUS 餐廳合作方人員 |
| `aiwave-partner-smile` | 速邁樂加油站合作方人員 |
| `aiwave-partner-blackcat` | 黑貓宅急便合作方人員 |
| `aiwave-partner-cosmed` | 康是美合作方人員 |
| `aiwave-partner-711shop` | 7-ELEVEN 線上購物中心合作方人員 |
| `aiwave-partner-resort` | 統一渡假村合作方人員 |
| `aiwave-partner-foodomo` | foodomo 合作方人員 |
| `aiwave-partner-711c2c` | 7-ELEVEN 交貨便合作方人員 |
| `aiwave-partner-iopenmall` | iOPEN Mall 合作方人員 |
| `aiwave-partner-ibonticket` | ibon 售票合作方人員 |
| `aiwave-manager` | 社區管理者 |
| `aiwave-admin` | 隔離 Demo 環境的平台營運者 |

這些固定 key 僅用於競賽 Demo，不是正式驗證設計。

## 測試

```bash
uv run python -m openapi_spec_validator contracts/vendor-openapi.yaml
uv run pytest -q

cd web/app
npm test
npm run typecheck
npm run build
cd ../..

bash -n run.sh
git diff --check
```

完整測試會使用臨時資料庫與 in-process HTTP client，不會替你留下背景服務。實際通過數量與
驗收步驟以 [Demo 與測試手冊](docs/testing/demo-runbook.md) 的最新紀錄為準。

## 重設 Demo 資料

平台營運者可協調重設平台資料與 Partner fake；既有 Vendor fake 仍需以自己的控制端點重設：

```bash
curl --fail --silent --show-error \
  -X POST \
  -H "Authorization: Bearer aiwave-admin" \
  http://127.0.0.1:8000/api/v1/platform/demo/reset

curl --fail --silent --show-error \
  -X POST \
  -H "X-Fake-Control-Key: local-demo-key" \
  http://127.0.0.1:8021/__fake__/reset
```

## 暫時分享給測試者

安裝 `cloudflared` 並完成依賴安裝後，在專案根目錄使用 Git Bash：

```bash
bash run.sh
```

腳本會啟動兩個 fake upstream、Platform API、Vite 與 TryCloudflare Quick Tunnel；按
`Ctrl+C` 會停止所有由腳本啟動的程序。腳本只用於短期公開測試，不會由 Codex 自動啟動。

## 專案結構

```text
api/             FastAPI Platform API 與 Bearer principal 邊界
core/access/     Account、RoleMembership、Workspace、DemoWorkspace
core/groups/     使用者自行命名的共享 Group
core/communities/獨立 Community、加入申請、邀請與核准
core/fulfillment/Booking、Order、StatusEvent 與正式 reschedule
core/points/     Demo points ledger
core/payments/   DemoPaymentAdapter
core/notifications/持久化通知中心
core/calendar/   AIWave Calendar projection
core/providers/  Standard／Adapter／Workbench ProviderConnector
contracts/       現行 Partner OpenAPI；舊契約位於 contracts/legacy/
fake_upstreams/  可獨立執行、重設與故障注入的上游系統
web/app/         Vue 3 + Vite 前端
docs/            現行規格、ADR、狀態、測試證據與封存索引
```

## 文件

先讀 [產品與平台定案基線](docs/specs/15-agreed-product-and-platform-direction.md)、
[領域詞彙](CONTEXT.md)、[M0 程式碼盤點](docs/status/2026-07-30-m0-code-audit.md)與
[現況和差距](docs/status/2026-07-30-current-state-and-gap.md)。Partner fake、故障注入與正式
API 切換見 [fake upstream 手冊](fake_upstreams/README.md)。
