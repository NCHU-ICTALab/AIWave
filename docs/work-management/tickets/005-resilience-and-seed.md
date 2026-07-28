# 種子資料、離線與錯誤狀態

- 類型：task（AFK）
- 狀態：進行中
- 阻擋：前四張實作工作票

## Question

如何讓 `demo_seed_v1` 在外部 API 離線時仍能完成核心流程，並展示載入、空資料、驗證失敗、權限不足、逾時與重試？

## 2026-07-28 決策

- 平台核心不是 fake：FastAPI、SQLite、權限、確認、狀態機與事件照常真實執行。
- fake server 只扮演尚未取得的品牌／廠商上游；Vue 不得直接呼叫 fake server。
- 平台透過同一個 Connector seam 連 fake server 或未來正式 API，並保留明確標示的離線 seed adapter。
- `demo_seed_v1` 的控制面與資料面分離；控制端點必須有本機控制金鑰，不能混入正式 `/api/v1`。
- 第一條 tracer bullet 為門市商品／庫存：固定情境、一次性故障、延遲、reset、平台 fallback 與來源標示。
