---
id: product-help.points-and-redemption
title: 點數與折抵
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
  - title: Platform quote and points implementation
    path: api/platform_core.py
    license_or_permission: internal
---

# 點數與折抵

## 目前可用功能

競賽 Demo 使用可重置、明確標示為 Demo 的點數帳本。預約或商品流程在試算階段顯示原價、可折抵點數與應付金額；可折抵上限由平台帳本與服務規則計算，不由聊天文字決定。

## 操作步驟

1. 從「服務」選擇方案與可用時段。
2. 在試算步驟輸入要折抵的點數。
3. 確認原價、折抵與應付金額後，再決定是否送出。
4. 退款或取消時，平台會依 Demo ledger 建立沖銷紀錄。

## 限制與 Demo 標示

這是競賽展示用帳本，不代表正式 OPENPOINT 即時餘額、活動規則或品牌合作。會員只在明確確認後才會產生交易；AI 不會自行扣點。

## 導覽 action

可前往 `points` 查看會員點數，或前往 `services` 開始試算。

## 版本與來源

本說明對應 app version `0.1.0`；更新日期 2026-08-01。
