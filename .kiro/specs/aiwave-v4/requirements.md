# AIWave v4 Requirements

> 狀態：需求已由產品負責人逐項確認  
> 日期：2026-08-01  
> 本次範圍：建立規劃與文件；不得因本 spec 自動執行 `tasks.md` 或修改應用程式碼  
> 詳細來源：`docs/specs/15-*`、`16-*`、`17-*` 與 `CONTEXT.md`

## Evidence convention

每項對外能力必須區分：競賽可展示版本、正式產品版本與證據邊界。未完成能力、固定 Demo 資料、合理推導及待官方驗證內容不得描述成正式上線或已合作。

## Requirement 1：基礎平台先於創新

### User story

As a 評審或會員, I want 先看見可操作的生活服務閉環, so that 我能確認 Agent 建立在真實平台能力上。

### Acceptance criteria

1. WHEN 主 Demo 開始 THEN THE SYSTEM SHALL 先展示會員總覽、服務探索、手動預約、點數折抵及履約同步。
2. WHEN 一筆手動交易成立 THEN THE SYSTEM SHALL 讓訂單、通知、行事曆與 Provider 工作台讀取同一份狀態。
3. IF 某功能只有 seed、fake upstream 或固定資料 THEN THE DOCUMENTATION SHALL 清楚標示 Demo 性質。

## Requirement 2：自然對話與多種對話目的

### User story

As a 會員, I want 用自然說法聊天、詢問、比較、規劃、修改、反悔或執行, so that AI 不像固定表單機器人。

### Acceptance criteria

1. WHEN 會員以同義改寫描述相同需求 THEN THE SYSTEM SHALL 產生等價 intent 與 capability 選擇，不要求回答文案相同。
2. WHEN 會員使用「第二個」「改下午」「前一個不要」等上下文語句 THEN THE SYSTEM SHALL 引用目前 Session 中正確的 object。
3. WHEN 會員只想了解、比較或詢問 THEN THE SYSTEM SHALL NOT 強迫建立 TaskDraft、Grant 或交易。
4. WHEN 會員修正或反悔 THEN THE SYSTEM SHALL 只 patch 相關任務，不覆蓋其他項目。

## Requirement 3：兩階段 Agent 與權威 facts

### User story

As a 會員, I want AI 回答自然但數字與操作可靠, so that 我能信任方案與交易結果。

### Acceptance criteria

1. WHEN 一輪需要資料或操作 THEN THE SYSTEM SHALL 先由 LLM 理解與規劃工具，再由平台驗證／執行，最後由 LLM 根據結果自然回答。
2. THE SYSTEM SHALL 由確定性模組裁決 capability、日期、Provider、Offering、庫存、時段、價格、點數、權限、Grant、狀態及冪等。
3. WHEN 顯示精確方案或交易 facts THEN THE SYSTEM SHALL 使用結構化權威卡片，不依賴聊天文字作為操作參數。
4. IF LLM 回覆與工具 facts 矛盾 THEN THE SYSTEM SHALL 顯示權威卡片與安全摘要，不顯示矛盾內容。
5. THE SYSTEM SHALL NOT 展示 chain-of-thought、hidden prompt、credentials 或不必要個資。

## Requirement 4：Conversation Session 管理

### User story

As a 會員, I want 開新對話並管理歷史 Session, so that 新問題不被舊狀態卡住。

### Acceptance criteria

1. THE SYSTEM SHALL 支援建立、列出、讀取、重新命名、封存及解除封存 Session。
2. WHEN 會員建立新 Session THEN THE SYSTEM SHALL NOT 帶入其他 Session 的訊息、暫時偏好或待釐清狀態。
3. WHEN 新 Session 建立 THEN THE SYSTEM SHALL NOT 刪除舊 Session 已建立的 TaskDraft、Booking、Order、點數或行事曆事件。
4. WHEN Session 有待確認 Grant THEN THE SYSTEM SHALL 在歷史列表標示，且切換 Session 不得核准、延長或執行 Grant。
5. THE SYSTEM SHALL 依 DemoWorkspace、Workspace 與 Account 隔離 Session。

