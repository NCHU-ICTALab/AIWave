---
id: product-help.booking-and-cancellation
title: 預約、改期、取消與退款
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
  - title: Platform fulfillment and booking routes
    path: api/platform_core.py
    license_or_permission: internal
---

# 預約、改期、取消與退款

## 目前可用功能

服務頁會先列出核准目錄中的 Provider、Offering 與可用時段。選定後進入 TaskDraft 預約精靈；送出才會建立 Booking 或 CommerceOrder。

## 操作步驟

- 服務頁 → 選 Provider／方案／時段 → 填寫必要欄位 → 試算 → 確認送出。
- 可從「我的訂單」查看 StatusEvent 時間軸。
- 支援的訂單可提出改期申請；改期會重新查詢時段，不直接覆寫 Provider 的既有預約。
- 會員可以在訂單詳情提出取消；Demo upstream 回應後，平台同步狀態、通知、行事曆與退款／點數沖銷結果。

## 限制與 Demo 標示

取消費率與正式 Provider 規則尚待產品確認；競賽 Demo 不把 seed 或 fake upstream 說成正式合作。若 Provider 回應失敗，畫面會顯示可重試或等待狀態，不假裝完成。

## 導覽 action

可前往 `services` 開始預約、`booking` 填寫草稿或 `orders` 查看狀態。

## 版本與來源

本說明對應 app version `0.1.0`；更新日期 2026-08-01。
