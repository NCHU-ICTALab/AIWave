# AIWave v4：自然對話 Agent、Session 與 LLM Wiki 規格

> 狀態：已確認設計，待實作  
> 定案日期：2026-08-01  
> 上位基線：[15 產品與平台定案基線](15-agreed-product-and-platform-direction.md)  
> 關聯功能：[16 主動生活管家、在地生活圈與商業閉環](16-proactive-life-butler-and-commercial-loop.md)  
> 誠實邊界：本文件描述目標設計；現行 Agent 的完成狀態以程式與測試為準

## 1. 問題與目標

### 1.1 已確認的現況問題

現行 Agent 已具備 LLM 拆解、確定性 Registry／TimeResolver、真目錄方案、`TaskDraft`、`ExecutionGrant` 與履約閉環，但對話體驗受以下設計限制：

- LLM 主要把單句轉成固定 JSON，不負責一般自然回覆。
- 模型每輪只看到當前訊息，無法可靠承接「第二個」「改下午」「先不要」等上下文。
- Service Registry 最終依固定字串包含匹配；小幅同義改寫可能掉出詞表。
- 新自由文字可能重建並覆蓋既有 subtasks，而不是增量修改。
- 釐清、提案、欄位、授權與完成文字多為模板。
- 前端永遠還原 latest Session，沒有新對話或歷史管理入口。

這些是架構邊界，不是單純換更強模型即可解決。

### 1.2 目標

1. 讓好模型真正負責語意理解、自然對話、上下文承接、規劃與 grounded 解釋。
2. 保留日期、服務、庫存、價格、點數、權限、授權、狀態與冪等的確定性守門。
3. 允許聊天、FAQ、生活詢問、探索、規劃、執行、修正、反悔與暫停。
4. 支援可管理的多 Session，不再永遠卡在最後一段對話。
5. 用兩個小型 LLM Wiki 提供有來源的生活指南與產品說明。

## 2. 核心原則

### 2.1 模型自由與系統權威分離

LLM 可以自由決定語氣、解釋順序、釐清問題及建議下一步；平台只限制不可捏造或越權的事實與副作用。正常回覆不要求固定文案。

權威 facts 由結構化資料與 UI 卡片呈現，包含 Provider、Offering、時段、價格、點數、庫存、訂單狀態及授權。自然文字可以比較與解釋，但不得改變 facts。

### 2.2 每輪先理解目的

`TurnIntent` 至少包含：

- `conversation`：一般對話或整理想法。
- `product_help`：AIWave 操作求助。
- `life_guide`：生活知識與準備問題。
- `explore`：查詢服務、比較方案，不建立草稿。
- `plan`：建立或修改任務包／TaskDraft。
- `execute`：要求產生外部影響，須通過授權。
- `pause_or_cancel`：停止、撤回或取消目前推進。

同一回合可有一個主要目的與多個建議 action；沒有 action 是合法結果。

## 3. 兩階段 Agent 回合

### 3.1 第一階段：理解與工具規劃

LLM 輸入：

- System policy 與目前允許的 capability descriptions。
- 目前 Session 的最近訊息與壓縮摘要。
- 目前任務包、subtasks、草稿與待確認狀態。
- 會員明確保存且與本輪相關的偏好／地址。
- 依問題選定的 LLM Wiki 小語料。

LLM 輸出概念契約：

```json
{
  "assistantMessage": "自然語言回覆或釐清問題",
  "intent": "conversation | product_help | life_guide | explore | plan | execute | pause_or_cancel",
  "taskPatches": [],
  "proposedActions": [],
  "clarification": null
}
```

`proposedActions` 只能引用 Capability Registry 暴露的能力與 schema；Account、角色、Workspace 不接受模型參數宣稱，由 server principal 注入。

### 3.2 平台驗證與執行

平台依 action 類型：

1. 檢查 capability、權限、schema 與 idempotency。
2. 解析日期、查 Catalog／Wiki／訂單／點數等權威來源。
3. 低風險讀取可執行；草稿只改 `TaskDraft`；外部影響必須有有效 `ExecutionGrant`。
4. 回傳 facts、可顯示 cards、warnings、errors 及可用下一步。

LLM 無法直接連 DB、呼叫未註冊工具、修改金額、編造 Provider 或繞過授權。

### 3.3 第二階段：grounded 回覆

需要工具結果時，LLM 接收經驗證的 facts 與本輪原始意圖，生成自然答覆。精確 facts 優先由 UI 卡片顯示；若文字引用數字、日期、Provider 或狀態，必須可對應 facts。

