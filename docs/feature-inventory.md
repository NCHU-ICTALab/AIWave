# 功能總覽（Feature Inventory）

> 盤點日期：2026-08-02。**用途：讓新的工作 session 在幾分鐘內知道「現在有哪些功能、程式碼在哪、哪個測試證明它、哪些是真的哪些是 Demo」。**
>
> 這份文件描述**現行程式的實際能力**，是「有什麼」的清單。其他文件的分工：
>
> - 「應該是什麼」→ [15 產品與平台定案基線](specs/15-agreed-product-and-platform-direction.md)（最高依據）、[16](specs/16-proactive-life-butler-and-commercial-loop.md)、[17](specs/17-conversational-agent-session-and-llm-wiki.md)
> - 「還差什麼、為什麼還沒完成」→ [現況與差距](status/2026-07-30-current-state-and-gap.md)
> - 「怎麼跑起來驗收」→ [v4 驗收矩陣](testing/v4-acceptance-matrix.md)、[v4 五分鐘 Demo runbook](testing/v4-five-minute-demo-runbook.md)
> - 「詞彙定義」→ [CONTEXT.md](../CONTEXT.md)
>
> **維護規則：新增或移除功能時，同步更新本文件的對應列。** 寫進規格不等於功能存在；本文件只列出有程式與測試的項目。

---

## 0. 三十秒版

**社區小統**（產品對外名稱；程式與憑證裡的 `aiwave*` 識別碼刻意不改名）是一個**會員優先的生活服務平台**：住戶用自然語言講出生活需求 → 平台理解並拆成任務 → 對到真實服務目錄 → 走完預約／購買／付款／取消的完整閉環，並在會員授權後主動提醒與關懷。

四種角色各有獨立入口（ADR-0015）：**住戶 `/user`**、**管委會 `/community`**、**合作廠商 `/partner`**、**平台營運 `/platform`**。

規模概況：

| 項目 | 數量 |
| --- | --- |
| `core/` 業務模組 | 33 個套件、104 個 Python 檔 |
| HTTP 端點 | 158（`api/app.py` 85 + `platform_core` 60 + `platform_access` 13） |
| 後端測試檔 | 57 |
| 前端頁面（Vue view） | 28；前端測試檔 38 |
| ADR | 17 份現行 |

---

## 1. 系統組成與啟動

| 元件 | 位置 | 啟動 | 說明 |
| --- | --- | --- | --- |
| Platform API | `api/app.py`（`create_app()`） | `uv run main.py`（:8000） | 唯一的業務進入點；`/` 只是資訊頁 |
| Web 前端 | `web/app`（Vue 3＋Vite＋Pinia＋TS） | `npm run dev`（proxy `/api` → :8000） | 四個角色工作區共用一個 router |
| Partner fake upstream | `fake_upstreams/partner_app.py` | :8020 | 現行 Partner API v2 契約（`contracts/vendor-openapi.yaml`） |
| Legacy vendor fake | `fake_upstreams/vendor_app.py` | :8021 | 舊 LifeTask 相容路徑，非新契約證據 |
| MCP server | `mcp_server/server.py` | `uv run python -m mcp_server.server` | stdio 相容層，**只透過 Platform API**，自己不碰 DB |
| LLM | `core/clients/llm.py` | `.env` 的 `API_URL`/`API_KEY`/`MODEL` | 地端為 NCHC Gemma（OpenAI 相容）；`bedrock.py` 是 AWS 替換座 |
| 持久化 | `tmp/*.sqlite3` | — | SQLite；每個 repository 都在 Protocol 後面，可換 RDS |

**分層鐵律**：`core/` 是唯一碰資料與 LLM 的層；HTTP 與 MCP 都只是傳輸層，不得自行實作業務規則（ADR-0004）。

---

## 2. 功能清單

各表格欄位一致：**功能 → 實際做到什麼 → 程式碼 → 對外端點 → 證明它的測試**。

### A. 身分、角色與範圍

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 帳號與角色 | Account、RoleMembership、Workspace、固定 personas；member／partner staff／community manager／platform operator | `core/access/` | `/api/v1/auth/me`、`/auth/workspaces`、`/auth/workspace-session` | `test_access_workspaces.py`、`test_platform_access_api.py` |
| Bearer 授權邊界 | Bearer principal 決定帳號、角色、Workspace、Provider、scopes；client 傳的 `X-Account-Id`／`X-Role` 不具權威 | `core/access/repository.py` | 全部 platform 端點 | `test_platform_access_api.py` |
| Group（自訂群組） | 自行命名、邀請加入、改名、離開；**沒有家庭／朋友 type** | `core/groups/` | `/api/v1/groups*` | `test_groups.py` |
| Community（社區） | 獨立模型、加入申請、管理者核准、邀請、加入多社區、預設社區 | `core/communities/` | `/api/v1/platform/communities*` | `test_communities.py` |
| Scope 統一機制 | 個人／家庭／社區是同一套 `owner_scope`＋`grp`／`group_member`，不是三套子系統（ADR-0003） | 跨模組 | — | 各 scope 隔離測試 |

