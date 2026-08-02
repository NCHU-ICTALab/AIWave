# AIWave v4 Delivery Tasks

> 狀態：持續交付清單（2026-08-01 更新）。已勾選項目必須有程式碼與可重現測試／畫面證據；未勾選項目不是默認完成。
> 外部資料、人工審核、正式 Provider／AWS 與現場彩排 gate 會保留 unchecked，並記錄於 [v4 五分鐘 Demo runbook](../../../docs/testing/v4-five-minute-demo-runbook.md) 與 current-state 文件。
> 保留工作樹既有修改；本清單不代表已建立 commit。

## Phase 0：內容與 Demo 證據

- [ ] 1. 蒐集並審核 LLM Wiki 生活指南來源
  - [ ] 1.1 找到可商業使用的中元普渡官方或授權來源，記錄地域、更新日、授權與審核者
  - [ ] 1.2 建立並審核 `docs/knowledge/life-guides/zhongyuan-preparation.md`
  - [ ] 1.3 找到中央／地方防災官方來源，建立 `typhoon-preparation.md`
  - [ ] 1.4 找到搬家、戶政、水電／瓦斯等官方來源，建立 `moving-and-housewarming.md`
  - [ ] 1.5 驗證每篇必要／可選項目、差異、警示、推播與商業使用狀態
  - Requirements: R6, R7, R9

- [ ] 2. 依真實 Demo 版本整理產品 FAQ Wiki
  - [x] 2.1 建立點數與折抵說明
  - [x] 2.2 建立預約、改期、取消與退款說明
  - [x] 2.3 建立 TaskDraft、手動接手與 ExecutionGrant 說明
  - [x] 2.4 建立通知與行事曆說明
  - [x] 2.5 建立時間可達生活圈與到府服務範圍說明（維持 draft，直到地理資料 gate 通過）
  - [x] 2.6 已發布的四篇 FAQ 逐篇核對 UI／API、app version、route ID、限制及 Demo 標示；時間可達生活圈文章仍依 2.5 保持 draft
  - Requirements: R5

- [ ] 3. 準備會場固定地理資料
  - [ ] 3.1 確認華南銀行國際會議中心座標
  - [ ] 3.2 建立並人工檢查步行 10／15 分鐘與機車 10 分鐘 GeoJSON
  - [ ] 3.3 建立固定 Provider／Location 座標與清單映射
  - [x] 3.4 記錄資料來源、產生時間與 Demo 標示（pending fallback metadata）
  - Requirements: R8

## Phase 1：自然 Agent 與 Session

- [x] 4. 建立新版 Agent 的 red-capable 驗收矩陣
  - [x] 4.1 同義改寫矩陣
  - [x] 4.2 代名詞、省略句、修正、反悔與暫停矩陣
  - [x] 4.3 非交易對話與零副作用矩陣
  - [x] 4.4 新 Session 隔離與舊任務保留矩陣
  - Requirements: R2, R4, R13

- [x] 5. 定義 Turn、Action、ToolResult 與 TaskPatch 契約
  - [x] 5.1 定義 TurnIntent 與 optional actions
  - [x] 5.2 將 capability descriptions 暴露給 LLM，但由平台驗證 ID／schema／principal
  - [x] 5.3 定義權威 facts、cards、warnings、retry 與 audit refs
  - [x] 5.4 以 stable ID＋expectedVersion 套用增量 patch
  - Requirements: R2, R3, R10

- [x] 6. 實作 ConversationSession 生命週期
  - [x] 6.1 後端 create/list/get/rename/archive/restore API
  - [x] 6.2 title、status、summary、pending grant 與 object refs
  - [x] 6.3 前端新對話、歷史列表、重開、重命名與封存
  - [x] 6.4 AI 主頁與 drawer 共用明確選中的 Session
  - [x] 6.5 Workspace／Account 隔離、OCC 與保留政策（封存保留；未提供永久刪除）
  - Requirements: R4

- [x] 7. 實作兩階段自然對話回合
  - [x] 7.1 組合 bounded Session context、task state、capabilities 與 selected Wiki
  - [x] 7.2 LLM 理解／規劃自然訊息；平台產生並驗證 stable patches 與 proposed actions
  - [x] 7.3 平台驗證與執行工具
  - [x] 7.4 把 facts 交回正式 LLM client 產生 grounded 回覆
  - [x] 7.5 facts／response 矛盾、timeout 與 invalid schema 安全降級
  - Requirements: R2, R3

## Phase 2：LLM Wiki 與生活圈

