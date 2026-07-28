# 訂單事件、異常與客服閉環

- 類型：task（AFK）
- 狀態：完成（2026-07-28）
- 阻擋：[九項服務題組與報價規則](001-service-forms-and-pricing.md)

## Question

如何用同一個訂單與事件模型呈現購物、寄件、訂位與到府服務，並讓延誤或履約問題能建立客服工單？

## Answer

以既有 `INQ-*` 服務委託與 `ORD-*` 平台訂單為客服 subject，不另造一套訂單聚合；`SupportService` 先驗證所有權，再從問題內容與 subject 最近事件產生可重算的類別、優先級與 SLA。`SqliteSupportRepository` 保存 `SUP-*` 工單與 `open → in_progress → resolved` 事件，Web、Planner 與 MCP 共用這一層。

住戶可在原訂單內診斷、確認建單及追蹤；AI 管家可從單號診斷並提供建單動作；管理端可接手與帶結果結案。詳見 [訂單異常與客服閉環](../../specs/11-order-exception-support.md)。

## Evidence

- `tests/test_support_workflow.py`
- `web/app/tests/inquiryLifecycle.spec.ts`
- `web/app/tests/assistantPlanning.spec.ts`
- `web/app/tests/communityGroupBuy.spec.ts`