### B. 服務目錄與 Provider 接入

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 平台目錄投影 | Provider／Location／Offering／Resource／Slot 投影表；探索讀投影，**不依賴 upstream 存活**，但下單前仍由 connector 現場驗證 | `core/catalog/repository.py`、`sync.py` | `/catalog/providers`、`/catalog/listings`、`/catalog/availability`、`/catalog/sync`、`/catalog/health` | `test_m4_scenarios.py`、`test_service_catalog.py` |
| Domain registry | 每個 offering 的 `domainType` → 必填 TaskDraft 欄位、booking vs commerce 分流、per-domain 狀態名稱（訂位「店家確認」、宅配「理貨」…） | `core/catalog/domains.py` | — | `test_m4_scenarios.py` |
| 確定性試算 | 價格由目錄決定、不信任 client；讀會員真實點數餘額與折抵上限（Demo 規則 1 點＝NT$1） | `core/catalog/pricing.py` | `POST /quotes` | `test_quote_response.py`、`test_m4_scenarios.py` |
| ProviderConnector | Standard／Existing API Adapter／Workbench 三種接入共用同一介面，由環境變數選擇（ADR-0007 統一為 ProviderConnector） | `core/providers/connector.py`、`service.py` | — | `test_partner_api_contract.py`、`test_retail_connector.py` |
| 多 Provider 路由 | 依 booking 的 `providerId` 解析 connector；每場景 Provider 各自 API key（`PARTNER_PROVIDER_KEYS`） | `core/providers/service.py` | — | `test_m4_scenarios.py` |
| 廠商工作台接入 | 廠商直接維護目錄與時段，寫入後自動同步投影 | `api/platform_core.py` | `PUT /provider/catalog`、`PUT /provider/availability`、`GET /provider/snapshot` | `test_vendor_platform_integration.py` |
| Partner API 契約 | OpenAPI 3.0.3 v2 是現行唯一契約，涵蓋 catalog／availability／bookings／snapshot／選配 webhook | `contracts/vendor-openapi.yaml` | fake :8020 | `test_partner_api_contract.py`、`test_fake_upstream_server.py` |
| 服務媒合 | 命題明列的七項條件（類型／地區／時段／預算／緊急度／服務範圍／評分），每項對應一條可解釋規則，回傳 `reasons`；LLM 不參與評分 | `core/matching/vendors.py` | `GET /api/v1/match/{service_id}` | `test_matching.py` |

### C. 需求理解：題組引擎與留資表單

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 官方題組引擎 | 完全對齊官方 `pms_form`／`pms_form_group`／`pms_form_topic`／`pms_topic_option` schema；題型**只用官方 1–10 碼**；題目排序、跳題（存在官方 JSONB `feature.skipLogic`，零 DDL 變更）、驗證、`progress()`、輸出官方 `answerList` | `core/forms/engine.py`、`models.py` | `GET /api/forms` | `test_form_engine.py` |
| 表單種子 | F1 修繕／F2 團購／F3 公設 | `core/forms/seed_forms.py` | — | `test_form_engine.py` |
| 服務目錄（9 項） | 服務清單、搜尋、每項服務的表單與報價 | `core/forms/service_catalog.py`、`core/services/service_search.py` | `/api/v1/services*` | `test_service_api.py`、`test_service_catalog.py` |
| 對話式填單 | 「問題是模板、答案抽取是 LLM」的刻意分工；`interpret()` 回 `answer｜skip｜unclear`；地區以口語名稱回來再解成官方 county／district code；**任何 LLM 或解析失敗都降級為 `unclear`，不會讓回合崩潰** | `agent/form_agent.py` | `POST /api/chat/start`、`/api/chat/message`、`/api/chat/message/stream` | `test_ai_inquiry_api.py` |
| 地區解析 | 口語地名 → 官方 `county_code`／`district_code`；正規化「臺→台」；補上少數命名空間化的 demo 行政區（官方樣本只是子集） | `core/data/regions.py` | — | `test_regions.py` |
| 諮詢單生命週期 | `INQ-YYYYMMDD-NNN` 編號、`inquiry_events` 稽核、報價／確認／修改／取消／完成 | `core/inquiries/repository.py` | `/api/v1/inquiries*` | `test_inquiry_lifecycle.py` |

### D. 交易閉環（M4 六場景）

住／食／行／醫／預／樂六個場景走的是同一條閉環。

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| TaskDraft | 持久化草稿、版本控制（OCC）、欄位來源標記、狀態轉移；**Agent 與手動 UI 共用同一份 TaskDraft** | `core/task_drafts/` | `/task-drafts`、`PATCH /task-drafts/{id}`、`/transition` | `test_task_drafts.py` |
| 草稿送單 | domain 必填驗證 → booking／commerce 分流 → 價格由目錄決定 → 記錄產出的交易 id；**重複提交回同一筆** | `api/platform_core.py` | `POST /task-drafts/{id}/submit` | `test_m4_scenarios.py` |
| 交易核心 | Booking 與 CommerceOrder 分離、StatusEvent 時間軸（依插入序穩定排序）、Provider selection | `core/fulfillment/` | `/bookings*`、`/commerce-orders*` | `test_fulfillment_core.py`、`test_platform_core_api.py` |
| 取消＋退款 | 上游取消 → 本地轉移 → 自動全額退款＋點數沖銷 → 通知＋行事曆取消 | `api/platform_core.py` | `POST /bookings/{id}/cancellation`、`/commerce-orders/{id}/cancellation` | `test_m4_scenarios.py` |
| 改期 | 正式 reschedule request 與廠商審核；核准後行事曆跟著新時段 | `core/fulfillment/` | `POST /bookings/{id}/reschedule-requests`、`/booking-reschedule-requests/{id}/review` | `test_m4_scenarios.py` |
| 付款 wiring | 付款主體所有權驗證（IDOR 防護）；失敗 → `payment_failed`，重付成功 → 回 `placed` | `core/payments/demo.py` | `POST /payments`、`/payments/{id}/cancel`、`/refund` | `test_points_and_payment.py`、`test_m4_scenarios.py` |
| 安全與復原 | hash 過的 API key、payload-bound idempotency、OCC、上游狀態未知時的安全重試、503 誠實回報 | `core/access/`、`core/providers/` | — | `test_m4_scenarios.py`（含隔離／IDOR／冪等） |

