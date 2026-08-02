# AIWave v4 五分鐘 Demo Runbook

> 狀態：內部主線可依測試替身重現；完整實站驗收仍受外部／人工 gate 阻擋。本文件不把 blocker 寫成已完成  
> 定案日期：2026-08-01  
> 依據：[v4 規格](../specs/16-proactive-life-butler-and-commercial-loop.md)／[自然 Agent 規格](../specs/17-conversational-agent-session-and-llm-wiki.md)  
> 目標：五分鐘內先證明基礎平台，再證明自然 Agent、主動生活指南與商業閉環

## 1. 成功定義

評審在五分鐘後應能回答：

1. AIWave 不是聊天殼，而是能手動操作、建立訂單並追蹤 Provider 履約的平台。
2. LLM 能自然理解多輪語言、修正與反悔，但價格、時段、點數、權限與交易不由模型猜。
3. 生活情境與可信指南可轉成清單、在地服務及可執行建議。
4. 會員保有逐項修改與最後授權權；Provider 完成後平台才產生收入。

北極星不是聊天數，而是生活任務完成率。

## 1.1 目前可驗收的邊界

repository 內已可重現的主線是：公開首頁／會員總覽 → product-help FAQ → 生活圈限制與誠實 fallback → 手動 TaskDraft／試算／交易 → 通知／行事曆 → 新 Agent Session → 任務包逐項修改 → bounded ExecutionGrant → Provider／會員狀態 → Demo event 關懷卡 → LifeOutcome／Achievement／Demo reward／Provider settlement。固定 API、前端 fixture 與測試入口列在 [v4 驗收矩陣](v4-acceptance-matrix.md)。

正式／授權生活指南內容、會場官方座標／外部人工檢查的地理範圍、真實瀏覽器鍵盤走查、完整五分鐘實站彩排，以及正式 Provider／OPENPOINT／AWS 整合，不用 fixture 冒充正式結果。競賽主線可使用明確標示的內部 Demo 指南與固定 GeoJSON；畫面必須同步顯示 Demo、非即時、非導航與「不建立訂單」限制。

## 2. 固定 Demo 資料

| 項目 | 固定值／規則 |
| --- | --- |
| 會員 | 虛構 Demo 會員；不得使用真實個資 |
| 會場起點 | 華南銀行國際會議中心，臺北市信義區松仁路 123 號（固定 Demo 起點；官方精確座標尚待外部／人工確認） |
| 生活圈 | 步行 10 分鐘為主；步行 15 分鐘、機車 10 分鐘可切換 |
| 地理資料 | repository 有四種模式／門檻的固定 Demo GeoJSON；明確標示 approximation、非即時、非導航，不宣稱官方範圍 |
| 手動服務 | 一筆可快速完成的預約，具真方案、Demo 時段與點數折抵 |
| AI 生活目標 | 「爸媽週末要來，家裡要清潔、燈要修，也想安排晚餐。」 |
| 修改動作 | 現場刪除／暫緩或修改一項，證明會員控制 |
| Provider | 至少一個標準 API 接入與一個工作台接入的 Demo Provider |
| 指南 | 中元普渡準備；內部編寫、人工檢視的 Demo `published` 指南，仍不宣稱官方／授權建議 |
| 點數 | 基礎段展示折抵；完成段展示獨立 Demo 活動回饋 |
| 成就 | 完成任務包後一次解鎖，例如「準備周到」；不得重複 |
| 成功服務費 | Provider／平台端的 Demo 投影；費率不代表正式合作 |

## 3. 五分鐘逐秒腳本

> **⚠️ 本節已過時（2026-08-02）。** 下表寫的是舊主線（會場生活圈 → 爸媽來訪任務包 →
> 中元關懷卡 → Provider 結算）；`08ca073` 之後的產品主線已改為社區團購 × 訂閱。
> 錄影與簡報請改用 [Demo 影片錄製：九幕分鏡與自動駕駛](demo-video-recording.md)。
> 本文件其餘章節（§1 成功定義、§4 畫面要求、§6 備援策略、§9 blocker 清單）仍然有效。

