# 2026-07-30 現況、完成證據與後續差距

> 產品目標與完成定義以 [15 產品與平台定案基線](../specs/15-agreed-product-and-platform-direction.md) 為準。
> 本文件不沿用 2026-07-30 前文件的「完成」標記；每一項狀態都以現行程式與測試為證據。

## 一句話判斷

M0～M3 已落地；M4 完成：**後端六場景閉環**（端到端測試）＋ HTML 原型**經產品負責人核准
（方向 A）**＋ 正式廠商名單（`廠商and表單.md`）落入 seed（partner-demo-v5）＋ **Vue 手動 UI**
（六場景探索、TaskDraft 預約精靈、訂單詳情/取消/改期/重付、行事曆、廠商案件工作台、
平台管理台、8 家合作方登入）。M8 Agent 已完成(2026-07-31):確定性守門(Service Registry/TimeResolver/
ExecutionGrant)、真 LLM(.env Gemma)協調器、與手動共用 TaskDraft/同一 submit 閉包、
AI 頁換腦+側欄共享對話、舊 planner 退場。尚未完成:M9 遠端 MCP、M10 全面稽核與
Demo 主故事排演,因此不能宣稱整個 AIWave 已完成。

## M0～M3 狀態

| 里程碑 | 狀態 | 實際完成 | 權威證據 |
| --- | --- | --- | --- |
| M0 盤點與保護 | 完成 | dirty worktree 保護、保留／重構／移除／延後分類、舊文件封存、可重現測試基線 | [M0 程式碼盤點](2026-07-30-m0-code-audit.md)、封存索引、完整測試 |
| M1 身分與共享 | 完成 | Account、RoleMembership、Workspace、固定 personas、member／partner staff／community manager／platform operator、personal／group／community scope | core/access/、test_access_workspaces.py、test_platform_access_api.py |
| M1 Group | 完成 | 使用者自行命名、邀請加入、改名、離開；沒有家庭／朋友 type | core/groups/、test_groups.py、groupClient.ts |
| M1 Community | 完成 | 獨立模型、加入申請、管理者核准、邀請、加入多社區、預設社區 | core/communities/、test_communities.py、test_platform_access_api.py |
| M2 TaskDraft | 完成 | 持久化 draft、版本控制、欄位來源與狀態轉移 | core/task_drafts/、test_task_drafts.py |
| M2 交易核心 | 完成 | 分離 Booking／CommerceOrder、StatusEvent、Provider selection、正式 reschedule request | core/fulfillment/、test_fulfillment_core.py、test_platform_core_api.py |
| M2 點數與支付 | 完成 | 單一 Demo ledger：取得、折抵、退款、沖銷、到期；DemoPayment 成功、失敗、取消、退款 | core/points/、core/payments/、test_points_and_payment.py |
| M2 通知與行事曆 | 完成 | 持久化 read/unread、scope、deep link、quiet hours；訂單、任務、提醒、Group、Community、手動及週期 projection | core/notifications/、core/calendar/、test_notifications_calendar.py |
| M3 Partner 契約 | 完成 | OpenAPI 3.0.3 v2 為現行唯一契約，涵蓋 catalog、availability、bookings、snapshot、選配 webhook | contracts/vendor-openapi.yaml、test_partner_api_contract.py |
| M3 ProviderConnector | 完成 | Standard、Existing API Adapter、Workbench 共用相同介面；由後端環境變數選擇 | core/providers/、connector contract tests |
| M3 fake upstream | 完成 | 獨立程序、partner-demo-v2、台灣中文 seed、reset、delay、503、timeout、malformed、after-commit state unknown | fake_upstreams/partner_app.py、test_partner_api_contract.py |
| M3 安全與復原 | 完成 | Bearer principal、Provider／scope 綁定、hash API keys、payload-bound idempotency、OCC、安全重試 | access、provider、platform core 與 isolation tests |
| M3 協調 reset | 完成 | 平台、points、交易、通知、Calendar、TaskDraft、Agent session 與 Partner fake 同步回到相容 seed | core/demo_reset.py、test_demo_reset.py |

## 重要邊界

### Platform API

- Web 使用 Platform API，不直接操作 repository 或 fake upstream。
- 新核心由 api/platform_access.py 與 api/platform_core.py 對外提供。
- 舊 X-Account-Id／X-Role 即使由 client 傳入也不具權威；Bearer principal 決定帳號、角色、
  Workspace、Provider 與 scopes。
- 手動服務表單不再只寫入 Pinia：送出會持久化為 order 或誠實標示的 service request。
- 非購物服務在 M4 Provider-specific fulfillment 完成前，不會假裝已成立 booking。

### Partner 與 legacy Vendor

- 8020：現行 Partner API v2 fake，使用 contracts/vendor-openapi.yaml。
- 8021：既有 LifeTask 相容用 legacy Vendor fake，舊契約位於 contracts/legacy/。
- compatibility path 保留回歸價值，但不算 M3 Partner API 或 M4 正式閉環證據。

### 前端