### E. 點數、通知與行事曆

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| Demo 點數帳本 | 單一 ledger：取得、折抵、退款、沖銷、到期 | `core/points/ledger.py` | `GET /points`、`POST /admin/points` | `test_points_and_payment.py` |
| Demo 付款 | 成功、失敗、取消、退款四種路徑 | `core/payments/demo.py` | 見 D | `test_points_and_payment.py` |
| 通知 | 持久化 read／unread、scope、deep link、安靜時段 | `core/notifications/` | `/notifications`、`/notifications/{id}/read`、`PUT /notification-preferences/quiet-hours` | `test_notifications_calendar.py` |
| 行事曆 | 訂單、任務、提醒、Group、Community、手動與週期事件的投影 | `core/calendar/` | `/calendar/events`（GET／POST／PATCH） | `test_notifications_calendar.py` |

### F. 對話 Agent（v4 核心）

設計原則（ADR-0017）：**LLM 規劃、規則執行**。LLM 只做三件事——把語句拆成子任務、抽服務關鍵詞與日期片語、抽表單欄位值；服務是否存在、日期、方案時段、價格、授權全部由確定性模組裁決。提案理由是模板文字，永遠可驗證。

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| Agent 協調器 | 理解 → 拆解 → 查真目錄 → 提案 → 預填 TaskDraft；LLM 解析失敗重試一次，再失敗誠實降級為追問 | `core/agent_core/orchestrator.py` | `POST /agent/messages`、`/agent/messages/stream` | `test_agent_m8.py`、`test_agent_guardrails.py` |
| Turn／Action／ToolResult／TaskPatch 契約 | stable ID、`expectedVersion`、capability 的 risk／schema／principal 邊界；grounded 第二階段對正式 LLM 可用；模型失敗或 facts 矛盾時保留安全摘要 | `core/agent_core/contracts.py`、`turns.py` | — | `test_agent_v4_contracts.py`、`test_v4_acceptance_matrix.py` |
| Service Registry | 口語需求詞 → domain 與 offering 候選；模糊需求（如「洗衣服」）回釐清選項，**不硬答也不回「沒有服務」**；`vocabulary()` 把同一份字彙交給需求理解器當 bounded context，模型才不會抽出解不開的 serviceHint | `core/agent_core/registry.py` | — | `test_agent_guardrails.py`、`test_demo_capabilities.py` |
| 場合展開（只說場合、沒說服務） | 「父親節那個交給你安排」「爸媽要來」「過年前先弄一下」句中沒有服務名詞，登錄表解不開就會停在追問，住戶讀起來像「平台沒有這個服務」。`_OCCASION_BUNDLES` 是確定性對照表，把場合展開成**真的存在的** domain（父親節／母親節→清潔＋餐廳、過年→大掃除＋餐廳、搬家→清潔＋宅配…）。它只決定「提哪幾類服務」，**日期、價格、店家一律不填**；句中已有服務名詞時完全不介入 | `core/agent_core/registry.py::suggest_for_occasion`、`orchestrator.py::_occasion_decomposition` | — | `test_demo_capabilities.py` |
| 對應不到時說得出自己會什麼 | 真的無法解析時，追問句會列出平台現在做得到的服務清單，而不是只說「不確定對應哪一類服務」 | `core/agent_core/orchestrator.py::_capability_menu_clarify` | — | `test_demo_capabilities.py` |
| TimeResolver | 日期片語的確定性解析 | `core/agent_core/time_resolver.py` | — | `test_agent_m8.py` |
| ExecutionGrant | 產生交易前的有範圍授權（服務商、時間範圍、預算／點數上限、到期時間）；送單前必須 consume 涵蓋該交易的已核准 Grant，超範圍或過期就擋下（ADR-0008） | `core/agent_core/grants.py` | `GET /agent/grants/{id}` | `test_agent_guardrails.py`、`test_agent_m8.py` |
| ConversationSession | create／list／get／rename／archive／restore、metadata、pending grant、active task package、OCC、workspace／account 隔離；**封存保留資料，不宣稱永久刪除**；持久化於 SQLite 而非行程記憶體 | `core/agent_core/sessions.py` | `/agent/sessions*`、`/agent/sessions/latest` | `test_session_store.py`、`web/app/tests/agentSessions.spec.ts` |
| 工具註冊表 | 一份定義雙重曝露（規劃器＋MCP）；**身分不由模型決定**（來自 `ToolContext`，工具參數不收身分）；參數先驗證再執行 | `core/tools/registry.py`、`catalog.py` | `GET /api/v1/assistant/tools` | `test_tool_registry.py`、`test_tool_catalog.py` |
| 規劃與執行 | 計畫產生與執行分離 | `agent/planner.py`、`agent/intent_agent.py` | `POST /api/v1/assistant/plan`、`/plan/execute`、`/api/v1/intent/match` | `test_planner.py`、`test_intent_agent.py`、`test_assistant_api.py` |

