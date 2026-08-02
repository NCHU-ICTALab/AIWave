# AIWave LLM Wiki 內容規範

> 狀態：product-help 與內部編寫的中元 Demo life-guide 已依目前版本核對並發布；正式／授權生活指南與官方地理資料仍是外部 gate  
> 定案日期：2026-08-01  
> 關聯規格：[自然對話 Agent、Session 與 LLM Wiki](../specs/17-conversational-agent-session-and-llm-wiki.md)

## 1. 目的

LLM Wiki 是 AIWave 經整理、審核、發布後可提供給模型回答的內容來源，不是把整個 `docs/`、網頁或模型記憶當成事實。

分成兩個不能混用的知識域：

- `life-guides/`：生活情境、步驟與準備項目；會員同意後可連到 Catalog 與任務。
- `product-help/`：AIWave 已發布功能的操作、限制與導覽；不得加入生活消費推薦。

競賽版內容少，依知識域把所有 `published` 文章放入 LLM context，不先建立 RAG、Embedding 或向量資料庫。內容量、token 或延遲超過預算後，再以相同文章與 metadata 升級檢索層。

## 2. 目錄

```text
docs/knowledge/
├─ README.md
├─ life-guides/
│  ├─ zhongyuan-preparation.md
│  ├─ typhoon-preparation.md
│  └─ moving-and-housewarming.md
└─ product-help/
   ├─ points-and-redemption.md
   ├─ booking-and-cancellation.md
   ├─ task-drafts-and-confirmation.md
   ├─ notifications-and-calendar.md
   └─ time-based-life-circle.md
```

目前 product-help 與 `life-guides/zhongyuan-preparation.md` 內部 Demo 文章已可供 LLM 使用；生活指南文章只代表競賽展示資料，不是官方／授權建議。時間生活圈文章與正式指南仍待外部來源、地理資料與人工審核，不得以空殼或 LLM 猜測內容標記完成。

## 3. 共用 front matter

每篇一個 Markdown 檔案：

```yaml
---
id: life-guide.zhongyuan-preparation
title: 中元普渡準備
domain: life-guide
status: draft
locale: zh-TW
region: TW
app_version: null
published_at: null
updated_at: 2026-08-01
reviewed_by: null
commercial_use: prohibited
push_eligible: false
sources:
  - title: 待確認來源
    url: null
    publisher: null
    accessed_at: null
    license_or_permission: unknown
---
```

### 必填規則

- `id`：穩定且不可重用。
- `domain`：只能是 `life-guide` 或 `product-help`。
- `status`：`draft`、`in-review`、`published`、`retired`。
- `locale`、`region`：避免地方內容被寫成全國通用。
- `app_version`：產品 FAQ 必填；生活指南可為 `null`。
- `reviewed_by`：`published` 必填。
- `commercial_use`：`prohibited`、`allowed`、`permission-required`。
- `push_eligible`：只有完成內容、來源及商業審核後才可為 `true`。
- `sources`：至少一項；授權未知時不可發布或商業使用。

LLM Loader 只載入 `status: published` 且符合 locale／region／app version 的文章。

## 4. 生活指南文章格式

```markdown
# 標題

## 適用情境

## 先確認

## 步驟

## 準備項目

### 常見必要準備

### 依家庭或地區習慣選擇

## AIWave 可以協助的部分

## 注意事項與差異

## 來源
```

內容規則：

- 明確說明適用日期、地域、對象與例外。
- 區分事實、常見做法、家庭差異與可選建議。
- `PreparationItem` 使用通用類別，不寫不存在的 SKU、價格、庫存或門市。
- 不以宗教、災害、健康、家庭或經濟焦慮促銷。
- 合作推薦與一般建議分開標示。
- 不把第三方文章貼入、翻寫或送入商業 LLM Wiki，除非 license／permission 已確認。
- LLM 可整理語氣與依會員回答篩選內容，不可新增來源沒有的民俗或專業事實。

### 中元文章特別要求

