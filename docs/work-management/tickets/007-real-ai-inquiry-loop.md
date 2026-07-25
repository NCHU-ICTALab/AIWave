# 真 AI 諮詢閉環

- 類型：task（AFK）
- 狀態：**完成**（2026-07-26，commit `4f167a1`）
- 阻擋：無

## Question

如何讓評審在同一套正式 Vue 介面中，親眼看到自然語言由真 LLM 結構化、經確定性規則驗證、由使用者確認，再由後端建立可查詢的諮詢紀錄並回流訂單中心？

## Acceptance

- Vue Copilot 呼叫 FastAPI，而非回傳固定文字。
- LLM 只負責口語抽取；題組順序、驗證、確認與寫入由後端規則控制。
- API 回傳可展示的操作軌跡、目前進度與結構化結果，不揭露模型內部思考。
- 確認前不建立資料；確認後後端產生 inquiry id、狀態與事件。
- 可用 API 查回剛建立的 inquiry。
- Vue 接收後端 operation，訂單中心立即顯示同一 inquiry id。
- LLM／JSON 失敗有可理解的重試狀態，不產生假成功。
- 後端以 fake LLM 做穩定整合測試；可選的 live smoke test 使用既有 `.env`，不輸出憑證。

## Progress

- [x] 確認 LLM 設定完整
- [x] 確認既有表單引擎 13 tests 全綠
- [x] 後端 inquiry repository 與事件（`core/inquiries/repository.py`）
- [x] Chat API 結構化 trace／progress／operation（`api/app.py`）
- [x] FastAPI 整合測試（`tests/test_ai_inquiry_api.py`）
- [x] Vue AI client 與真正對話 UI（`aiInquiryClient.ts`＋`CopilotDrawer.vue`）
- [x] 後端 operation 回流 Pinia／訂單中心（`recordAiInquiry`＋`OrdersView`）
- [x] 完整驗證與雙軸審查
