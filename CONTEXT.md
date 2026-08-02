# AIWave 領域詞彙

> 更新日期：2026-08-01。此文件定義產品、Web、後端、Agent、MCP、廠商 API 與簡報共同使用的語言。完整決策以 [產品與平台定案基線](docs/specs/15-agreed-product-and-platform-direction.md) 為準。

## 產品與任務

**AIWave**：以個人會員為主體的生活服務作業系統。整合生活服務、點數、行程、通知、群組與社區情境，讓使用者以手動或 Agent 完成可追蹤的生活任務。
_Avoid_：第二個 OPENPOINT、純聊天機器人、服務型錄、社區管理 App、只有畫面的 mock demo。

**生活目標（LifeGoal）**：會員用自然語言描述想完成的結果，例如「爸媽週六要來，幫我把家裡整理好」。

**生活任務（LifeTask）**：由生活目標拆出的可執行工作單元，含相依順序、輸入、工具、確認層級與狀態。
_Avoid_：沒有履約能力的待辦文字、聊天回覆。

**TaskDraft**：手動 UI 與 Agent 共用的進行中草稿。保存對話取得的欄位、使用者修改、驗證結果、候選方案與尚未確認的操作；切換操作方式不得遺失。

**TaskPlan**：Agent 對 LifeGoal 產生的結構化步驟集合。通過 capability、schema、權限與規則檢查後，才可預覽或執行。

**Capability Registry**：Web、Agent 與 MCP 共用的能力清單，記錄參數、權限、風險、確認規則、冪等要求與可用性。

## 主動生活管家

**受益人（Beneficiary）**：生活任務希望照顧或協助的對象，例如會員的父母。受益人可以沒有 AIWave 帳號，也不因此取得操作權；付款與 `ExecutionGrant` 仍由會員本人核准。
_Avoid_：把受益人當成共同帳號持有人或推定其已同意分享資料。

**服務地點（ServiceLocation）**：生活任務實際履約的會員保存地址，例如「我家」或「爸媽家」。同一會員可保存多個服務地點；它不同於 Provider 的門市／據點 `Location`。

**時間可達生活圈（Time-based Reachability Area）**：以會員目前位置、服務地點或社區地址為起點，依步行／騎車等交通方式與 N 分鐘門檻計算的可達範圍，以及範圍內需要會員前往的生活服務。它不是固定行政區、直線半徑、住家與公司的單一路線，也不取代到府服務範圍。
_Avoid_：未經路網或明確 Demo 規則計算就宣稱「10 分鐘可達」「最近」或提供導航；以 Provider 據點離會員近就推定其提供到府服務。

**到府服務範圍（Provider Service Area）**：Provider 明確承諾可到達會員服務地點的縣市、行政區或其他覆蓋規則，適用於清潔、修繕、外送與宅配等由 Provider 前往的服務；與會員前往門市的時間可達生活圈分開判斷。

**生活情境事件（LifeContextEvent）**：由公共日曆、會員明確授權資料或清楚標示的 Demo 注入資料形成的客觀生活事實，例如母親節、會員行事曆事項或指定行政區的天氣情境。

**關懷候選（CareCandidate）**：系統根據生活情境事件判斷可能值得提醒的機會；尚未通過提醒政策，也不代表已向會員顯示或送達。

**關懷訊息（CareMessage）**：關懷候選通過類別、頻率、安靜時段與送達方式等政策後，實際呈現給會員的內容。一般關懷與訂單、付款、預約異動等交易通知分開處理。

**主動關懷偏好（ProactivePreference）**：會員對一般關懷的強度、類別、安靜時段與送達方式選擇。模式只提供預設值，會員仍可逐類覆寫；提高關懷強度不代表授權更多資料或建立情感依附關係。

**成就解鎖提示（Achievement Unlock）**：由可驗證的任務完成事件觸發、僅解鎖一次的愉悅微互動，用來強化完成感與 Demo 記憶點；不等同生活成果、OPENPOINT 回饋或具經濟價值的獎勵。
_Avoid_：擴張成 XP、等級、每日登入、排行榜、角色養成，或把它宣稱為核心產品價值。

