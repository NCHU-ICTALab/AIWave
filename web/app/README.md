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

`src/api/lifeServicesClient.ts` 是真實 `/api/v1` 的前端邊界；目前畫面使用 `src/data/demoFixtures.ts` 的穩定資料，讓展示不受外部廠商 API 狀態影響。所有會寫入資料的展示動作應先經過確認視窗。

瀏覽器以同源 OIDC／session cookie 呼叫平台 API；角色由後端驗證後決定。廠商金鑰只存在後端 Adapter，不會打包進前端，也不採信前端自行宣告的角色。

## UI 基線

- 320px 起可用，650px 與 1050px 兩個主要重排斷點。
- 互動目標至少 44px，支援鍵盤 focus、跳至主要內容與 reduced motion。
- 核心文字色彩組合由測試維持 WCAG AA 的 4.5:1 對比門檻。
