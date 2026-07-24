# 九項服務題組與報價規則

- 類型：task（AFK）
- 狀態：完成
- 完成日期：2026-07-25
- 阻擋：無

## Question

如何讓官方八項服務＋商城購物共九項服務，每項都能透過同一題組引擎完成必要填答、驗證與至少一個可追蹤下一步，同時讓價格與優惠保持確定性？

## Acceptance

- 題組定義由資料驅動，支援文字、單選、日期／時段與條件必填。
- 九項服務都有服務別題組及完成動作，不存在死卡。
- 商城購物顯示商品、優惠券、OPENPOINT 與支付方案的可重算明細。
- 清潔／修繕可建立諮詢；寄件、訂位、外送與商城可建立相應訂單。
- 確認摘要包含答案、資料用途、合作夥伴、價格與下一步。
- 驗證錯誤以文字呈現並能由鍵盤修正。
- 公開 store／repository seam 有單元測試，主流程有元件測試。

## Progress

- [x] 九項服務目錄與選取狀態
- [x] 商城購物簡化折扣
- [x] 題組 schema 與驗證器
- [x] 九項 fixture 題組
- [x] 動態表單 UI
- [x] 服務別 fulfillment 與確認摘要
- [x] 測試、型別、建置

## Resolution

- 前端題組沿用官方題型代碼；本票所需 type 1、2、3、9 由同一動態元件呈現，完整 type 1–10 的對話核心仍由既有 `core/forms/` 負責。
- `validateServiceAnswers` 處理條件可見性、必填、選項、數量及可注入日期範圍。
- `calculateServiceQuote` 是唯一價格來源；優惠券、點數與支付加碼均由答案決定。
- store 提供 `createInquiry`、`createReservation`、`createShipment`、`createOrder` 與安全 dispatch，避免所有服務假裝成同一訂單。
- 確認摘要顯示題組答案、資料用途、合作夥伴與應付金額。
- Spec／Standards 初審發現 6 項問題，修正後複核全部關閉。
- 驗證：6 個測試檔、26 項測試、typecheck、production build 全數通過。