**情境式生活指南（Contextual Life Guide）**：針對報稅、租屋、祭拜、就醫、搬家或防災等生活情境，提供有來源、適用範圍與更新日期的步驟及準備清單，並可在會員同意後轉成採買、預約或服務 `TaskDraft`。
_Avoid_：未經授權複製第三方內容、由 LLM 捏造民俗或專業事實，或以焦慮與恐懼促成消費。

**準備項目（PreparationItem）**：情境式生活指南中的通用需求，包含用途、必要／可選狀態、數量依據與適用限制；不是具體商品 SKU。實際商品、價格、庫存、地點與點數條件由 Catalog／Provider 資料決定。

**LLM Wiki**：AIWave 共用的內容整理、審核、發布與問答能力；依查詢目的選擇知識域，並以可追溯來源回答。它不是一個混合所有內容的資料池，也不以模型記憶取代來源。

**生活指南知識庫（Life Guide Knowledge Base）**：保存情境式生活指南、觸發條件、地域、準備項目、來源、授權與商業使用狀態的知識域；可在會員同意後連結採買與生活服務。

**產品說明知識庫（Product Help Knowledge Base）**：保存 AIWave 已發布功能的操作手冊、FAQ、限制、版本與導覽入口的知識域；只協助使用產品，不觸發生活消費推薦。
_Avoid_：將生活指南與產品說明混合檢索，或在取消、退款、權限等求助回答中插入促銷。

**協助式商務（Assistive Commerce）**：先以有用且可關閉的生活提醒或指南協助會員；只有會員主動開啟並要求準備後，才呈現必要、可選與明確標示的合作推薦，並經確認轉成採買或服務任務。
_Avoid_：在推播中直接製造焦慮、把可選商品說成必要，或未經同意建立購物車與訂單。

## 帳號、角色、工作空間與範圍

**Account**：登入身分，不等同單一角色或單一人物資料集合。

**RoleMembership**：Account 在指定 Workspace 中擁有的角色、權限與狀態。單一 Account 可同時具有會員、合作方人員、社區管理者與平台營運者資格。

**Workspace**：使用者目前代表哪個個人、廠商、社區或平台空間操作的明確上下文。資料查詢和寫入都必須帶入，不可從過去登入行為猜測。

**會員（Member）**：產品主要使用者及官方消費者端。會員不一定住在已接入的社區。

**合作方人員（PartnerStaff）**：代表合作服務提供者維護方案、時段、接單及履約狀態的人員。

**社區管理者（CommunityManager）**：經人工核准管理特定 Community 公告、設施、成員與社區服務的人員。

**平台營運者（PlatformOperator）**：管理合作方接入、契約、稽核、Demo workspace 與系統異常的人員。

**Scope**：資料或操作的歸屬，現行值為 `personal`、`group`、`community`。

**Group**：會員自行建立、命名及邀請成員的共享集合。系統不要求 family／friend／couple 等類型。
_Avoid_：把 Community 當 Group type。

**GroupMembership**：會員在 Group 中的角色、權限、加入狀態與通知偏好。

**Community**：對應真實住宅社區或組織，具有住戶、管理權、公告、設施與社區服務。會員可加入多個 Community 並設定預設值。

**CommunityMembership**：會員在 Community 中的住戶／管理關係與核准狀態；與 GroupMembership 分開建模。

## Agent、授權與互動

**Agent**：AIWave 的自然語言操作與任務規劃層。能理解需求、選工具、比較、預填、重新規劃及在授權內執行；不是另一套後端，也不直接存取 DB。
_Avoid_：FAQ、只會說話的 LLM、無限制全自動代理、Agent swarm。

**自然對話層（Conversational Layer）**：由 LLM 根據目前對話、任務狀態、可用能力與知識內容，自然回答、承接省略語句、釐清及提出下一步；不以固定問句或單句關鍵詞表取代語意理解。

**確定性行動層（Deterministic Action Layer）**：驗證並執行自然對話層提出的結構化動作，負責能力存在性、日期、Provider、方案、庫存、時段、價格、點數、權限、授權、狀態轉移與冪等。LLM 可解釋這些結果，但不可取代裁決。

**對話 Session（ConversationSession）**：會員與 Agent 針對一段目標或討論建立的獨立對話上下文，可建立、重新開啟、重新命名及封存。開始新 Session 不帶入舊對話，也不刪除舊 Session 已建立的 TaskDraft、Booking、Order 或行事曆事件。