### G. LLM Wiki（隔離知識庫）

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 兩個隔離知識域 | 生活指南與產品 FAQ 完全隔離；依 domain、locale、region、app version 選文；引用與 action allowlist；**無證據時明確回答「沒有依據」，不會誤配第一篇文章**；Wiki body 只是資料，不能變成工具 action | `core/wiki/service.py` | Agent 回合內引用 | `test_v4_wiki.py` |
| 已發布語料 | `docs/knowledge/product-help/` 加上內部編寫的 `life-guides/zhongyuan-preparation.md`；都只描述已核對或明確標示的 Demo 能力 | `docs/knowledge/` | — | `test_v4_wiki.py` |
| 能力條目（AI 知道自己會什麼） | `product-help.ai-capabilities` 列出 Service Registry 的 11 個 domain、住戶常見說法、服務以外的能力,以及「只說場合沒說服務」的展開規則；同一份字彙也注入需求理解器的 bounded context | `docs/knowledge/product-help/ai-capabilities.md`、`core/agent_core/orchestrator.py::_service_vocabulary` | Agent 回合內引用 | `test_demo_capabilities.py` |
| 中文檢索 | 查詢先切成詞與 CJK 2–4 字滑動視窗再依命中數排序;中文沒有空白,舊的整句比對幾乎命中不了任何條目 | `core/wiki/service.py::_query_terms` | — | `test_v4_wiki.py`、`test_demo_capabilities.py` |
| 正式資料邊界 | 中元文章是 `published` 的內部 Demo 內容，不是官方／授權建議；颱風、搬家與正式指南仍待外部來源與人工審核 | 同上 | — | `test_v4_wiki.py` |

### H. 生活圈（Reachability）

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 時間可達範圍 | ReachabilityProvider 介面、固定 GeoJSON schema、步行／機車兩種模式、10／15 分鐘限制、篩選 Catalog Location | `core/reachability/service.py` | `GET /reachability/area` | `test_v4_reachability.py` |
| Provider 服務範圍 | 到府服務範圍是獨立決策，**絕不退化成「離會員多遠」的距離推算** | 同上 | `GET /provider-service-areas/{provider_id}` | 同上 |
| 隱私 | 前端單次定位、不保存 | `web/app/src/views/ReachabilityView.vue` | — | `web/app/tests/reachability.spec.ts` |
| 誠實邊界 | `data/reachability/demo.geojson` 提供四種固定 Demo 示意範圍，明確標示 approximation、非即時、非導航；不冒充官方最近距離 | `data/reachability/README.md` | — | `test_v4_reachability.py` |

### I. 主動關懷

刻意分成三個狀態：**白名單情境事件存在 → 產生確定性候選 → 送達可操作的會員訊息**。這裡不做背景定位、不刮行事曆、不發推播、無任何外部副作用。

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 候選 → 送達 | candidate 與 message 分離；讀取訊息不產生副作用 | `core/proactive_care/service.py` | `GET /care/messages` | `test_v4_care.py` |
| 送達政策 | quiet／balanced／caring 三檔、類別覆寫、頻率上限、安靜時段、交易通知獨立計數、資料來源白名單；在 delivery 前套用 | `core/proactive_care/policy.py`、`docs/architecture/v4-care-delivery-policy.md` | — | `test_v4_care_policy.py` |
| 會員操作 | 顯示原因／來源／使用了哪些資料；ignore／snooze／close／開啟指南 | `core/proactive_care/service.py` | `POST /care/messages/{id}/actions` | `test_v4_care.py` |
| 指南與商務邊界 | 開啟後顯示內部 Demo 指南、分類與 Demo 點數估算；「幫我準備」只整理清單，不建立訂單 | 同上 | — | 同上 |

### J. 任務包（LifeTaskPackage）

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 可編輯任務包 | source／beneficiary／ServiceLocation／TaskDraft refs；逐項修改／暫緩／移除；Provider 與時段變更**只接受目錄已提供的確定性選項**，所以 LLM 或任意 client 無法覆寫權威價格／廠商 | `core/task_packages/service.py` | `GET /agent/task-packages`、`PATCH .../items/{item_id}` | `test_v4_task_packages.py` |
| 執行 | OCC、一次有界授權（bounded grant）、跨 Provider 逐項執行、partial failure、event-key 冪等；執行時以最新任務包項目同步共用 TaskDraft 再 submit | 同上 | 同上 | `test_v4_task_packages.py`、`test_agent_m8.py` |
| 邊界 | 任務包本身**永遠不會直接建立 booking 或 order** | 同上 | — | 同上 |

### K. 生活成果、成就與商業投影

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| LifeOutcome | completed／delivered 只計一次的成果；一次性 Achievement | `core/outcomes/service.py` | `GET /outcomes` | `test_v4_outcomes.py` |
| Demo 回饋 | reward budget／cap／dedupe／reversal；全額 operator refund 會產生 `refunded` reversal projection | 同上 | 同上 | 同上 |
| Provider 結算 | Provider fee 與平台結算；**會員端投影刻意不含 provider fee**，費用表只在結算投影曝光 | 同上 | `GET /provider/settlement` | `test_v4_outcomes.py`、`test_platform_core_api.py` |