若 grounded 回覆格式錯誤、矛盾或遺漏必要警示，退回安全摘要；不能把 LLM 失敗當成工具失敗，也不能把未執行說成已完成。

## 4. 任務狀態更新

### 4.1 Patch，不覆蓋

LLM 提出的是針對既有任務的增量 patch，例如：

- 新增一項。
- 修改預算／時段／服務地點。
- 刪除或暫緩一項。
- 選擇／更換 Provider。
- 引用既有 `TaskDraft` 或正式訂單。

平台以 stable ID 套用 patch 並處理 OCC；不得因新一句自由文字就整批覆寫 subtasks。

### 4.2 修正、反悔與暫停

- 「第二個」依目前可見方案與 Session 上下文解析。
- 「改下午」只修改相關時段條件並重新查詢。
- 「餐廳保留，清潔刪掉」只 patch 指定項目。
- 「只是問問」回到探索，不建立或提交草稿。
- 「先不要」停止推進；撤回 grant 不刪除已完成的正式交易。

不確定引用對象時先自然釐清，不猜測。

## 5. Conversation Session

### 5.1 生命週期

Session 狀態至少包含：

- `id`、`title`、`status`、`createdAt`、`updatedAt`、`archivedAt`。
- `messages` 或可重建訊息來源。
- `summary` 與最近訊息視窗。
- `activeTaskPackageId`／相關草稿與正式任務引用。
- `pendingActions`、`awaiting`、`grantId`。

狀態可為 `active`、`waiting_confirmation`、`task_created`、`archived`。標題可由首輪內容自動建議，會員可修改。

### 5.2 使用者操作

- 建立新對話。
- 列出目前 Workspace 的最近 Session。
- 讀取指定 Session。
- 重新命名、封存、解除封存。
- 明確刪除（不與新對話混用）。
- 引用舊任務至新 Session。

開始新 Session 不帶入舊聊天與暫時狀態；舊 `TaskDraft`、Booking、Order、點數、通知及行事曆不受影響。

### 5.3 記憶邊界

- **Session 記憶**：目前對話、目標、暫時偏好、釐清與任務狀態。
- **會員保存資料**：地址、提醒偏好、硬性限制；會員可查看、修改及刪除。
- **正式系統事實**：TaskDraft、Order、點數、行事曆、通知、Grant；依權限查詢，不等於模型記憶。

不自動讀取其他 Session 全文。跨頁 AI 主頁與側欄共享明確選中的 Session；`latest` 只能是首次沒有選擇時的 fallback。

### 5.4 Pending grant

有待核准 grant 的 Session 在歷史列表明確標示。會員可離開或建立新對話，但 grant 仍受 TTL；不能因切換 Session 自動核准、延長或執行。

## 6. LLM Wiki

### 6.1 兩個隔離知識域

1. **生活指南知識庫**：有來源的情境、步驟與 `PreparationItem`；可在會員同意後連到生活服務。
2. **產品說明知識庫**：已發布功能的操作方式、限制及導覽；不觸發生活消費推薦。

規格、ADR、Roadmap 與 archive 不直接成為產品 FAQ 事實來源。生活指南不得直接複製未授權第三方文章。

### 6.2 競賽版載入

文件量少時先依知識域載入全部 `published` 內容到 LLM context：

```text
分類問題
→ 選擇 knowledge domain
→ 載入該域已發布小語料
→ LLM 依內容回答
→ 顯示引用與更新日期
```

不做 RAG、Embedding 或向量資料庫。當 token、延遲或內容量超過預算時，再以相同文章與 metadata 升級檢索層。

### 6.3 生活指南輸出

```json
{
  "answer": "...",
  "citations": [],
  "preparationItems": [],
  "suggestedActions": [],
  "warnings": []
}
```

`PreparationItem` 是通用需求，不是 SKU。`suggestedActions` 只使用白名單，例如建立清單、查看生活圈 Catalog 或建立草稿。

### 6.4 產品 FAQ 輸出

```json
{
  "answer": "...",
  "citations": [],
  "navigationActions": [],
  "limitations": []
}
```

導覽 action 只能使用系統提供的 route ID／deep link 白名單，不自行拼接 URL。沒有可支持答案的已發布內容時回答不知道。

## 7. UI 呈現

### 7.1 AI 工作區

