# P0 推進紀錄

## 2026-07-25

### 已完成基線

- 建立 Vue 3＋Vite＋TypeScript 應用與六個工作區路由。
- 建立九項服務目錄、確定性商城折扣、訂單建立與黑貓種子訂單。
- 建立社區需求 → 廠商報價 → 社區指派 → 平台狀態回流。
- 建立同源 session 模式 `/api/v1` client，不把 API key 或角色授權放在前端。
- 建立確認視窗、Copilot 抽屜、焦點管理、AA 色彩 token 測試與 demo reset。
- 驗證：5 個測試檔、15 項測試、typecheck、production build 全數通過。

### 當前工作

- 已完成：[九項服務題組與報價規則](tickets/001-service-forms-and-pricing.md)
- 下一張可開始：[訂單事件、異常與客服閉環](tickets/002-order-events-and-support.md)

### 九項服務題組成果

- 使用官方 `pms_form_topic.type` 數字代碼承載 P0 所需簡答、詳答、單選與日期題型。
- 九項服務各自有題組、資料用途、落地類型與確定性價格規則。
- 諮詢、訂位、寄件與訂單使用不同公開 store seam；錯誤 action 不會誤寫入。
- 商城優惠券、OPENPOINT 與 icash Pay 均由使用者明確選擇後重算。
- 支援 `/app/services/:serviceSlug`，可由 LINE 或 Web 直接開啟指定服務。
- 表單空白、無效選項、純空白文字、數量範圍與日期範圍都有文字錯誤與焦點導引。
- 展示日期由可注入 `DEMO_NOW` 推導，不依執行機器當天時間。
- 最終驗證：6 個測試檔、26 項測試、typecheck、production build 全數通過。
- 雙軸審查複核：Spec 與 Standards 均無剩餘高／中問題。

### 已知風險

- ~~repository 沒有初始 commit~~ → 2026-07-26 已解除。
- 目前 API client 是契約邊界，畫面仍由種子 store 驅動；四類提交 seam 尚待後端 repository 實作。
- 尚未執行瀏覽器層 390×844／1440×900 的完整流程驗收。

## 2026-07-25・方向校正：從互動原型升級為真 AI Demo

- 使用者指出：只有 fixture/mock 且 AI 無實際作用，不足以構成有價值的 Demo。
- 盤點確認：LLM URL、key、model 均已配置；`FormAgent`、FastAPI chat API 與確定性 `FormSession` 已存在，Python 測試 13/13 通過。
- 問題根因：後端 AI 是孤島，未接 Vue、未建立平台自己的 inquiry record，也未回流跨工作區。
- 決策：暫停純 UI 擴充，優先完成 [真 AI 諮詢閉環](tickets/007-real-ai-inquiry-loop.md)。只有廠商上游維持 mock；平台 Agent、規則、寫入與事件必須真實執行。

## 2026-07-26・題組定義收斂、官方資料接入、產品化轉向

- **題組定義收斂**（commit `4f167a1`）：九項服務定義移到後端成為單一事實來源，
  前端改 fetch；金額由後端統一 API 試算。前端測試 fixture 由
  `tools/dump_catalog_fixture.py` 從後端產生，避免漂移。
- **官方訂單資料接入**（commit `a31f3cf`）：先前 `mms_order_record`（99 筆／10 帳號）
  完全未被程式使用、畫面數字全寫死。現以官方資料建立行為軌跡、消費摘要與**可解釋推薦**
  （每則附 `record_id` 證據，由規則產生非 LLM）。
- **產品化轉向**（commit `be66181`）：使用者指出目前是「為 demo 而做」，初次到訪者
  不知道怎麼用。診斷與目標旅程記於 [08 產品體驗](../specs/08-product-experience.md)，
  三項分岔待決策。
- **文件整理**（本次）：過時文件移入 [archive/](../archive/)；`brand-spec` 提升為現行規格。
- 測試現況：後端 65、前端 36，typecheck 與 production build 通過。