- M0～M3 只修正資料來源、Bearer auth、角色隔離、Group 定義、真實 persistence 與無作用控制；
  沒有在 HTML 方向核准前重寫正式 Vue 視覺。
- 首頁與點數頁改讀同一 Demo points ledger；新會員不再繼承 180 點。
- 本地 seed 訂單、無 handler 的主要按鈕與靜態 connector／campaign 成功狀態已移除。

## M4 已完成（2026-07-30 本輪）

| 項目 | 實際完成 | 權威證據 |
| --- | --- | --- |
| 平台目錄投影 | `core/catalog/`：Provider/Location/Offering/Resource/Slot 投影表、`CatalogSyncService` per-provider 誠實同步、`/catalog/*` 探索與 health 端點；探索不再依賴 upstream 存活 | test_m4_scenarios.py |
| 六場景 fake upstream | `partner-demo-v5` seed：7 個 Provider（住×2/食 21PLUS/行 速邁樂+黑貓/醫 康是美/預 7-ELEVEN/樂 統一渡假村）、多據點/方案/資源、相對日期時段、建單消耗 slot、取消釋放；品牌依產品負責人 2026-07-30 提供的正式名單（廠商and表單.md） | fake_upstreams/partner_seed.py、test_partner_api_contract.py |
| 多 Provider connector | ProviderBookingService 依 booking 的 providerId 解析 connector；每場景 Provider 各自 API key（`PARTNER_PROVIDER_KEYS`）；新增 5 組 partner demo 帳號與 workspace | core/providers/service.py、core/access/ |
| TaskDraft→交易銜接 | `POST /task-drafts/{id}/submit`：domain 必填驗證（`core/catalog/domains.py`）、booking/commerce 分流、價格由目錄決定不信任 client、draft 記錄產出交易 id、重複提交回同一筆 | test_m4_scenarios.py |
| 試算 | `POST /quotes`：確定性計算、讀會員實際點數餘額、折抵上限 | test_m4_scenarios.py |
| 會員取消＋退款 | `POST /bookings/{id}/cancellation`、`/commerce-orders/{id}/cancellation`：上游取消→本地轉移→自動全額退款＋點數沖銷→通知＋行事曆取消 | test_m4_scenarios.py |
| 付款↔訂單 wiring | 付款主體所有權驗證（IDOR 防護）；失敗→`payment_failed`、重付成功→回 `placed`（失敗恢復） | test_m4_scenarios.py、test_platform_core_api.py |
| Projection 補齊 | 取消同步取消行事曆事件；改期核准後行事曆跟新時段；通知使用 per-domain 狀態名稱（訂位「店家確認」、宅配「理貨」…）；StatusEvent 依插入序穩定排序 | api/platform_core.py、core/catalog/domains.py |
| 工作台接入端點 | `PUT /provider/catalog`、`PUT /provider/availability`（partner staff、Provider 綁定、寫後自動同步投影） | api/platform_core.py |
| 協調 reset 擴充 | demo reset 後重新同步目錄投影，seed version 一致 | core/demo_reset.py、test_demo_reset.py |
| 六場景閉環測試 | 住（含點數/改期/完工/重開 app 持久性）、食（取消＋slot 釋放）、醫（OCR 未確認擋下）、行、預（付款失敗恢復＋配送）、樂（佔位＋取消退款沖銷）＋隔離/IDOR/冪等/狀態未知重試/503 誠實回報 | tests/test_m4_scenarios.py（9 tests） |

### M4 Vue 手動 UI（2026-07-30 方向 A 核准後完成）

| 項目 | 實際完成 | 權威證據 |
| --- | --- | --- |
| 基礎層 | 共用 `src/api/http.ts`（Bearer/Idempotency/錯誤正規化）、`src/api/platformClient.ts`（目錄/TaskDraft/試算/Booking/Order/付款/通知/行事曆/管理）、`tests/fixtures/platformStub.ts`（有狀態測試假後端） | typecheck、27 檔 vitest |
| 服務探索 | ServicesView 六場景分組（食/醫/住/行/預/樂）、真實品牌 icon（`public/brand-icons/`，官網 favicon）、預約 CTA 導 booking wizard | servicesExplore.spec.ts |
| 預約精靈 | `/user/booking`：TaskDraft 驅動（第一次下一步建草稿、每步 OCC 更新、409 誠實重載、`?draft=` 重新整理續填）、據點→方案→真實時段→domain 欄位（醫場景強制 rx_confirmed）→試算（點數上限 422）→submit→DemoPayment；503 顯示重試同步 | bookingWizard.spec.ts（5 tests） |
| 訂單 | OrdersView 平台 booking/commerce 列表；`/user/orders/:id` 詳情：per-domain 狀態名稱、StatusEvent 時間軸、取消（含退款顯示）、改期（重查 availability）、payment_failed 重付、providerSync 警示 | orderDetail.spec.ts |
| 行事曆 | `/user/calendar`（首頁卡片進入，不佔主導覽）：日期分組、來源篩選、booking 連訂單、手動事件 | calendarView.spec.ts |
| 首頁/會員中心 | TodayView 近期行程卡＋通知未讀；MemberView 行事曆入口、reset 走 platformClient | todayInsights.spec.ts 續過 |
| 廠商工作台 | VendorView 平台案件分頁：合法轉移按鈕（不合法不渲染）、409 重載、aria-live 同步提示、commerce 轉移、snapshot | vendorPlatformBookings.spec.ts |
| 平台管理台 | PlatformView 重寫：目錄健康表、重新同步（partial 誠實顯示）、demo reset 確認 | platformAdmin.spec.ts |
| 登入 | 帳密登入卡（示範驗證與錯誤狀態）＋ 8 家合作方品牌可選（與 access seed 一致） | loginAndAccess.spec.ts |
| 方向 A 版面對齊（2026-07-31） | 公開首頁 `/`（產品價值、六場景、右上登入，spec 15 §9.1）；手機 ≤650px 底部導覽（同一 nav 元素固定底部，修 backdrop-filter 包含塊陷阱）；行事曆月/列表切換（週日開頭月曆格） | loginAndAccess.spec.ts、實站截圖 |