**對話目的（TurnIntent）**：會員在單一對話回合想進行的互動，包括一般對話、產品求助、生活詢問、探索方案、規劃任務、執行操作及暫停／取消。只有需要外部影響的目的才進入行動與授權流程。
_Avoid_：把每句自由文字都強制解讀為下單意圖，或在會員只想了解、比較、修改及反悔時持續推進交易。

**Role-scoped Agent**：同一 Agent runtime 依 Account、RoleMembership、Workspace 與 API scopes 取得不同能力；不是每個角色各訓練一個模型。

**ExecutionGrant**：使用者對一組外部影響操作核准的有界授權，至少包含提供者、時間範圍、預算／點數上限與到期時間。條件超界或改變時必須再次確認。

**直接操作**：低風險讀取、搜尋與導覽。完成後仍須讓使用者看見結果。

**草稿／預覽**：Agent 可建立或修改 TaskDraft，但尚未造成交易、共享或履約影響。

**受控執行**：Agent 在有效 ExecutionGrant 內執行一個或多個步驟；不是逐工具機械確認，也不是永久授權。

**執行進度**：顯示正在查詢的能力、可驗證階段、依據與結果。
_Avoid_：原始 chain-of-thought、hidden prompt、憑證或不必要個資。

**TimeResolver**：以 `Asia/Taipei` 目前時間確定性解析「明天」「下週三」等相對日期，並回顯絕對日期。

**Service Registry**：服務、同義詞、提供方式、必要欄位及 capability 的權威清單。遇到模糊需求先釐清，不把未知用語直接判為沒有服務。

## 服務、提供者與履約

**生活場景**：官方以食、醫、住、行、預、樂描述的可擴充分類；不是固定只能六種。

**官方服務來源**：官方資料中的服務分類或整合來源，不等同實際履約公司。

**合作服務提供者（Provider／Partner）**：經平台核准、實際提供商品、時段、報價或履約的組織。
_Avoid_：把所有 Provider 都稱為自動媒合結果。

**Location**：Provider 的可選門市、據點或服務單位。

**Offering**：Provider 在指定 Location 提供的具體服務或商品，包含價格、限制與預約規則。

**Resource**：履約所需的可選人員或資源，例如設計師、車種、房型；是否需要由服務類型決定。

**AvailabilitySlot**：由 Provider 提供且仍可預約的實際空檔。使用者從空檔選擇，而非任填一個 Provider 未承諾的日期。

**服務推薦**：根據地點、時段、預算、限制與偏好排序 1–3 個 Provider／Offering 並說明理由；使用者保有最終選擇權。

**彈性留資表單／諮詢單**：官方命題中的 lead-capture flow。正式送出時必須包含該服務履約所需的聯絡、地點、時間／可配合條件及服務欄位，不能只有分類答案。

**題組引擎**：讀取表單 schema、套用已知會員資料、處理跳題與驗證，並可由 Agent 選項或完整表單操作的共用能力。

**Booking／Order**：使用者確認後產生的預約或訂單。不同 domain 可有不同欄位與狀態，不以單一 nullable 萬用表取代領域模型。

**StatusEvent**：接單、確認、備貨、排程、到場、完成、取消與異常等不可混淆的履約事件。首頁、訂單、合作方工作台、通知與行事曆讀取同一來源。

**進度時間軸**：像電商訂單的階段呈現，但標籤由服務 domain 定義並由 StatusEvent 驅動。

**DomainType**：Offering 所屬的服務領域（如 `home_repair`、`dining_reservation`、`ec_preorder`），定義於 `core/catalog/domains.py`；決定 TaskDraft 必填欄位、走 Booking 或 CommerceOrder，以及對使用者顯示的狀態名稱。

**目錄投影（Catalog projection）**：平台保存的 Provider／Location／Offering／Resource／Slot 副本（`core/catalog/`），由 `CatalogSyncService` 從各 ProviderConnector 同步；探索頁讀投影、下單前仍以 connector 現場驗證。Provider 仍是目錄的權威來源。
_Avoid_：把投影當成第二份權威資料或前端 fixture。

## 合作方接入與 fake upstream