## 2026-07-28・會員產品殼與首頁資訊架構

- 會員主導覽改為固定五頁籤：首頁、點數兌換、AI、服務、會員中心；訂單與群組收回次層入口。
- 手機使用同一組語意導覽固定於底部，補齊 safe area、44px 觸控目標與精確 active state。
- 首頁依核准順序呈現資源總覽、待處理、輕量 AI、單項可撤回推薦、常用功能與優惠。
- 點數頁透過 `/personalization/{account_id}/restock-plan` 顯示展示錢包與確定性節省方案，明確標示非 OPENPOINT 即時帳戶。
- 會員中心顯示目前登入身分，並提供訂單、群組與點數的可操作次層入口；不以靜態條列冒充功能。
- `ui-ux-pro-max` 的 AI 原生與 WCAG 規則已整理進 `design-system/aiwave/MASTER.md`；視覺仍以 LearnHub 品牌規範為準。
- 驗證：前端 17 個測試檔、123 項測試、typecheck、production build、聊天內捲稽核皆通過；390×844 與 1440×900 的 12 頁實際 UI 稽核未發現溢出、觸控、HTTP 或 console 問題。

## 2026-07-28・獨立 Vendor API 與正式切換 seam

- 建立 `contracts/vendor-openapi.yaml`，涵蓋廠商、據點、方案、可預約時段、諮詢單、
  報價、訂單、履約事件與受保護 fake control plane。
- 建立可獨立啟動的 `fake_upstreams.vendor_app`；固定 Faker `zh_TW` seed 產生
  10 個人工白名單品牌、30 個台灣據點、120 筆諮詢單與 120 筆報價。
- 品牌包含使用者在 OPENPOINT 觀察到的太子物業與王子水電；Faker 不生成品牌名，
  價格、評分、時段與案件均標示為競賽資料，不冒充正式合作 API 或即時實價。
- 建立 `VendorClient`、`MockVendorClient`、`RealVendorClient` 與 `VendorService`；
  `VENDOR_MODE=fake|real` 只在後端切換，Vue、Agent 與 MCP 共用同一份媒合規則與狀態。
- 讀取故障會明確標示 `offline_fallback` 與原因；寫入故障不會假裝成功。
- 驗證涵蓋 OpenAPI lint、固定 seed/reset、一次性故障、冪等寫入、完整履約生命週期、
  malformed 2xx、real Bearer token，以及 Web／MCP 同源結果。

## 2026-07-28・P0 Hero、群組槓桿與 MCP 閉環完成

- Hero 句子穩定建立同一筆 `LifeTask`，拆成浴室燈修繕與冷氣清洗，辨識週六並只補日期確認、
  地址及個人／家庭／社區範圍；廠商比較與 OPENPOINT 展示折抵由規則計算。
- 一次確認以版本與 idempotency key 建立兩件 Vendor API 諮詢；部分失敗保存成功項目，UI 顯示
  真實上游原因並提供安全重試，不會重複建單。
- 王子水電與 DUSKIN 樂清工作台讀取各自案件、報價及更新履約；會員 AI、首頁與折疊訂單頁
  讀取同一個上游狀態。vendor proxy 以登入身分隔離，不能藉 query string 查看其他廠商。
- 住戶社區頁新增明確同意的共同需求：未同意不能送出；後端保存 consent version，只聚合設備、
  台數、時段與特殊需求並以帳號雜湊去重，不回傳其他住戶識別資料。
- Registry／MCP 新增 6 個會員 LifeTask tools 與 4 個廠商履約 tools；整合測試實際用外部 Agent
  transport 完成草稿、設定、送單、兩廠商報價、接受報價、完工與會員回讀。
- 故障矩陣涵蓋慢速成功、503、timeout、malformed 2xx、離線 fallback、寫入不假成功與恢復。
- 測試、操作、故障與五分鐘節奏統一記錄於 `docs/testing/demo-runbook.md`。