### L. 洞察與個人化（全部由官方訂單算出）

**這一區沒有任何硬編碼數字**——儀表板上的每個數字都從官方 `mms_order_record` 計算。

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 官方資料讀取 | 處理原始檔「多個 top-level JSON 物件串接」的怪癖（`json.load` 會噴 `Extra data`）；normalize 99 筆 `mms_order_record`／10 個帳號；官方 `service_id` → 9 項服務目錄 | `core/data/official_source.py`、`official_orders.py` | — | `test_insights.py` |
| 行為指紋（身分解析） | 用官方 `member_*_hash` 把 10 個通路帳號真實合併成 8 個身分（hash 確實跨帳號重複，這是真的、不是編的） | `core/data/identity.py` | `GET /api/v1/insights/accounts` | `test_identity.py` |
| Demo 家庭 | 小圓／陳伯伯／Vivian 三個家庭是**明確標示 `source: demo_composition` 的組合**，絕不當成推論結果呈現 | `core/data/personas.py` | — | `test_identity.py` |
| 主展示住戶王小明 | 走同一條 `orders_for()` → `accounts_for_persona()` 展開，對到 4 個官方帳號（30 筆訂單、6 種服務）；**訂單與小圓／陳伯伯重疊**，所以 summary 一定附帶 `composition` 區塊寫明 `demo_composition` 與重用說明。`PERSONAS` 仍維持 3 個（它是 10 個官方帳號的分割），需要涵蓋王小明的種子改用 `DEMO_HOUSEHOLDS` | `core/data/personas.py`、`core/insights/behavior.py` | `/api/v1/insights/{id}/summary` | `test_wang_demo_data.py`、`test_identity.py` |
| 行為軌跡與消費摘要 | 時間序事件與消費統計（注意：行為指紋 ≠ 行為軌跡） | `core/insights/behavior.py` | `/api/v1/insights/{id}/summary`、`/trail` | `test_insights_api.py` |
| 可解釋推薦 | 確定性規則決定「推什麼、為什麼」，附 `evidence` 指向真實 `record_id`；**LLM 不參與**。回訪規則刻意排除事件驅動服務（修繕／餐廳／寄件）——「該再修一次水管了」是廢話 | `core/insights/recommendations.py` | `/api/v1/insights/{id}/recommendations` | `test_insights_api.py` |
| 今日摘要 | 由真實待辦算出、不是 LLM 生成；排序依據是「誰在等誰」（卡在使用者身上的最優先） | `core/insights/today.py` | `GET /api/v1/today/{account_id}` | `test_today_briefing.py` |
| 個人化 | 可撤回的回饋、補貨建議、提醒（ADR-0012 明確同意與最小保存） | `core/personalization/service.py` | `/api/v1/personalization/{id}/*` | `test_insights_api.py` |
| 超商生態 | 門市查詢與缺貨候補；即時門市 API 尚未取得，庫存資料帶 `competition_seed`，但候補狀態寫入平台自己的 SQLite（非前端假資料） | `core/retail/service.py` | `/api/v1/retail/stores/search`、`/retail/stock-watches` | `test_retail_connector.py` |

### M. 社區功能

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 社區團購 | 住戶或管委會發起 → 社區住戶跟團 → 管理者到期結單；`open` → `closed`（產出給廠商的彙總）→ `fulfilled`。同一檔活動住戶與管委會看到不同視角，**資料只有一份**（ADR-0003） | `core/community/group_buy.py` | `/api/v1/community/campaigns*` | `test_group_buy.py` |
| 社區聯合服務 | 匿名需求、方案決策與廠商履約放在同一筆可稽核資料；種子帶 `competition_seed` 來源標記 | `core/community/joint_service.py` | `/api/v1/community/joint-services*`、`/api/v1/vendor/joint-services*` | `test_joint_service.py` |
| 社區公告 | 公告發布與閱讀 | `core/communities/` | `/platform/communities/{id}/announcements` | `test_communities.py` |
| 社區方案身分（免費／訂閱） | 商業模式是**社區訂閱**，不是個人付費。免費社區只開放團購（瀏覽、跟團、開團），其餘住戶功能霧面顯示；訂閱社區解鎖全部。身分放在 Identity 的 `communityMembership`；沒帶這欄的身分（含舊 localStorage）由 `demoCommunityMembership()` 依帳號推導，展示上**王小明的社區已訂閱、陳伯伯的社區還沒**，兩種狀態都看得到。姓名旁顯示 VIP／免費徽章 | `web/app/src/stores/session.ts`、`views/SubscriptionView.vue` | 前端狀態（後端未建模） | `web/app/tests/subscriptionAndTicker.spec.ts` |
| 付費功能的霧面遮罩 | `subscriberOnly` 路由**不導走**免費住戶——內容照常渲染，再由 `SubscriptionLock` 蓋上霧面與解鎖卡片，住戶才看得到訂閱換到什麼。關鍵是模糊只是視覺：被鎖的內容一律 `inert` + `aria-hidden`，鍵盤與螢幕閱讀器都進不去，否則就是「看得到、唸得出、Tab 進得去」的假鎖，還會踩到 WCAG 2.4.11。`prefers-reduced-motion` 與 `prefers-contrast: more` 下改用低透明度而非模糊。**區塊級的閘門用同一個元件**：首頁的主動關懷卡、近期行程、生活圈、AI 管家與個人化建議都是同一份內容加 `:locked`，不是「訂閱版＋免費替代卡」兩份會漂移的 markup；住戶社區頁也把訂閱後的實際畫面霧面放出來，取代原本的「🔒 功能條列」 | `web/app/src/components/SubscriptionLock.vue`、`App.vue`、`views/TodayView.vue`、`views/CommunityHubView.vue`、`router/index.ts` | — | `web/app/tests/subscriptionAndTicker.spec.ts` |
| 社區快訊跑馬燈 | 首頁與住戶社區頁的橫向跑馬燈，公告與熱銷團購交錯輪播；有暫停／播放按鈕（`aria-pressed`），並在 `prefers-reduced-motion` 下停止動畫。**團購推播由 `GROUP_BUY_CATALOG` 算出**（取成團進度最高的兩檔、算出還差幾件），不是另寫一份文案，所以不會跟商品頁的價格與進度漂移 | `web/app/src/components/CommunityTicker.vue` | 前端 Demo 內容 | `web/app/tests/subscriptionAndTicker.spec.ts` |