- 左側／抽屜：新對話與 Session 歷史。
- 主區：自然聊天訊息。
- 需要時才插入 FAQ 引用、生活指南、方案、TaskDraft、Grant、訂單結果卡片。
- Composer 永遠可輸入文字；卡片不阻擋修正、反悔或一般詢問。

### 7.2 權威卡片

卡片直接渲染後端結構：Provider、Offering、時段、價格、點數、範圍、來源與狀態。按鈕傳 stable ID 與 action type，不把顯示文字送回當作權威參數。

### 7.3 自然度

不要求模型使用固定起手式、固定結尾或逐字重述卡片。回覆應簡潔、承接會員用語、不重複、不過度擬人化；不展示 chain-of-thought。

## 8. 安全與隱私

- Server principal 注入 Account、Workspace、Role 與 scopes。
- Wiki 內容視為不可信資料，不能覆蓋 system policy 或要求呼叫工具。
- 模型只能提議 action；平台驗證後才執行。
- 精確位置只在會員主動請求後單次使用，預設不寫入 Session 長期記憶。
- Session、草稿與訂單按 DemoWorkspace／Workspace／Account 隔離。
- Prompt、trace 與日誌不得保存 secrets、hidden reasoning 或不必要個資。
- 外部影響操作持續使用 `ExecutionGrant`、TTL、預算／點數上限與冪等。

## 9. 失敗與降級

| 失敗 | 使用者可見行為 |
| --- | --- |
| LLM timeout／格式錯誤 | 保留 Session，顯示簡短可重試訊息；已有工具結果不遺失 |
| Wiki 無支持內容 | 明確說目前沒有經確認資料，不用模型記憶補答 |
| 工具不可用 | 說明哪項查詢失敗及可重試／手動入口，不假成功 |
| facts 與 LLM 文字矛盾 | 不顯示矛盾文字，改用權威卡片＋安全摘要 |
| Session 找不到／無權 | 404，不揭露其他帳號是否存在；提供建立新對話 |
| grant 過期／範圍變更 | 停止執行，依新 facts 重新產生確認摘要 |

## 10. 驗收策略

### 10.1 自動行為矩陣

- 四句以上同義改寫產生等價 intent／capability，不要求文案相同。
- 多輪「第二個」「改下午」「前一個不要」引用正確 object ID。
- 新增／修改／刪除 task 使用 patch，不覆蓋無關項目。
- 「只是問問」「先不要」不建立交易副作用。
- FAQ 與指南路由至正確知識域，無交叉商業內容。
- 工具 facts 與卡片一致；LLM 不可改寫金額、日期、Provider 或狀態。
- 新 Session 不引用舊 Session 方案；舊正式任務仍可查詢。
- 重送 action 不重複建單、扣點或執行。

### 10.2 人工自然度評分

固定情境以 1～5 分評估：

- 是否理解口語與小幅改寫。
- 是否承接上下文、修正與反悔。
- 是否像自然對話而非逐欄問卷。
- 是否簡潔、不重複、不過度承諾。
- 是否清楚區分建議、草稿、已確認與已執行。

### 10.3 不用逐字 snapshot

自動測試斷言 intent、tool call、state、facts、cards、權限及副作用；只對安全 fallback、授權法律文字等確定性內容做固定字串驗證。

## 11. 交付順序

1. 建立 paraphrase／上下文／Session red-capable 驗收矩陣。
2. 定義 Turn、Action、ToolResult、TaskPatch 與 Session 契約。
3. 加入 Session list／create／rename／archive API 與 UI。
4. 將 LLM 輸入擴充為 Session context＋capabilities，輸出自然訊息＋結構化計畫。
5. 建立兩階段工具回合與 grounded 回覆。
6. 把 Registry 從最終字串裁決改為 capability ID 驗證與模糊安全 fallback。
7. 建立兩個小型 Wiki 載入器、輸出 schema、引用與 action 白名單。
8. 以固定情境跑自動矩陣、真模型人工評分及五分鐘 Demo。

## 12. 明確不做

- 不讓 LLM 直接寫 DB、計價、扣點或改訂單狀態。
- 不自動混入其他 Session 全文或建立不可見長期記憶。
- 不以新增更多同義詞表作為自然語意能力的主要方案。
- 不使用大型向量基礎設施處理目前的小型 Wiki。
- 不展示原始 chain-of-thought、hidden prompt 或 credentials。
- 不因追求自然語氣移除 `ExecutionGrant`、權限、冪等與稽核。
