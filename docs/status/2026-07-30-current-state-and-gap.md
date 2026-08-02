# 2026-08-01 現況、完成證據與後續差距

> 產品目標與完成定義以 [15 產品與平台定案基線](../specs/15-agreed-product-and-platform-direction.md) 為準。
> 本文件不沿用 2026-07-30 前文件的「完成」標記；每一項狀態都以現行程式與測試為證據。

## 一句話判斷

M0～M3、M4 六場景手動閉環與 M8 Agent 仍以原有證據成立；本輪另完成 v4 的 Turn／Session
契約、隔離 Wiki、固定生活圈服務、主動關懷候選→送達、可編輯任務包、成果／成就／Demo
回饋／Provider 結算投影，以及會員端生活成果與生活圈頁。v4 的內部 API、測試替身與前端
流程可重現；**完整五分鐘實站 Demo 尚不能標記完成**，因為正式／授權生活指南來源與會場
官方座標／人工檢查仍是外部或人工 gate，Amazon Location、正式 Provider／OPENPOINT／AWS
資料也尚未取得。競賽 Demo 本身已改用清楚標示的內部固定資料，可直接走查互動。

## v4 增量現況（2026-08-01）

| 能力 | 現況 | 可重現證據 |
| --- | --- | --- |
| Turn／Action／ToolResult／TaskPatch | 已建立 stable ID、expectedVersion、capability risk/schema/principal 邊界；grounded 第二階段對正式 LLM client 可用，模型失敗或 facts 矛盾會保留安全摘要 | `core/agent_core/contracts.py`、`turns.py`、`orchestrator.py`；`tests/test_agent_v4_contracts.py`、`tests/test_v4_acceptance_matrix.py` |
| ConversationSession | create/list/get/rename/archive/restore、metadata、pending grant、active task package、OCC、workspace/account 隔離；封存保留資料，沒有永久刪除宣稱 | `core/agent_core/sessions.py`、`api/platform_core.py`；session lifecycle tests、`web/app/tests/agentSessions.spec.ts` |
| LLM Wiki | product-help 與內部編寫的 life-guide 中元 Demo 都已發布；domain、locale、region、app version、引用與 action allowlist、無證據 fallback 已驗證；Wiki body 只作資料，不能變成工具 action；無關問題不會誤配第一篇文章 | `core/wiki/service.py`、`docs/knowledge/`；`tests/test_v4_wiki.py` |
| 會場生活圈 | ReachabilityProvider、固定 GeoJSON schema、步行／機車與 10／15 分鐘限制、Catalog Location 篩選、Provider Service Area 分流與前端單次定位不保存已完成；目前使用明確標示為內部 Demo approximation 的固定 GeoJSON，非即時路況／導航／官方座標 | `core/reachability/`、`data/reachability/README.md`、`demo.geojson`、`web/app/src/views/ReachabilityView.vue`；`tests/test_v4_reachability.py`、`web/app/tests/reachability.spec.ts` |
| 主動關懷 | 白名單 Demo event、candidate 與 message 分離；delivery 會先套用來源／偏好／頻率／安靜時段 policy，讀取不再產生副作用；原因／來源／資料／ignore／snooze／close／open guide 與「只整理清單、不下單」已完成 | `core/proactive_care/service.py`、`policy.py`；`tests/test_v4_care.py`、`tests/test_v4_care_policy.py` |
| 關懷正式政策 | quiet／balanced／caring、類別覆寫、頻率、安靜時段、交易通知獨立計數與資料來源白名單已做成不進主 Demo 設定頁的可測試 policy，並接在 delivery 前 | `core/proactive_care/policy.py`、`docs/architecture/v4-care-delivery-policy.md`；`tests/test_v4_care_policy.py` |
| LifeTaskPackage | source／beneficiary／ServiceLocation／TaskDraft refs、逐項修改／暫緩／移除／Catalog option replacement、OCC、bounded grant、跨 Provider partial failure 與 event-key 冪等已完成；執行時以最新任務包項目同步共用 TaskDraft 再 submit | `core/task_packages/`、`api/platform_core.py`；`tests/test_v4_task_packages.py`、`tests/test_agent_m8.py` |
| LifeOutcome／商業投影 | completed／delivered once-only outcome、一次 Achievement、Demo reward budget/cap/dedupe/reversal、Provider fee、平台結算與會員 fee 隔離已完成；全額 operator refund 會產生 `refunded` reversal projection | `core/outcomes/`、`api/platform_core.py`；`tests/test_v4_outcomes.py`、`tests/test_platform_core_api.py` |
| Agent／v4 畫面證據 | Assistant 畫面呈現 ToolResult 狀態、facts、稽核參照、Wiki 引用與更新日；生活圈／關懷／成果／Provider 頁面保留 Demo、pending、非正式限制文案 | `web/app/src/components/AgentConversation.vue`、`web/app/src/views/`；`web/app/tests/assistantConversation.spec.ts`（6）、全套 Vitest（31 files／154 tests）、typecheck/build |
| 會員／Provider 畫面 | `/user/life-circle`、`/user/wellbeing` 與 `/partner`；生活圈切換、關懷卡、任務包項目操作、成果／成就／Demo 回饋、Provider 結算、真實限制文案與 responsive CSS 已完成 | `web/app/src/views/ReachabilityView.vue`、`WellbeingView.vue`、`VendorView.vue`；前端 route tests、typecheck/build |
| 驗收入口 | Agent／Wiki／生活圈／關懷／任務包／成果矩陣已集中，非 deterministic 文案不做逐字 snapshot | [v4 acceptance matrix](../testing/v4-acceptance-matrix.md) |