### N. 客服與訂單異常

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 問題診斷 | 訂單所有權驗證、問題診斷與工單規則的單一來源 | `core/support/service.py` | `POST /api/v1/support/diagnose` | `test_support_workflow.py` |
| 工單 | 建立、佇列、開始處理、結案 | `core/support/repository.py` | `/api/v1/support/tickets*`、`/support/queue` | `test_support_workflow.py` |

### O. 平台營運與 Demo 控制

| 功能 | 做到什麼 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| 協調 reset | 平台、points、交易、通知、Calendar、TaskDraft、Agent session 與 Partner fake **同步**回到相容 seed；reset 後重新同步目錄投影，seed version 一致 | `core/demo_reset.py` | `POST /api/v1/platform/demo/reset` | `test_demo_reset.py` |
| 工作區 reset | 單一 membership 的重置 | 同上 | `POST /platform/admin/workspaces/{id}/reset` | `test_demo_reset.py` |
| 上游健康與故障注入 | 目錄健康表、重新同步（partial 誠實顯示）、可注入 delay／503／timeout／malformed | `api/app.py`、`fake_upstreams/` | `/platform/admin/upstream-health`、`/upstream-faults` | `test_fake_upstream_server.py` |

### P. 相容層與較早的垂直切片（仍在跑、仍有測試）

這些是早期里程碑留下的路徑。**保留回歸價值，但不算現行閉環的證據**——判斷現行能力時以 A–O 為準。

| 功能 | 狀態 | 程式碼 | 端點 | 測試 |
| --- | --- | --- | --- | --- |
| LifeTask 編排 | 舊的跨服務目標編排；走 legacy vendor fake（:8021） | `core/life_tasks/` | `/api/v1/life-tasks*` | `test_life_task_flow.py` |
| Legacy vendor-api | 舊契約（`contracts/legacy/`） | `core/vendors/` | `/api/v1/vendor-api/*` | `test_vendor_client.py`、`test_fake_vendor_server.py` |
| MCP stdio proxy | 相容代理，已只走 Platform API；**不是** mcp==2.0.0 Streamable HTTP Gateway | `mcp_server/server.py` | stdio | `test_mcp_server.py` |
| AWS 部署腳本 | CloudFormation 與部署腳本存在，屬探索性；正式部署未完成 | `infra/` | — | — |

> `core/life_butler/` 目前是**空目錄**（沒有任何 `.py`）——別去那裡找主動生活管家的程式碼，它散在 F／G／H／I／J／K 幾區。

---

## 3. 前端頁面地圖

