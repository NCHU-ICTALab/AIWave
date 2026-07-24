# 原始資料說明

本目錄為 2026 雲湧智生：臺灣生成式 AI 應用黑客松（統一資訊命題）官方提供的資料集。

資料來源系統為統一資訊旗下的居家服務平台（PIC / OP APP），涵蓋訂單、諮詢單、表單、地區設定等核心業務資料表。

---

## 檔案清單

### 資料表結構定義（SQL DDL）

#### `mms_order_record.sql`
- **內容**：訂單/訂位統一紀錄表（`mms_order_record`）的 PostgreSQL 建表 DDL，含欄位定義、索引與欄位注解。
- **用途**：了解訂單資料的完整欄位語意與資料型別，為解讀 JSON/CSV 範例資料的依據。
- **重點欄位**：
  - `order_no`：訂單編號（服務商提供）
  - `service_vendor_id` / `service_id`：服務提供商與服務 ID，對應 `相關主檔設定.json`
  - `platform_code`：平台代號（`01` = OP APP）
  - `order_type`：訂單類型（`01` 一般服務、`02` 訂位、`07` 商城購物）
  - `order_status`：訂單狀態（`12` 待確認、`80` 完成、`90` 取消中、`98` 部分退款、`99` 全額退款）
  - `member_name / member_phone / member_email`：**AES-256 GCM 加密**，可用對應 `_hash` 欄位做相同會員的比對
  - `order_items`：JSONB，訂購項目明細（格式因服務類型不同而異）
  - `vendor_data`：JSONB，服務商回傳的額外資料（如退款項目、訂位連結）
  - `deposit_amount`：訂金；`original_amount`：服務費；`final_amount`：實收金額
  - `quote_no`：報價單號（水電修繕類服務的估價流程）

#### `縣市區域檔.sql`
- **內容**：`sys_county`（縣市代碼）與 `sys_district`（行政區代碼）兩張參考資料表的 DDL。
- **用途**：解碼訂單與諮詢單中的 `county_code` / `district_code` 欄位。

#### `諮詢單相關table.sql`
- **內容**：諮詢/表單系統相關資料表的 DDL，包含：
  - `pms_form`：表單主檔（服務介紹、注意事項、服務條款等 HTML 內容）
  - `pms_form_feedback`：表單回饋檔（客戶提交的諮詢單，個資欄位同樣 AES-256 GCM 加密）
  - `pms_form_group`：表單題組主檔
  - `pms_form_topic`：題目定義
  - `pms_topic_option`：題目選項
  - `pms_topic_media`：題目媒體（圖片）
  - `pms_topic_county_district_relation`：題目可服務地區設定

---

### 範例資料（JSON / CSV）

#### `相關主檔設定.json`
- **內容**：服務商（`cms_homepage_service_vendor`）與服務項目（`cms_homepage_service`）的主檔設定。
- **服務商對照表**：

  | id | name | 說明 |
  |----|------|------|
  | 1 | 清潔 | 居家清潔服務 |
  | 2 | 寄件 | 包裹運送 |
  | 5 | 餐廳訂位 | 餐廳訂位 |
  | 10 | 商城購物 | 限時購 |
  | 11 | 修繕服務 | 水電服務 |
  | 14 | 美食外送 | 美食外送 |

- **服務項目 type 代碼**：`1` 一般居家清潔、`2` 家電清洗、`3` 包裹寄送、`6` 餐廳訂位、`9` 美食外送、`10` 水電修繕、`11` 商城購物

#### `order_record範例資料.json` / `order_record範例資料.csv`
- **內容**：`mms_order_record` 資料表的範例資料，兩者內容相同，格式不同（JSON 與 CSV）。
- **資料量**：約 2,041 筆訂單記錄（record_id 1 ~ 2041）。
- **注意事項**：
  - `member_name`、`member_phone`、`member_email` 為加密的 binary 資料，直接讀取會顯示亂碼，請使用 `_hash` 欄位識別同一會員。
  - `order_items` 與 `vendor_data` 為 JSON 字串，不同服務類型的資料結構不同：
    - **水電修繕**（service_id=17）：含 `orderItems` 陣列，有子項目（材料費/施工費）、報價單號（`quote_no`）
    - **商城購物**（service_id=18）：含 `item_id`、`item_name`、`unit_price`、`quantity` 的陣列格式
    - **餐廳訂位**（service_id=9）：含餐廳名稱、人數、預約時間、電話、地址
    - **居家清潔**（service_id=1）：簡單的 `itemName`（如「直立式」洗衣機）與 `unitPrice`

#### `縣市區域範例資料.json`
- **內容**：`sys_county`（22 個縣市）與 `sys_district`（全台行政區）的完整參考資料。
- **用途**：將訂單與諮詢單中的 `county_code`（2 碼）與 `district_code`（3 碼）轉換為中文地名。
- **範例**：`county_code="01"` → 台北市；`district_code="002"` → 大同區（郵遞區號 103）

#### `諮詢單相關範例資料.json`
- **內容**：諮詢/表單系統各資料表的範例資料，包含：
  - `pms_form`：表單定義（1 筆範例）
  - `pms_form_topic`：題目列表（含題型如簡答、單選、複選、地區選單、上傳圖片等）
  - `pms_topic_media`：題目圖片
  - `pms_topic_option`：題目選項（含子選項與 columnMapping 對應欄位）
  - `pms_topic_county_district_relation`：題目可服務地區限制
  - `pms_form_feedback`：客戶提交的諮詢單範例（1 筆，含加密個資與回饋內容 JSON）
- **個資加密**：`contact_name`、`contact_mobile`、`contact_email`、`contact_address_detail` 均為 AES-256 GCM 加密，可用對應 `_hash` 做身份比對。

---

## 資料表關聯

```
cms_homepage_service_vendor (id)
  └── cms_homepage_service (service_vendor_id → id)
        └── mms_order_record (service_vendor_id, service_id)

pms_form (id)
  ├── pms_form_group (form_id)
  │     └── pms_form_topic (form_group_id)
  │           ├── pms_topic_option (topic_id)
  │           ├── pms_topic_media (topic_id)
  │           └── pms_topic_county_district_relation (topic_id)
  └── pms_form_feedback (form_id)
        └── [feedback_content JSONB 對應 topic/option]

sys_county (code)
  └── sys_district (county_code)
        └── pms_form_feedback (contact_address_county / contact_address_district)
        └── pms_topic_county_district_relation (county_code / district_code)
```

---

## 使用建議

1. **快速了解業務**：先閱讀 `相關主檔設定.json` 了解平台提供哪些服務，再搭配 `mms_order_record.sql` 的欄位注解理解訂單流程。

2. **載入資料庫分析**：
   - 可執行 `mms_order_record.sql`、`縣市區域檔.sql`、`諮詢單相關table.sql` 在 PostgreSQL 建立 schema。
   - 再將各 JSON 範例資料匯入對應資料表進行 SQL 查詢分析。

3. **不需解密即可做的分析**：
   - 訂單量、金額、服務類型分佈、時間趨勢等統計分析可直接使用非加密欄位。
   - 用 `member_name_hash` / `member_phone_hash` 辨識同一會員的跨訂單行為（相同 hash = 同一人）。

4. **AI 應用開發參考**：
   - `pms_form_feedback.feedback_content`（JSONB）包含客戶填寫的完整諮詢內容，是訓練客服 AI 或意圖識別的重要語料。
   - `order_items` 中的 `itemName`（如「水管-水管不通」、「插座-插座沒電」）可作為服務分類的標籤資料。
