---
id: product-help.task-drafts-and-confirmation
title: TaskDraft、手動接手與授權
domain: product-help
status: published
locale: zh-TW
region: TW
app_version: 0.1.0
published_at: 2026-08-01
updated_at: 2026-08-01
reviewed_by: current-code-audit
commercial_use: prohibited
push_eligible: false
sources:
  - title: TaskDraft and Agent implementation
    path: core/task_drafts
    license_or_permission: internal
---

# TaskDraft、手動接手與授權

## 目前可用功能

TaskDraft 是手動預約精靈與 AI 管家共用的進行中草稿。AI 選定方案後可切到帶有 `draft` ID 的手動頁面；手動修改的值會以會員輸入為優先。

## 操作步驟

1. 在 AI 對話中選定方案，或從服務頁開始預約。
2. 在草稿中補齊必要欄位並查看試算。
3. 交易型動作會顯示 ExecutionGrant，內容包含 Provider、時間範圍、預算／點數上限與有效期。
4. 只有會員按下核准後，平台才會提交草稿；「先不要」只會暫停或撤回授權，不會送單。

## 限制與 Demo 標示

ExecutionGrant 是一次有界授權，不等於永久授權，也不保證跨 Provider 原子交易。任何超出範圍、過期或條件改變都必須重新確認。

## 導覽 action

可前往 `assistant` 開始對話、`booking` 接手草稿或 `orders` 查看已建立的結果。

## 版本與來源

本說明對應 app version `0.1.0`；更新日期 2026-08-01。
