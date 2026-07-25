# 生活 AI 管家 Web

Vue 3、Vite、TypeScript 的比賽展示應用。網站是完整功能的主要介面；LINE 可作為對話入口與通知管道，之後直接連回相同網頁流程，不依賴 LIFF 才能運作。

## 啟動

先在 repository 根目錄啟動真 AI／SQLite API：

```bash
uv run uvicorn api.app:app --reload
```

再於 `web/app` 啟動 Vue（Vite 會將 `/api` 代理到 `127.0.0.1:8000`）：

```bash
npm install
npm run dev
```

## 驗證

```bash
npm test
npm run typecheck
npm run build
```

## 目前展示路徑

- `/app/today`：個人儀表板、推薦與「不感興趣」偏好回饋。
- `/app/services`：OPENPOINT 式服務入口、搜尋、九項跨廠商服務。
- `/app/orders`：跨廠商統一訂單狀態。
- `/app/community`：社區需求彙整與團購。
- `/app/vendor`：廠商報價、活動與接入流程。
- `/app/platform`：統一 API 連接器與營運健康度。

## 資料來源

前端**不自帶服務目錄、題組定義或金額規則**，全部向後端取得：

| Client | 提供 |
| --- | --- |
| `src/api/serviceCatalogClient.ts` | 服務目錄、題組定義、金額試算 |
| `src/api/insightsClient.ts` | 行為軌跡、消費摘要、可解釋推薦（含官方訂單證據） |
| `src/api/aiInquiryClient.ts` | AI 對話、諮詢單建立與查詢 |

`src/domain/serviceIntake.ts` 只保留型別與**前端即時驗證**（後端在收單時才是權威）。
測試 fixture 由 `tools/dump_catalog_fixture.py` 從後端產生，不手寫。
所有會寫入資料的動作都先經過確認視窗。

瀏覽器以同源 OIDC／session cookie 呼叫平台 API；角色由後端驗證後決定。廠商金鑰只存在後端 Adapter，不會打包進前端，也不採信前端自行宣告的角色。

## UI 基線

- 320px 起可用，650px 與 1050px 兩個主要重排斷點。
- 互動目標至少 44px，支援鍵盤 focus、跳至主要內容與 reduced motion。
- 核心文字色彩組合由測試維持 WCAG AA 的 4.5:1 對比門檻。
