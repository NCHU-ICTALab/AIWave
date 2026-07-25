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
