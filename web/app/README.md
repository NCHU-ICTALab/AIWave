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

## AI 智慧社區 × 社區團購 Demo

這次 Demo 以「管委會訂閱」為入口、以「社區團購」為商業突破口，與既有後端串接頁隔離在 `/demo/*`，不需要 API、資料庫或真實 LLM。

### Demo 路由與角色切換

- `/demo/community`：住戶王小明的日光森林社區頁，包含公告、包裹、報修、設備保養、公設預約、問社區與服務優惠；`/demo/resident` 保留為同一頁的住戶入口。
- `/demo/resident/group-buy/:groupBuyId`：團購詳情、規格、數量、跟團、取消與進度。
- `/demo/member`：統一 Demo 的個人檔案；從「我的社區」可回到 `/demo/community`。
- `/demo/committee`：主委陳建華的開團、訂單彙總、KPI、分潤試算與 Wiki 管理摘要。
- `/demo/subscription`：112 戶的標準月費、試辦優惠、住戶省下與社區淨效益。

從 `/login` 的「AI 智慧社區 × 社區團購」統一入口選擇「住戶王小明」或「主委陳建華」進入；登入後也能從右上角「Demo 角色切換」選單切換角色。選擇「重設 Demo」會清除本次開團、跟團、問答與未回答問題，回到住戶初始狀態並前往 `/demo/resident`。程式上也可呼叫 `useCommunityDemoStore().resetDemo()`。

### 九步簡報走查

1. 從 `/login` 選擇「以住戶王小明進入」，先看 2 件待領包裹、電梯保養公告、報修進度與進行中團購。
2. 在「問社區」輸入「垃圾車幾點來」，展示 AI 思考狀態、完整規則、來源與相關問題。
3. 再問「裝修可以假日施工嗎」，展示平日、週六與週日／國定假日規則。
4. 展示冷氣清洗市價 NT$3,800、社區價 NT$3,500，點擊問號看訂閱回饋說明。
5. 切換主委，在 `/demo/committee` 按「發布杜拜巧克力開團」；商品起始進度固定 7/10。
6. 切回住戶，進入杜拜巧克力，選「六入 × 1」並按「我要 +1」；進度變成 8/10、訂單金額 NT$780。
7. 切回主委，查看王小明、A 棟 12F-3、六入 × 1、NT$780 的依住戶／規格彙總與成交額 KPI。
8. 查看 Wiki 查詢排行、最新問題與未回答清單，將問題標記為待補充。
9. 進入 `/demo/subscription`，展示標準月費 NT$12,000／月、試辦優惠 NT$6,000／月、本月住戶省下 NT$18,420 與淨效益 +NT$12,420。

### Mock 與 LINE Bot 對接邊界

型別在 `src/domain/communityDemo.ts`，集中世界觀資料在 `src/data/communityDemoSeed.ts`，狀態與操作由 `src/services/communityDemoService.ts` 和 `src/stores/communityDemo.ts` 提供。未來 LINE Bot 可直接讀取同一組 typed service 函式：

`listAnnouncements()`、`getResidentDashboard(householdId)`、`askCommunity(query, householdId)`、`reportUnanswered(query, householdId)`、`listGroupBuys()`、`getGroupBuy(id)`、`publishDemoGroupBuy(input)`、`joinGroupBuy(input)`、`listMyOrders(householdId)`、`getCommitteeDashboard()`、`getSubscriptionSummary()`、`resetDemo()`。

本次不實作 LINE Messaging API、聊天模擬器或真實 LLM；前端 Demo 只使用 Pinia + typed mock service。