- [x] 8. 實作小語料 LLM Wiki
  - [x] 8.1 front matter parser 與 published／locale／region／app-version filter
  - [x] 8.2 product-help／life-guide domain router 與隔離
  - [x] 8.3 小語料全量 context loader
  - [x] 8.4 兩種輸出 schema、引用驗證與 action allowlist
  - [x] 8.5 無證據 fallback 與外部內容 prompt-injection 防護（Wiki body 只作資料，不能產生工具 action）
  - Requirements: R5, R6

- [ ] 9. 實作時間可達生活圈
  - [x] 9.1 建立 ReachabilityProvider 深層介面
  - [ ] 9.2 固定 GeoJSON 必要 Demo provider（目前只有空的 pending fallback；實際範圍待外部座標／人工檢查）
  - [x] 9.3 步行／機車與 10／15 分鐘 UI
  - [x] 9.4 幾何範圍與 Catalog Location 篩選
  - [x] 9.5 到府 Provider Service Area 分流
  - [x] 9.6 單次定位權限與不保存預設（前端只在主動按鈕後請求，座標不進 API／Session／localStorage；瀏覽器人工 permission 走查仍屬 15.5）
  - [ ] 9.7 驗證後選配 Amazon Location adapter 與 fallback
  - Requirements: R8

## Phase 3：主動管家、任務包與商業事件

- [x] 10. 實作 LifeContextEvent、CareCandidate 與 CareMessage
  - [x] 10.1 公共日曆、明確授權資料與 Demo event 白名單
  - [x] 10.2 候選與實際送達分離
  - [x] 10.3 原因、資料、來源、忽略／稍後／關閉 action
  - [x] 10.4 正式偏好／頻率規則先完成規格與測試，不放主 Demo 設定流程
  - Requirements: R9

- [ ] 11. 串接情境式生活指南與協助式商務
  - [ ] 11.1 中元關懷卡開啟已發布 Wiki
  - [ ] 11.2 LLM 產生通用 PreparationItem，不產生 SKU
  - [ ] 11.3 Catalog 映射商品、Location、庫存、價格與 Demo 點數
  - [ ] 11.4 會員點「幫我準備」後才建立 checklist／TaskDraft
  - [ ] 11.5 必要、可選、便利與合作推薦分層
  - Requirements: R6, R7, R9

- [x] 12. 深化可編輯 LifeTaskPackage
  - [x] 12.1 來源情境、受益人、ServiceLocation 與 TaskDraft refs
  - [x] 12.2 修改、暫緩、刪除、替換 Provider 與總額／時段重算
  - [x] 12.3 一張 bounded grant 涵蓋選中項目
  - [x] 12.4 跨 Provider 逐項執行、部分失敗保留成功項與重規劃
  - Requirements: R10

- [x] 13. 實作完成結果與商業投影
  - [x] 13.1 LifeOutcome 完成摘要
  - [x] 13.2 once-only Steam 式 Achievement Unlock
  - [x] 13.3 Demo RewardRule、活動預算、上限、去重與沖銷
  - [x] 13.4 completed／delivered 後 once-only Provider success fee
  - [x] 13.5 Provider／平台結算；會員端不顯示抽成
  - Requirements: R11

## Phase 4：整合與驗收

- [ ] 14. 串接五分鐘主 Demo
  - [x] 14.1 基礎會員總覽、FAQ、會場生活圈、手動交易與跨頁同步（地理資料仍以 pending fallback 呈現）
  - [x] 14.2 爸媽來訪自然 Agent、任務修改、一次授權與 Provider 回流
  - [ ] 14.3 中元短場景停在可執行建議，不重跑下單
  - [x] 14.4 生活成果、成就、Demo 回饋與 Provider 結算
  - [ ] 14.5 所有關鍵結果由畫面呈現，不靠旁白補功能（待完整實站彩排／人工 gate）
  - Requirements: R1, R12

- [ ] 15. 完成驗收與證據
  - [x] 15.1 Agent semantic／context／session／facts／grant matrix
  - [x] 15.2 Wiki isolation／citations／no-evidence／action allowlist
  - [x] 15.3 reachability／service-area／privacy（資料未確認時的 honest fallback 與單次定位不保存已測；真實瀏覽器 permission 走查歸 15.5）
  - [x] 15.4 points／reward／fee idempotency and reversals
  - [ ] 15.5 390px／1440px、鍵盤與 WCAG 2.2 AA（既有 M4 證據不替代新 v4 頁面人工走查）
  - [ ] 15.6 五分鐘彩排、離線 seed 與錄影備援
  - [x] 15.7 更新 current-state 文件，只對通過證據的能力標記完成
  - Requirements: R13