| 時間 | 操作 | 畫面必須直接呈現 | 成功條件 |
| --- | --- | --- | --- |
| 0:00–0:30 | 開公開首頁、登入、進生活總覽 | 點數、近期行程、待辦、通知 | 數字來自同一 Demo workspace |
| 0:30–0:45 | 在 AI 問「OPENPOINT 怎麼折抵？」 | 簡短答案、來源、更新日期、「查看我的點數」 | 來自產品 FAQ Wiki，不插入促銷 |
| 0:45–1:20 | 開會場生活圈，切步行／機車與時間 | GeoJSON、Provider 清單、起點、模式、門檻同步 | 不顯示即時路況／導航／未驗證最近距離 |
| 1:20–2:00 | 從清單開服務，手動選方案／時段並折點 | 原價、折抵、應付、確認 | 試算可重算，建立真 Demo Booking／Order |
| 2:00–2:15 | 開訂單，再看通知與行事曆 | 同一 subject ID／StatusEvent | 跨頁狀態一致 |
| 2:15–2:35 | 點「＋ 新對話」，輸入爸媽來訪目標 | 全新 Session、自然承接 | 不帶入前一個 FAQ 對話狀態 |
| 2:35–3:05 | Agent 拆成跨服務任務包 | 自然文字＋結構化任務卡 | 任務源自同一生活目標 |
| 3:05–3:20 | 修改／刪除／暫緩一項 | 總額與時段重新計算 | 不覆蓋其他任務，user 值優先 |
| 3:20–3:30 | 一次核准 `ExecutionGrant` | Provider、時段、預算、點數、TTL | 只涵蓋選中項目 |
| 3:30–4:00 | 切 Provider 工作台接單並回會員端 | Provider 案件、會員狀態回流 | `StatusEvent` 為同一權威來源 |
| 4:00–4:10 | 首頁顯示中元關懷卡 | 原因、來源、更新日、忽略／稍後／關閉 | 不靠旁白補充透明資訊 |
| 4:10–4:25 | 開指南並查看步驟與準備清單 | 必要／可選、警示、來源／更新日 | 內容來自已發布的內部 Demo Wiki，不由模型記憶捏造 |
| 4:25–4:35 | 點「幫我準備」 | PreparationItem、生活圈商品類別、Demo 點數試算 | 不建立訂單，不把類別冒充 SKU |
| 4:35–4:50 | 推進爸媽來訪任務完成 | 生活成果、Demo 回饋、Steam 式成就提示 | 三者分開，完成前不出現 |
| 4:50–5:00 | 切 Provider／平台結算 | 成交、Demo 成功服務費、預估淨額 | 完成後只產生一次 |

## 4. 不靠旁白的畫面要求

- 關懷卡直接顯示「為何提醒、用了什麼資料、來源、更新日」。
- FAQ 與指南回答直接附引用及限制。
- 生活圈直接顯示起點、交通模式、時間門檻與 Demo 地理資料標示。
- 任務卡直接顯示修改／暫緩／刪除，摘要直接顯示重新計算結果。
- Grant 卡直接顯示 Provider、時段、預算／點數上限及有效期。
- Provider 接單、會員狀態、生活成果、成就、回饋及結算都必須有可見結果。
- 中元短場景到「可執行建議」即停止，不用口頭說「後面其實可以下單」。

## 5. 預演前檢查

### 5.1 資料

- [x] Demo reset 後使用同一 seed version；`tests/test_demo_reset.py`。
- [x] 固定 Demo GeoJSON 有步行／機車及 10／15 分鐘切換；已清楚標示 approximation、非即時、非導航。官方座標與外部人工檢查仍是 blocker。
- [x] 測試替身的步行／機車及 10／15 分鐘切換會改變範圍與清單；`tests/test_v4_reachability.py`、`web/app/tests/reachability.spec.ts`。
- [x] 到府服務不被錯放為會員前往的 N 分鐘服務；同上。
- [x] 目前位置只在會員主動按下後單次請求，座標不保存也不送入 pending Demo GeoJSON；`web/app/tests/reachability.spec.ts`。
- [x] product-help FAQ 與內部編寫的中元 Demo Wiki 已發布且來源／更新日可見；不可宣稱為官方／授權生活指南。
- [x] Demo 點數餘額、折抵、回饋、沖銷與結算可重置；`tests/test_v4_outcomes.py`、`tests/test_demo_reset.py`。

