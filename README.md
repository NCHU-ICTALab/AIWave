# AI 生活服務平台

2026 雲湧智生：臺灣生成式 AI 應用黑客松——統一資訊命題
**「AI 生活管家：智慧社區服務需求理解與媒合平台」**

用自然語言說出生活需求，AI 判讀後產生對應的**彈性留資表單**、引導填答，
並依地區、時段、預算與評分**媒合合作廠商**；住戶、社區、廠商與平台端共用同一組服務契約。

## 快速開始

需求：Python 3.13（透過 [uv](https://docs.astral.sh/uv/)）、Node.js 20+

```bash
# 依賴
uv sync

# 獨立廠商 fake API（另開終端機，預設 http://localhost:8020）
uv run python -m fake_upstreams.vendor_app

# 後端 API（預設 http://localhost:8000）
uv run main.py

# 前端（另開終端機，預設 http://localhost:5173）
cd web/app
npm install
npm run dev
```

`.env` 需提供 LLM 設定（OpenAI 相容端點）：

```dotenv
API_URL=...    # 例如 NCHC GenAI 的 /v1/ 端點
API_KEY=...
MODEL=...      # 例如 gemma-4-31B-it
VENDOR_MODE=fake
VENDOR_FAKE_URL=http://127.0.0.1:8020
```

## 測試

```bash
uv run pytest                     # 後端
cd web/app && npm test            # 前端
cd web/app && npm run typecheck   # 型別檢查
uv run python -m openapi_spec_validator contracts/vendor-openapi.yaml
```

## 專案結構

```text
core/          業務核心——唯一碰資料與 LLM 的一層
  forms/         題組引擎（確定性：跳題、驗證、官方 feedback_content）
  data/          官方資料載入（訂單、地區、服務主檔）
  insights/      行為軌跡與可解釋推薦（規則產生，附官方訂單證據）
  services/      應用邊界（HTTP 與未來的 MCP 都經此層）
  clients/       外部服務介面（LLM：地端 Gemma → AWS Bedrock 只換實作）
  vendors/       VendorClient HTTP seam、媒合與履約上游整合
agent/         LLM 上層：口語 → 結構化答案
api/           FastAPI；由 create_app() 建構，可注入 repository 與 LLM
contracts/     可供 fake／real 廠商共同實作的 OpenAPI 3.0 契約
fake_upstreams/ 可獨立執行、重置與故障注入的 upstream servers
web/app/       Vue 3 + Vite 前端
docs/          規格與決策紀錄（source of truth）
raw_data/      命題方提供的官方資料集
```

## 設計要點

**題組定義是單一事實來源。** 可操作服務的表單定義放在後端（對齊官方
`pms_form_topic` schema），Web 表單與 AI 對話讀同一份——新增服務只需新增定義，
前端不必改程式。

**AI 提議、規則把關。** LLM 只負責把口語抽成結構化答案；題目順序、驗證、金額試算
與寫入一律由確定性規則決定。因此報價金額與必填欄位不會因模型出錯而失控。

**畫面上的數字指得出來源。** 消費摘要與推薦皆由命題方提供的 `mms_order_record`
算出，每則推薦都附得出對應的 `record_id`。

## 文件

從 [docs/README.md](docs/README.md) 開始——規格、架構決策紀錄（ADR）與封存的歷程都在那裡。
廠商 API 的手動啟動、reset、故障注入與正式 API 切換見
[fake_upstreams/README.md](fake_upstreams/README.md)。
開發前請先讀 [CLAUDE.md](CLAUDE.md)（常用指令與架構要點）與
[CONTEXT.md](CONTEXT.md)（領域詞彙）。

## 狀態

競賽 P0 已完成：會員產品殼、成熟 AI 對話、跨服務 Hero、獨立 Vendor API、
廠商履約回流、明確同意的群組聚合、Web／AI／MCP 同源與故障恢復均有自動化測試。
自行啟動後的五分鐘操作順序見 [Demo 與測試手冊](docs/testing/demo-runbook.md)，
完成證據見 [P0 工作地圖](docs/work-management/p0-map.md)。