### 實站瀏覽器稽核（2026-07-30，四服務全啟動後以 Playwright 驗證）

- 10 個頁面 × 390px/1440px：無水平捲動、單一 h1、欄位皆有 label、無 console/page error
  （登入頁無 skip-link 為設計取捨——該頁無重複區塊，符合 WCAG 2.4.1）。
- **住・修繕預約流程在真實堆疊端到端走通**（fake upstream 8020 → Platform API → Vue：
  據點→方案→真實時段→表單→試算→送出，取得真實 booking id）。
- 稽核發現並已修：行事曆新增事件表單 390px 水平溢出（scoped CSS）；partner 前端
  accountId 誤用 access 帳號 id 導致 legacy vendor-api 403（改回 Provider id 慣例）；
  投影過期會短暫列出剛被訂走的時段（送出時會被誠實擋下）→ 建單/取消成功後自動刷新
  該 Provider 的 slot 投影。

M4 尚未包含（誠實邊界）：取消收費規則目前一律全額退款（cancelPolicyHours 僅記錄於目錄，
費率待產品負責人確認）；adapter 接入的建單 payload 相容性仍未修（六場景皆走 standard 或
workbench）；改期申請無查詢端點（送出後僅顯示等待回覆）；系統化 E2E 測試套件與全站
WCAG 深度稽核（含鍵盤逐頁走查）屬 M10。

## 仍未完成

| 後續里程碑 | 差距 |
| --- | --- |
| 廠商細節 | 取消費率、正式價目與時段規則待產品負責人確認後替換 seed；「行・叫車」（ibon 叫車為機台流程）未線上化 |
| P2 | 醫療僅辨識展示流程（處方箋照片上傳 OCR 未實作，欄位以人工確認 checkbox 代表）；語音依時程處理 |
| M6 HTML 審批 | ✅ 方向 A 已核准（2026-07-30）；原型保留於 `design-system/aiwave/pages/` 作設計基準 |
| M7 正式 Web | 六場景手動閉環 UI 已整合;390/1440 全頁截圖走查與 WCAG 2.2 AA 全面驗收仍待 M10 稽核 |
| M8 Agent | ✅ 完成(2026-07-31):`core/agent_core/`(Registry/TimeResolver/Grant/orchestrator/sessions)、`/platform/agent/*` 端點與手動共用 submit/payment 閉包、AgentConversation+AgentDrawer、真 LLM 實站三條流程驗證(單場景/跨場景一張授權兩單/切手動 user 值優先);證據:test_agent_guardrails.py(11)、test_agent_m8.py(5)、runbook §8 |
| M9 遠端 MCP | 現有 stdio compatibility proxy 已只走 Platform API，但不是 mcp==2.0.0 Streamable HTTP Gateway |
| M10 hardening | 六大場景 browser E2E、正式 Demo 主故事與整體 WCAG 稽核尚未完成 |
| 延後 | LINE／Discord、正式 AWS、簡報與商業話術 |

## 目前不應開始

- 未取得正式品牌／表單前自行補廠商、價目或服務欄位。
- HTML 原型未核准前全面重寫 Vue。
- 以 legacy Hero 或舊 MCP 測試宣稱新的 Agent／MCP 目標完成。
- 新增無 handler 按鈕、靜態統計、假推薦或只存在瀏覽器記憶體的成功流程。
- LINE、語音、正式醫療與正式 AWS 部署。

## 驗證入口

- [M0 程式碼盤點](2026-07-30-m0-code-audit.md)
- [M0～M3 測試與操作手冊](../testing/demo-runbook.md)
- [Partner fake upstream 手冊](../../fake_upstreams/README.md)
- [封存索引](../archive/README.md)

下一階段開始每一類服務前，唯一會直接阻擋產品細節的輸入仍是：經產品負責人確認的統一體系
或合作廠商、服務欄位、價目／時段規則與代表性表單。