## Requirement 5：產品說明 Wiki

### User story

As a 會員, I want 問 AIWave 如何操作並直接前往功能, so that 我不必離開產品搜尋說明。

### Acceptance criteria

1. THE SYSTEM SHALL 只載入另外整理、狀態為 `published` 且符合目前 app version 的 product-help 文件。
2. WHEN 回答產品問題 THEN THE SYSTEM SHALL 提供引用、更新日期、限制及白名單 navigation action。
3. THE SYSTEM SHALL NOT 把規格、Roadmap 或 archive 中未實作內容回答成可用功能。
4. THE SYSTEM SHALL NOT 在取消、退款、權限或錯誤求助回答中插入商品與促銷。
5. IF 沒有支持內容 THEN THE SYSTEM SHALL 明確回答目前沒有經確認資料。

## Requirement 6：生活指南 Wiki

### User story

As a 會員, I want 取得有來源的生活準備指南, so that 第一次處理祭拜、防災或搬家時知道如何開始。

### Acceptance criteria

1. THE SYSTEM SHALL 將 life-guide 與 product-help 內容分開載入與驗證。
2. EVERY published 生活指南 SHALL 包含適用情境、地域、步驟、必要／可選準備項目、來源、授權、更新日及審核者。
3. THE SYSTEM SHALL NOT 擷取、複製或改寫未授權第三方文章作商業知識庫。
4. WHEN LLM 產生準備清單 THEN THE SYSTEM SHALL 只輸出通用 PreparationItem；SKU、價格、庫存、門市與點數由 Catalog／Provider 決定。
5. IF 內容存在地域、家庭或信仰差異 THEN THE SYSTEM SHALL 顯示差異與警示，不把單一做法寫成絕對規則。

## Requirement 7：協助式商務

### User story

As a 會員, I want 先獲得有用提醒再決定是否看商品, so that 我不被焦慮式推播操控。

### Acceptance criteria

1. WHEN 系統送出生活提醒 THEN THE SYSTEM SHALL 先顯示情境、原因、來源與可提供的協助，不直接推銷具體商品。
2. WHEN 會員主動開啟指南並點「幫我準備」 THEN THE SYSTEM MAY 顯示必要、可選、便利與明確標示的合作推薦。
3. THE SYSTEM SHALL NOT 未經同意建立購物車、TaskDraft、Booking 或 Order。
4. THE SYSTEM SHALL NOT 把可選品項描述成必要，或以宗教、災害、家庭及健康焦慮促成消費。

## Requirement 8：時間可達生活圈

### User story

As a 會員, I want 查看從指定起點步行或騎機車 N 分鐘可到達的服務, so that 我能理解周邊生活供給。

### Acceptance criteria

1. THE DEMO SHALL 以華南銀行國際會議中心（臺北市信義區松仁路 123 號）為固定起點。
2. THE DEMO SHALL 支援步行 10 分鐘，並可切換步行 15 分鐘與機車 10 分鐘。
3. WHEN 交通方式或門檻改變 THEN THE SYSTEM SHALL 同步更新 GeoJSON 範圍與服務清單。
4. THE DEMO SHALL 使用經人工檢查的固定 GeoJSON 作必要版本，並標示非即時路況與導航。
5. THE SYSTEM SHALL 只將時間可達生活圈用於會員前往的服務；到府服務 SHALL 使用 Provider Service Area。
6. WHEN 會員選擇目前位置 THEN THE SYSTEM SHALL 明確請求權限、單次使用且預設不保存。
7. Amazon Location dynamic isoline SHALL 為權限、覆蓋、成本與品質驗證後的加分／正式方案，不阻塞必要 Demo。

## Requirement 9：主動生活管家

### User story

As a 會員, I want 收到透明且可關閉的生活協助, so that AI 能在適當時機幫忙而不造成打擾。