| Route | View | 主要功能 | 測試 |
| --- | --- | --- | --- |
| `/` | `HomePublicView` | 公開首頁：產品價值、六場景、右上登入（spec 15 §9.1） | `loginAndAccess.spec.ts` |
| `/login` | `LoginView` | 帳密登入卡＋8 家合作方品牌（與 access seed 一致） | `loginAndAccess.spec.ts` |
| `/user` | `TodayView` | 住戶首頁：今日摘要、近期行程卡、未讀通知 | `todayInsights.spec.ts` |
| `/user/services/:slug?` | `ServicesView` | 服務探索，六場景分組（食／醫／住／行／預／樂），真實品牌 icon | `servicesExplore.spec.ts` |
| `/user/services/provider/:id` | `ProviderDetailView` | 廠商詳情 | `providerDetail.spec.ts` |
| `/user/booking` | `BookingWizardView` | 預約精靈：TaskDraft 驅動、每步 OCC、409 誠實重載、`?draft=` 續填、據點→方案→真實時段→domain 欄位→試算→submit→付款 | `bookingWizard.spec.ts` |
| `/user/orders`、`/user/orders/:id` | `OrdersView`、`OrderDetailView` | 訂單列表與詳情：per-domain 狀態名稱、StatusEvent 時間軸、取消、改期、重付、providerSync 警示 | `orderDetail.spec.ts`、`residentOrderFlow.spec.ts` |
| `/user/assistant` | `AssistantView` | 獨立 AI 頁：ToolResult 狀態、facts、稽核參照、Wiki 引用與更新日、Session 歷史 | `assistantConversation.spec.ts`、`assistantPlanning.spec.ts`、`agentSessions.spec.ts` |
| `/user/calendar` | `CalendarView` | 行事曆（由首頁卡片進入，不佔主導覽）：月／列表切換、日期分組、來源篩選 | `calendarView.spec.ts` |
| `/user/points` | `PointsView` | 點數帳本（與首頁讀同一份 ledger） | `pointsView.spec.ts` |
| `/user/member` | `MemberView` | 會員中心 | `memberCenter.spec.ts` |
| `/user/subscription` | `SubscriptionView` | 住戶端社區方案：免費／訂閱兩張方案卡、功能比較表、Demo 模擬啟用 VIP。**未訂閱者存取 `subscriberOnly` 路由時會被導向這裡**；完整六級距以真正的 `<table>` 呈現，社區月費一律由 `planForHouseholds(householdCount)` 對照 `SUBSCRIPTION_TIERS`（日光森林 28 戶 → NT$999），導入期優惠是免費試用 3–6 個月而不是第二個價格；與管委會端 `/demo/subscription` 讀同一份 `COMMUNITY_DEMO_SEED.subscription` | `subscriptionAndTicker.spec.ts` |
| `/user/community` | `CommunityHubView` | 住戶端社區入口：訂閱社區看完整看板；免費社區看到訂閱說明＋可用的團購區塊（`CommunityBoardView` 的 `groupBuyOnly` 模式收起公告／群組／共同需求，但保留跟團），再把訂閱後的社區首頁整個霧面（`SubscriptionLock` + `DemoResidentView`）放在下方，讓住戶直接看到訂閱換到什麼 | `communityAnnouncements.spec.ts`、`communityGroupBuy.spec.ts`、`subscriptionAndTicker.spec.ts` |
| `/user/community/group-buys` | `GroupBuyCatalogView` | 團購商品目錄：真實統一企業商品名稱、規格與原商品頁連結；商品照是**零售通路（momo／全聯線上）拍的商品照片**，一次下載後放在 `web/app/public/group-buy/` 由本站提供（執行時不連外部 CDN），逐張出處記在同資料夾的 `README.md`，**不是統一企業授權的官方素材**，載入失敗時退回自繪 SVG；價格、庫存、到貨日與成團進度是 Demo 資料 | `groupBuyCatalog.spec.ts` |
| `/user/life-circle` | `ReachabilityView` | 生活圈：步行／機車切換、單次定位不保存 | `reachability.spec.ts` |
| `/user/wellbeing` | `WellbeingView` | 生活成果、成就、關懷卡、Demo 回饋 | `wellbeing.spec.ts` |
| `/community` | `CommunityView` | 管委會工作台 | `communityAnnouncements.spec.ts` |
| `/partner` | `VendorView` | 廠商工作台：平台案件分頁、合法轉移按鈕（不合法不渲染）、409 重載、aria-live、結算 | `vendorPlatformBookings.spec.ts` |
| `/platform` | `PlatformView` | 平台管理台：目錄健康表、重新同步、demo reset 確認（不在登入選項與主導覽） | `platformAdmin.spec.ts` |
| `/demo/*` | `Demo*View` | Demo-first 社區團購走查頁，與既有串接頁隔離，方便簡報重複操作 | `communityDemoFlow.spec.ts`、`demoStore.spec.ts` |

**共用元件**：`AgentConversation`、`AgentDrawer`、`AgentSessionHistory`（獨立 AI 頁與側欄共享同一段對話與草稿）、`CommunityTicker`（首頁／社區頁的社區快訊跑馬燈）、`ServiceIntakeForm`、`LifeTaskCard`、`SupportIssuePanel`、`ConfirmDialog`、`StepIndicator`、`AppIcon`、`DemoRoleSwitcher`。

**「後端沒啟動」是一句很貴的話**：使用者看到就會去重開一個其實正在跑的 API，真正的原因反而被蓋掉——住戶 王小明 的公告 403（他當時不是社區成員）就是這樣被讀成「存取不到後端」的。因此 `web/app/src/api/http.ts` 匯出 `backendAnswered(reason)`（有 HTTP 狀態碼＝後端有回應；連線失敗會被正規化成 `status 0`），前端必須把三件事分開講：**成功但空**、**後端回了錯誤／拒絕**、**真的連不上**，只有最後一種可以叫使用者去確認服務是否啟動。由 `tests/backendUnavailableHonesty.spec.ts` 守住。

**前端鐵律**：前端**不持有**任何服務或表單定義——目錄、表單定義、報價全部來自後端；`domain/serviceIntake.ts` 只保留型別與即時回饋用的鏡像驗證器。測試 fixture 由後端產生（`uv run python tools/dump_catalog_fixture.py`），所以不會偷偷漂移。WCAG 2.2 AA 由 `tests/accessibilityBaseline.spec.ts` 強制。

---

## 4. 資料真實性分級（**看功能時最容易誤判的一節**）

這個 repo 對「什麼是真的」有一套明確的標記紀律。看到下列標記時請照字面理解：

