# 訂單異常與客服閉環

> 狀態：保留為異常處理的 domain 參考；Account／Workspace、ExecutionGrant、Platform API 與 MCP 邊界以 [15](15-agreed-product-and-platform-direction.md) 為準。2026-07-28 的切片完成狀態不等於新基線已完成。

## 要解決的產品問題

生活服務的價值不只在下單。師傅未到、重複扣款、服務品質或改期發生時，使用者必須能在原訂單中說明問題、知道多久有人處理，並持續看到進度；營運人員則需要一個可排序、可接手、可留下結果的工作佇列。

## 端到端流程

1. 住戶從平台訂單或服務委託展開「這筆有問題」。
2. 系統先以 Account、RoleMembership、Workspace 與 scope 驗證訂單權限，再以確定性規則判斷問題類別、優先級與 SLA，展示目前狀態和最近事件作為證據。
3. 會員明確確認，或在有效 `ExecutionGrant` 內，才可用同一份 TaskDraft 建立 `SUP-*` 工單；同一帳號與訂單不可同時存在兩張未結案工單，重試必須使用 idempotency key。
4. 管理端的社區營運中心依優先級查看佇列，確認後接手，填寫處理結果後結案。
5. 住戶回到原訂單即可看到工單狀態與完整事件，不需要另找客服頁面。

Agent 也可從含 `INQ-*`／`ORD-*` 的自然語言要求呼叫 `diagnose_order_issue`，但診斷結果仍只是 TaskDraft；建立工單須由使用者確認或落在有效 ExecutionGrant 內。

## 深模組邊界

- `core/support/service.py`：所有權、分類、優先級、SLA 與應轉交單位。
- `core/support/repository.py`：工單編號、去重、狀態機、事件與 SQLite 持久化。
- Platform API 是 Web、內部 Agent 與 MCP 的唯一 application 邊界，不在 transport 複製商業規則。
- MCP Gateway 只呼叫 Platform API，不直接 import `SupportService`、repository 或資料庫。

## 信任與資料邊界

- 分類與 SLA 標示為 `deterministic_rules`，不是 LLM 猜測。
- 客服 HTTP body 不接受帳號、角色或稽核 actor；競賽 Web 統一從身分 adapter 取出，並在伺服器端區分住戶與管理者能力。查詢與建單都驗證帳號對訂單／委託的所有權；不存在或不屬於本人時一律回覆查無可處理訂單。
- 完成工單不可空白結案，處理人、時間與結果都寫入事件。
- 正式環境須以 OIDC／session middleware 解析 Account、RoleMembership 與 Workspace；未完成正式認證前不可公開部署管理端佇列。MCP principal 由 bearer key 或未來 OAuth／OIDC 解析，不接受模型自行傳入 `account_id`。
- 工單與管理佇列從一開始就必須帶 workspace、partner 與 `personal/group/community` scope，不保留可公開的全域佇列。

## 商業價值與量測

這條流程把「媒合完成」延伸到「履約恢復」，可用於衡量首次回應時間、SLA 達成率、重複異常率、結案時間與服務商品質。下一階段可依 `recommended_route` 串接廠商、金流或客服系統，不需改動住戶體驗與工具契約。

## 驗收證據

- 後端：`tests/test_support_workflow.py`
- 住戶訂單：`web/app/tests/inquiryLifecycle.spec.ts`
- AI 管家：`web/app/tests/assistantPlanning.spec.ts`
- 管理端：`web/app/tests/communityGroupBuy.spec.ts`