### Acceptance criteria

1. THE SYSTEM SHALL 分開 LifeContextEvent、CareCandidate 與實際 CareMessage。
2. EVERY CareMessage SHALL 顯示提醒原因、使用的授權資料、內容來源、更新日期及忽略／稍後／關閉入口。
3. THE SYSTEM SHALL 將一般關懷與交易通知分開計數。
4. THE DEMO SHALL 只要求站內關懷卡；完整模式、頻率與安靜時段設定不進主 Demo。
5. THE SYSTEM SHALL NOT 使用背景定位、聯絡人、相簿、郵件或秘密敏感推論觸發關懷。

## Requirement 10：可編輯任務包與部分失敗

### User story

As a 會員, I want 在一次授權前逐項修改 AI 建議, so that 我保有決定權。

### Acceptance criteria

1. THE SYSTEM SHALL 允許逐項修改、暫緩、刪除及更換 Provider。
2. WHEN 任務改變 THEN THE SYSTEM SHALL 重新計算總額、時段衝突與 Grant 範圍。
3. WHEN 會員確認 THEN THE SYSTEM SHALL 只對選中項目提出一張 bounded ExecutionGrant。
4. WHEN 跨 Provider 某項失敗 THEN THE SYSTEM SHALL 保留成功項、標示失敗原因並重新規劃失敗項。
5. IF 替代方案超出原 Grant THEN THE SYSTEM SHALL 重新確認。
6. 重試 SHALL NOT 重複建單、扣點、發回饋或收費。

## Requirement 11：完成結果、點數與結算

### User story

As a 會員或 Provider, I want 完成事件產生清楚且可追溯的結果, so that 回饋與收入不會提前或重複。

### Acceptance criteria

1. THE SYSTEM SHALL 分開 LifeOutcome、Achievement Unlock 與 Demo OPENPOINT reward。
2. Achievement Unlock SHALL 由可驗證完成事件觸發一次，且 SHALL NOT 直接發點或建立 XP／等級／排行榜。
3. Demo reward SHALL 只在符合活動資格的完成事件後發放，並支援上限、重放去重與沖銷。
4. Provider success fee SHALL 只在個別 Booking／Order 完成後產生一次；建立、接單、取消、失敗及未履約為零。
5. 會員端 SHALL NOT 顯示平台抽成；Provider／平台端 MAY 顯示 Demo 成交、費用、贊助與預估淨額。
6. THE DOCUMENTATION SHALL 標示點數、費率、贊助與合作條件為 Demo 或待官方驗證。

## Requirement 12：五分鐘 Demo

### User story

As a 評審, I want 在五分鐘內先看基礎再看創新, so that 我能理解價值、可信度與商業落點。

### Acceptance criteria

1. THE DEMO SHALL 依 `docs/testing/v4-five-minute-demo-runbook.md` 在五分鐘內完成。
2. THE DEMO SHALL 以前兩分鐘展示基礎平台，後三分鐘展示 Agent、Provider 回流、生活指南、成就與結算。
3. 中元短場景 SHALL 結束於來源指南、準備清單、生活圈商品類別與點數試算，不重跑完整下單。
4. 關鍵能力 SHALL 由畫面直接呈現，不以旁白補足缺少結果。
5. Group、Community 管理、MCP、完整提醒設定、錯誤注入及活動帳務 SHALL 放備用證據，不進主線。

## Requirement 13：驗收與成功指標

### Acceptance criteria

1. 自動驗收 SHALL 覆蓋同義改寫、上下文引用、修正／反悔、非交易對話、新 Session 隔離、facts 一致、Grant、冪等與權限。
2. 自動測試 SHALL NOT 對一般 LLM 回答做逐字 snapshot。
3. 人工驗收 SHALL 評估理解、上下文、自然度、簡潔度與建議／草稿／已執行狀態區分。
4. 北極星指標 SHALL 為生活任務完成率。
5. 未經授權交易次數 SHALL 為 0。