**Partner API**：AIWave 對合作方公開的 OpenAPI 3.0 契約，涵蓋 catalog／availability 同步、booking 接收與更新、snapshot 查詢及選配 webhook。

**ProviderConnector**：平台 domain 存取 Provider 能力的深層介面；標準接入、既有 API Adapter 與工作台接入共用它。

**標準接入**：Provider 直接實作 AIWave Partner API。

**Adapter 接入**：AIWave 將 Provider 的既有 API 映射到 ProviderConnector。

**工作台接入**：沒有 API 的 Provider 透過合作方後台維護同一份 domain workflow。

**Fake upstream server**：獨立執行、實作 Partner API OpenAPI 契約的上游模擬系統，支援 seed、reset、延遲、故障與狀態未知注入。
_Avoid_：前端 fixture、靜態 JSON、平台後端內嵌 mock。

**Seed version**：平台 DemoWorkspace 與 fake upstream 共同確認的資料版本，避免 reset 後保留失效遠端 ID 而產生持續 404。

## MCP

**AIWave MCP Gateway**：規劃於 M9 提供遠端 AI 以 Streamable HTTP 連線的系統操作入口。它把經授權的 Platform API capabilities 暴露為 MCP tools；M0～M3 尚未宣稱完成此 Gateway。
_Avoid_：直接連 DB、每個場景一台 MCP server、只給站內聊天使用。

**MCP principal**：由 bearer key 或未來 OAuth/OIDC 解析出的 Agent 身分、角色、Workspace 與 scopes。

**Demo bearer keys**：競賽用固定憑證。會員含 `aiwave`、`aiwave-chen`、`aiwave-vivian`、`aiwave-new`；合作方含 `aiwave-partner`、`aiwave-partner-duskin`；管理角色含 `aiwave-manager`、`aiwave-admin`。它們只用於隔離的 Demo personas／Workspace，不代表正式資安方案；未來 MCP principal 也會走相同 Platform API 權限邊界。

**Domain task ID**：長時間任務以 AIWave 自有 task／order ID 查詢，不依賴尚未被 SDK 支援的 MCP Tasks extension。

## 點數、支付、推薦與個人化

**Demo points ledger**：可重置、明確標示為 Demo 的 OPENPOINT 情境餘額、異動、沖銷與到期紀錄；所有頁面使用同一來源。

**點數最佳化**：確定性計算點數、優惠券與支付條件，輸出折抵和應付金額；LLM 只做解釋與規劃。

**DemoPaymentAdapter**：不處理真實卡號，但能展示成功、失敗、取消、退款與點數沖銷的支付 adapter。

**行為軌跡**：同一會員跨服務、跨時間排序的事件序列。

**行為特徵檔**：由經同意的行為軌跡可重算得到的頻率、週期、常用服務、時段與偏好。

**任務型推薦**：完成當前目標所需的下一步、候選或替代方案，不提供「不感興趣」，而是讓使用者修改條件。

**個人化推薦**：依會員同意範圍內的特徵與偏好產生的建議；可對單項表示不感興趣並復原。

**推廣型推薦**：付費或合作內容，必須明確標示；單項關閉不得隱藏整個推薦區。

**硬性限制**：過敏、禁忌、權限或使用者明確禁止的內容，必須排除，不能與軟性偏好混用。

## 日曆、通知、測試與邊界

**AIWave Calendar**：Booking、LifeTask、提醒、Group 與 Community 事件的統一 projection；不是完整 iCloud／Google Calendar 替代品。

**通知中心**：由 domain events 產生的持久化站內通知，含已讀狀態、scope、深層連結及安靜時段。

**DemoWorkspace**：每位測試者隔離的 seeded 環境，包含帳號、訂單、點數、Agent 對話、草稿、日曆、通知、Group 與 Community。重置時與 fake upstream 協調。

**OPENPOINT**：統一生態的帳號、點數、優惠、支付與服務資產。AIWave 消費或模擬其情境，不重做完整平台，也不宣稱 Demo 帳本是正式即時資料。

**完成閉環**：具備手動入口、可操作表單、Provider 回應、訂單／預約、履約事件、進度／通知、Agent 與 MCP 等價操作、成功與可恢復失敗路徑的端到端能力。