### 5.2 Agent

- [x] 新對話不載入舊 Session 內容；session isolation tests。
- [x] 同義改寫得到等價安全 intent；`tests/test_v4_acceptance_matrix.py`。
- [x] stable ID patch 只改相關項目；`tests/test_agent_v4_contracts.py`、M8 regression。
- [x] 「我只是想問」不建立 TaskDraft 或 Grant；product-help test。
- [x] LLM 失敗時 Session 與已取得 facts 不遺失；M8 regression；grounded stage 失敗保留安全摘要。
- [x] 精確 facts 由 ToolResult／畫面卡片提供，grounded 文字不能覆寫；grounded conflict test。
- [x] Agent 畫面呈現 ToolResult 狀態、facts、稽核參照、Wiki 引用與更新日；`web/app/tests/assistantConversation.spec.ts`。

### 5.3 交易與角色

- [x] 手動與 Agent 共用 TaskDraft／Booking／Order；M8 test。
- [x] 未核准、過期或超出 Grant 時零副作用；existing Grant guard tests。
- [x] 重送 action 不重複建單、扣點、發回饋或計費；M8／outcome tests。
- [x] Provider 工作台與會員端使用同一 StatusEvent；M4 scenario tests。
- [x] 其他 Account／Workspace 不能讀取 Session、草稿、訂單或結算；isolation tests。

### 5.4 可用性

- [ ] 390px 與 1440px 的新 v4 頁面人工走查（目前只有 component tests；人工／browser gate）。
- [ ] 鍵盤完成新對話、送訊息、選方案、修改任務與核准授權（人工／browser gate）。
- [x] v4 元件已提供可見 focus、aria-live／status 與文字狀態；需人工 WCAG 走查確認。
- [ ] 完整實站預演穩定少於五分鐘（尚未彩排／錄影）。

## 6. 備援策略

| 風險 | 現場策略 | 不可宣稱 |
| --- | --- | --- |
| Amazon Location 權限／網路失敗 | 使用固定 GeoJSON | 不說是即時 isoline 或路況 |
| LLM timeout | 保留 Session，顯示安全回覆並可重試；必要時使用預先錄影 | 不假裝模型已理解或工具已執行 |
| Provider fake 慢／失敗 | 展示可恢復狀態或切錄影 | 不把前端 fixture 說成遠端接單 |
| 外網中斷 | 所有必要 seed、Wiki、GeoJSON 與影片離線可用 | 不假裝外部正式 API 在線 |
| 時間不足 | 跳過備用頁，不刪基礎手動閉環與授權 | 不以旁白代替關鍵畫面結果 |

## 7. 備用證據，不進主線

- Session 列表、重新命名與封存完整操作。
- 同義改寫／上下文／反悔驗收矩陣。
- Group、Community 管理與個人／社區雙層生活圈。
- MCP 共用 capability。
- timeout、503、malformed response、state unknown 與重試。
- 提醒模式、類別、安靜時段與頻率。
- 活動預算池、退款沖銷與 Provider 結算明細。
- Amazon Location 動態 isoline 架構與權限驗證。

## 8. Demo 後一句話

> AIWave 先用可靠平台完成生活服務，再讓自然 AI 從生活情境開始，在會員授權下把跨服務任務做到履約完成。

## 9. 外部／人工 blocker 清單

- 正式或授權生活指南來源、商業使用許可、地域差異與 reviewer。
- 華南銀行國際會議中心精確座標、人工檢查後 GeoJSON、固定 Provider／Location 座標。
- 真實 Provider API／品牌／價目／取消費率、官方 OPENPOINT 活動規則。
- AWS／Amazon Location 權限、費用／覆蓋驗證與 production secrets。
- 新 v4 頁面 390px／1440px 真實瀏覽器鍵盤走查，以及五分鐘現場錄影備援。
- Session 永久刪除與 retention period 的產品／法務決策；目前只提供可恢復封存，不宣稱永久刪除。
- 真實 LLM 的自然度／人類評分；repository 內只以 deterministic semantic、context、grounding 與安全降級測試作為證據。
