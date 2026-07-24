# 前端與無障礙事實基線

> 核對日期：2026-07-24。用途：記錄本次前端架構與風格探索所依據的官方技術事實；產品取捨仍以 ADR 與 SRS 為準。

## Vue

- Vue 官方的 SPA 建立流程使用 Vite，並支援 Single-File Components；本專案據此採 Vue 3＋Vite。
- 來源：https://vuejs.org/guide/quick-start.html

## WCAG 2.2

- WCAG 2.2 是 W3C Recommendation，本專案選擇 AA 為 Web 驗收基線。
- AA 一般文字最低對比為 4.5:1，大字為 3:1。
- Reflow 要求垂直捲動內容可在相當於 320 CSS px 寬度呈現，而不遺失資訊或功能，必要的二維內容可例外。
- Target Size (Minimum) 的 AA 門檻為 24×24 CSS px，並有間距、等效控制項、行內文字等例外；專案另將主要操作提升為 44×44 CSS px 的產品目標。
- 來源：https://www.w3.org/TR/WCAG22/
- 來源：https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
- 來源：https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

## LINE／LIFF

- LIFF 是在 LINE 與外部瀏覽器運行的 Web 應用整合方式；頁面仍需提供標準 viewport 設定。
- Messaging API 的 URI action 可由可點擊控制項開啟網址，並可用於訊息、Flex Message 與 Rich Menu；因此導向 Web 不以 LIFF 為必要條件。
- LINE 於 2026 年公告 Android WebView 導覽區行為調整，底部內容必要時須使用 `safe-area-inset-bottom`，舊版 WebView 可採 LINE 提供的 Android fallback 變數。
- LIFF 初始化與登入屬通路能力，應與一般 Web 畫面分離；不應讓主要流程依賴 LIFF 才能顯示。
- 來源：https://developers.line.biz/en/docs/liff/developing-liff-apps/
- 來源：https://developers.line.biz/en/docs/messaging-api/actions/
- 來源：https://developers.line.biz/en/news/2026/03/24/release-liff-2-28-0/

## 統一資訊官方服務能力

> 此段只用於理解可對接的供給／平台能力，不作為前端配色、元件或品牌視覺依據，也不直接等同住戶端生活服務目錄。

- Products 分為 Martech、IDC & Security、Cloud Services、Enterprise Integration、Hardware & Software。
- Solution 涵蓋 DAM、Zero-Trust Security、Financial App Development、Automated Testing、Cross-Industry APP、Delivery & Logistics、Data Visualization & Analytics、Food Safety Solutions。
- 對本專案較直接的用途是支撐「平台整合中心／廠商能力」敘事，例如企業整合、跨產業 App、物流與資料分析；住戶端仍以原先定義的生活服務與統一體系消費服務為主。
- 來源：https://www.pic.net.tw/product/list/all
- 來源：https://www.pic.net.tw/

## OPENPOINT App 服務入口

> 此段只作為服務頁資訊架構參考，不直接複製 OPENPOINT 的品牌色、Logo、圖示或活動素材。

- App Store 官方說明將 OPENPOINT 的能力分為累積、兌換、查詢、綁定、支付、服務、集點、發票與團購；「服務」涵蓋 ibon 售票、列印、繳費、寄件、儲值、紅利、購物及生活服務。
- 官方 App 截圖採用「搜尋／常用功能／活動內容／分類服務」的垂直掃描節奏，適合作為本專案服務探索頁的行動版資訊架構參考。
- 本專案只借用資訊層級：自然語言搜尋 → 個人常用 → 情境建議 → 可操作服務分類；九項服務內容與後續流程仍以本專案官方資料、SRS 與統一服務契約為準。
- 來源：https://apps.apple.com/tw/app/%E6%9C%89openpoint%E7%9C%9F%E5%A5%BD/id1014238801