### 最新可重現驗證（2026-08-01）

- 受最新後端變更影響的回歸：`uv run pytest -q tests/test_agent_m8.py tests/test_agent_v4_contracts.py tests/test_v4_task_packages.py tests/test_v4_care.py tests/test_v4_care_policy.py tests/test_v4_wiki.py tests/test_v4_outcomes.py tests/test_platform_core_api.py` → 39 passed。
- 前端：`npm test -- --run`（於 `web/app`）→ 31 test files／155 tests passed；`npm run typecheck` 與 `npm run build` passed。
- 完整 fake stack 的 `npm run audit:ui` 回傳 exit 0；它是自動化 route audit，不替代新 v4 頁面的真實瀏覽器人工走查。
- `uv run pytest -q` 全庫單次執行曾在 300 秒 timeout；2026-08-01 已以五批覆蓋全部 53 個 backend test files 且全部通過，另以 39-test v4 受影響組合重跑確認，故不宣稱單次全庫命令通過。

### v4 目前不是完成的項目

- 中元 Demo 指南已由 AIWave 內部編寫並人工檢視後以 `published` 提供展示；颱風、搬家／入厝與正式／授權來源、商業使用權、地域差異仍是外部 gate，不把 Demo 內容說成官方建議。
- 華南銀行國際會議中心官方精確座標與外部人工檢查尚未取得；目前 `demo.geojson` 是可操作但明確標記 `isDemo`、非即時、非導航的固定示意範圍。
- 390px／1440px 新 v4 頁面的真實瀏覽器鍵盤走查、五分鐘實站彩排／錄影備援尚未完成；元件測試與 production build 不替代人工 gate。
- 本輪嘗試用 in-app browser 取得新 v4 頁面的畫面證據，但執行環境沒有可用 browser instance；因此沒有把瀏覽器畫面驗收標成通過。
- Amazon Location adapter、正式 Provider／品牌／價格／取消規則、OPENPOINT 官方活動規則、AWS production verification/secrets 仍是外部 gate；Session 永久刪除／retention policy 與真實 LLM naturalness 人工評分也尚未由產品／評審確認。

### 剩餘 unchecked task 與 blocker 對照

| v4 task | 目前未勾選原因 |
| --- | --- |
| 1／11／14.3 | 競賽 Demo 的內部指南與「只整理、不下單」流程已完成；正式／授權生活指南與地域審核仍未取得。 |
| 2（僅因 2.5）／3／9.2 | 會場官方精確座標、Provider／Location 外部座標與人工檢查 GeoJSON 尚未由外部提供／確認；內部固定 Demo fixture 已可走查。 |
| 9.7 | Amazon Location 的帳號權限、費用、覆蓋與 production verification 尚未具備；固定 provider 是選配，不以空殼代替。 |
| 14（僅因 14.3、14.5）／15.5 | 需要正式指南或真實瀏覽器的 390px／1440px、鍵盤、WCAG 與畫面人工 gate。 |
| 15.6 | 尚未有完整五分鐘實站彩排與錄影／離線備援；自動化 fake-stack audit 不替代現場彩排。 |
| Session retention／naturalness review | 永久刪除與 retention period 需要產品／法務決策；真實 LLM 自然度需要人類評分，非 repository 自動測試可替代。 |

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
| 方向 A 版面對齊（2026-07-31） | 公開首頁 `/`（產品價值、六場景、右上登入，spec 15 §9.1）；手機 ≤650px 底部導覽（同一 nav 元素固定底部，修 backdrop-filter 包含塊陷阱）；行事曆以可翻月的月曆格為主，並保留來源篩選與手動新增 | loginAndAccess.spec.ts、calendarView.spec.ts |

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
| v4 內部垂直切片 | ✅ Turn／Session／Wiki／Reachability／Care／TaskPackage／Outcome 與會員端頁面已完成；以 `docs/testing/v4-acceptance-matrix.md` 和本文件上方表格為準，不等同正式生活指南、正式地理資料或完整實站彩排 |
| v4 外部資料 gate | 尚未完成：正式／授權生活指南來源、會場官方精確座標／GeoJSON 人工檢查、Provider／OPENPOINT 正式資料；內部 Demo 資料維持清楚的非正式限制 |
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