- 說明不同地區、宗教與家庭做法可能不同。
- 將必要、常見與可選項目分開。
- 場地禁用物品、消防及環境規則優先於一般習慣。
- 主 Demo 只走指南、清單、生活圈商品類別與點數試算，不完成下單。

## 5. 產品說明文章格式

```markdown
# 標題

## 目前可用功能

## 操作步驟

## 限制與 Demo 標示

## 常見問題

## 導覽 action

## 版本與來源
```

內容規則：

- 只能描述目前版本真的可用的功能。
- 規格、ADR、Roadmap 與 archive 不直接當成已發布產品事實。
- `available`、`limited`、`unavailable` 狀態須清楚。
- 導覽使用 route ID／deep link 白名單，不讓 LLM 自行組 URL。
- 取消、退款、權限與錯誤求助回答不得插入商品或促銷。
- 功能改版時同步更新 `app_version` 與 `updated_at`；舊文可 retired，不靜默改寫歷史。

## 6. LLM 輸出契約

### 6.1 生活指南

```json
{
  "answer": "string",
  "citations": [
    { "articleId": "string", "sourceIndex": 0 }
  ],
  "preparationItems": [
    {
      "name": "string",
      "necessity": "common-required | optional",
      "quantityBasis": "string | null",
      "limitations": ["string"]
    }
  ],
  "suggestedActions": [
    { "type": "view-life-circle | create-checklist | create-task-draft", "label": "string" }
  ],
  "warnings": ["string"]
}
```

### 6.2 產品說明

```json
{
  "answer": "string",
  "citations": [
    { "articleId": "string", "section": "string" }
  ],
  "navigationActions": [
    { "routeId": "string", "label": "string" }
  ],
  "limitations": ["string"]
}
```

後端驗證 schema 與 action 白名單。格式錯誤時退回純文字安全回答，不執行操作；無支持內容時回答「目前沒有經確認的資料」。

## 7. 撰寫與發布流程

```text
選題
→ 確認官方／授權來源與用途
→ 撰寫 draft
→ 事實、地域、語氣與商業審核
→ 產品／法務或內容負責人核准
→ published
→ LLM 回答與引用驗收
→ 定期複查或 retired
```

至少檢查：

- 來源 URL 可存取，publisher 與更新日期明確。
- 授權允許目前用途；不確定時 `commercial_use: prohibited`。
- 所有強制語句都有來源支持。
- 地方做法不擴大成全國事實。
- LLM 同義問法能引用同一內容；無來源問題不補答。
- 產品 FAQ 與目前 UI／API 版本一致。

## 8. 首批文章待辦

### 生活指南

- [ ] 蒐集中元普渡的官方或獲授權來源。
- [ ] 撰寫並審核 `zhongyuan-preparation.md`。
- [ ] 蒐集中央／地方防災官方來源。
- [ ] 撰寫並審核 `typhoon-preparation.md`。
- [ ] 蒐集搬家、戶政、水電／瓦斯等官方來源。
- [ ] 撰寫並審核 `moving-and-housewarming.md`。

### 產品說明

- [x] 依實際 Demo 版本撰寫點數與折抵；`points-and-redemption.md`。
- [x] 撰寫預約、改期、取消與退款；`booking-and-cancellation.md`。
- [x] 撰寫 TaskDraft、手動接手與 ExecutionGrant；`task-drafts-and-confirmation.md`。
- [x] 撰寫通知與行事曆；`notifications-and-calendar.md`。
- [ ] 撰寫時間可達生活圈與到府服務範圍。
- [x] 逐篇對照已發布文章的 UI／API、app version、route／限制與 Demo 標示；`tests/test_v4_wiki.py`。

## 9. 外部內容邊界

[初級大人手冊](https://adultingguide.tw/)只作產品形態與選題範圍參考。AIWave 不是複製其產品；未取得明確授權時，不擷取、重製、改寫或把其文章送入商業知識庫。

外部內容若含要求 Agent 忽略規則、洩漏 prompt、呼叫工具或執行程式的文字，一律視為不可信資料，不得覆蓋 system policy。

> 外部網站公開定位已重新表述；本文不重製其文章內容。