| 分級 | 意思 | 例子 |
| --- | --- | --- |
| **官方資料** | 來自 `raw_data/` 的官方 DDL 與樣本 JSON，零修改；所有新功能都是外掛擴充表 | `mms_order_record`（99 筆／10 帳號）、`pms_form*` schema、`member_*_hash` |
| **真實推導** | 由官方資料實際算出 | 行為指紋合併出的 8 個身分、行為軌跡、消費摘要、可解釋推薦的 `evidence` |
| `demo_composition` | **明確標示的人為組合**，不可當成推論結果呈現 | 小圓／陳伯伯／Vivian 三個 Demo 家庭 |
| `competition_seed` | 競賽建置資料，非品牌正式報價或即時 API | 聯合服務方案、超商庫存資料、點數／優惠券帳本 |
| `placeholder: true` | 可替換的佔位 Provider | 「樂」場景的 Provider |
| `draft` / `not_published` | 內容未取得授權來源或未經人工審核，**系統會誠實擋下** | 尚未發布的颱風／搬家指南與正式生活資料 |
| `demo-only` | 競賽固定示意資料，只能用來展示互動，必須同時標示限制 | 中元內部 Demo 指南、`data/reachability/demo.geojson` |
| **真實品牌／通路商品照** | 商品名稱、品牌與規格是真的（附原商品頁連結可查），商品照是零售通路自己拍的商品照片、下載後在本機提供並逐張標註出處，**不是品牌授權的官方素材**（備援才是自繪 SVG）；價格與庫存仍是 Demo | 團購目錄的統一企業商品、`web/app/public/group-buy/*.jpg` 與其 `README.md`（備援 `*.svg`） |

品牌名單來自產品負責人 2026-07-30 提供的正式名單（`廠商and表單.md`）；`partner-demo-v5` seed 有 7 個 Provider（住×2／食 21PLUS／行 速邁樂＋黑貓／醫 康是美／預 7-ELEVEN／樂 統一渡假村）。

---

## 5. 明確「還沒有」的功能

避免下一個 session 去找不存在的東西。詳細原因見[現況與差距](status/2026-07-30-current-state-and-gap.md)。

- **取消收費規則**：目前一律全額退款；`cancelPolicyHours` 只記錄在目錄，費率待產品負責人確認。
- **Adapter 接入的建單 payload 相容性**：未修（六場景都走 standard 或 workbench）。
- **改期申請查詢端點**：沒有；送出後只顯示等待回覆。
- **醫療 OCR**：處方箋照片上傳與辨識未實作，欄位以人工確認 checkbox 代表。
- **行・叫車**：ibon 叫車是機台流程，未線上化。
- **語音輸入**：未做。
- **LINE／LIFF／Discord**：延後（ADR-0014 決定 Web 深層連結優先）。
- **正式生活指南內容**：官方／授權來源、商業使用權與地域審核尚未取得；目前只有內部 Demo 指南。
- **會場官方精確座標與外部人工檢查過的 GeoJSON**：尚未取得；目前固定檔案只作 Demo approximation，Amazon Location adapter 未接。
- **正式 AWS 部署**：`infra/` 只是探索性腳本，production verification／secrets 未具備。
- **MCP Streamable HTTP Gateway（mcp==2.0.0）**：現有只是 stdio 相容代理。
- **系統化 browser E2E 與全站 WCAG 深度稽核**（含鍵盤逐頁走查）：屬 M10，未完成。元件測試與 production build 不替代人工 gate。
- **Demo 錄影備援**：驅動腳本已可用（`web/app/tools/demo-drive.mjs`，九幕、可單幕重錄、輸出配音分軌表，見 [錄製文件](testing/demo-video-recording.md)），且已實跑通過；**但影片本身尚未錄製、旁白尚未配音**。腳本只涵蓋 `/demo/*` 前端 Demo 主線，不含 `/user/*` 的真後端與真 LLM 走查。
- **Session 永久刪除與 retention policy**：需要產品／法務決策。
- **訂閱的後端建模與計費**：社區方案身分目前**只存在於前端 Identity**（`communityMembership`），沒有訂閱資料表、沒有計費、沒有伺服器端授權檢查。訂閱頁的「模擬啟用 VIP」只改前端狀態；方案價格是商業模型示意，不是報價。

---

## 6. 驗證入口

```bash
# 後端全部測試（注意：單次全庫執行曾在 300 秒 timeout，必要時分批跑）
uv run pytest

# 單檔／單測
uv run pytest tests/test_form_engine.py
uv run pytest tests/test_form_engine.py::test_skip_ac_type_when_not_choosing_ac

# v4 受影響組合（39 tests）
uv run pytest -q tests/test_agent_m8.py tests/test_agent_v4_contracts.py \
  tests/test_v4_task_packages.py tests/test_v4_care.py tests/test_v4_care_policy.py \
  tests/test_v4_wiki.py tests/test_v4_outcomes.py tests/test_platform_core_api.py

# 王小明 Demo 憑證與 AI 能力邊界（場合展開、能力選單、服務字彙）
uv run pytest -q tests/test_wang_demo_credential.py tests/test_demo_capabilities.py

# 前端（於 web/app）
npm test -- --run
npm run typecheck
npm run build

# 目錄／報價／洞察改動後，重新產生前端 fixture（避免前後端悄悄漂移）
uv run python tools/dump_catalog_fixture.py
```

`pytest` 是後端唯一的 gate（沒有設定 linter 或 type checker）。

---

## 7. 新 session 的建議讀取順序

1. 本文件（知道有什麼）
2. [CLAUDE.md](../CLAUDE.md)（架構鐵律與指令）
3. [CONTEXT.md](../CONTEXT.md)（詞彙，特別是「行為指紋 ≠ 行為軌跡」這類易混淆項）
4. 要動的那一區 → 表格裡的程式碼路徑與測試檔
5. 要改行為 → 對應的 [spec 15／16／17](README.md) 與 ADR
