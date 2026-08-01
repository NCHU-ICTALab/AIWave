# AIWave M4 HTML 原型(設計審批用)

> 依 [spec 15 §9.2](../../../docs/specs/15-agreed-product-and-platform-direction.md):正式改寫 Vue 前,
> 先交付 HTML 方向由產品負責人核准。**本目錄是原型,不是實作**;原型內所有狀態僅存於瀏覽器
> localStorage,正式版一律走 Platform API。未經核准不整合、不重寫正式 Vue。

## 怎麼看

雙擊開啟 [index.html](index.html)(審閱目錄),或直接開任一頁。無需伺服器、無外部資源。
建議同時用 1440px 視窗與 390px(手機模擬)各走一遍;全站支援鍵盤操作與 `prefers-reduced-motion`。

- **方向 A**(主提案):沿用 `design-system/aiwave/MASTER.md` 已核准 tokens——奶油底、深墨粗框、
  硬偏移陰影、綠色主行動。完整涵蓋 goal 要求的 11 項。
- **方向 B**(對照):`variant-b/`,參考 `aws summit taipei` HULLWATCH 得獎前端——白底細線、
  等寬數字、編號導覽、高資訊密度。做公開首頁與 Dashboard 兩頁供比較或混搭。

## 設計假設(請審閱時確認或推翻)

1. **主導覽五項**照 spec 15 §9.1:首頁/點數兌換/AI/服務/會員中心;行事曆由首頁卡片進入。
   為了讓導覽無死連結,補了 points/ai/member 三個輔助頁;AI 頁是 M8 誠實佔位。
2. **示範閉環選「住・修繕」做最深**(spec §2.2 P0「住做最深」):王子水電 5 步 TaskDraft
   (據點→方案/人員→真實時段→表單→試算確認),含草稿自動儲存、重新整理續填、重複提交保護。
3. **品牌只用 fake upstream 既有核准 allowlist**(`fake_upstreams/vendor_seed.py`):王子水電、
   太子物業、DUSKIN 樂清、黑貓宅急便、7-ELEVEN 交貨便/賣貨便/線上購物中心、foodomo、
   EZTABLE 簡單桌、康是美。價格沿用 seed 基準價。
4. **「樂」場景沒有核准品牌**→ 分類顯示但標「合作品牌洽談中」、入口 disabled,不虛構。
5. **醫**只做處方箋「辨識展示 + 康是美藥局連結」示意,OCR 結果需逐欄人工確認,
   並帶免責:不提供診斷或用藥建議。
6. Demo 人物:林小圓(會員)、王師傅(王子水電)、陳主委(幸福社區)、aiwave-admin;
   展示日期 2026-07-30。

## 進 Vue 之前,需要你提供的輸入

- 六大場景的**正式廠商名單**與各場景代表服務的**參考表單/網址**(欄位、價目、時段規則)。
- 可用的**品牌素材**(logo、是否允許在 Demo 使用品牌名之外的視覺元素)。
- 方向選擇:A、B,或混搭(例如會員端用 A、Provider/admin 後台用 B 的密度)。
- 「樂」與「行・叫車」的品牌決定(目前行場景以宅配/寄件為代表)。

## 檔案清單

| 頁 | 檔案 |
| --- | --- |
| 審閱目錄 | `index.html` |
| 公開首頁 / 登入 | `home-public.html`、`login.html` |
| Dashboard | `dashboard.html` |
| 服務探索 / 詳情 | `services.html`、`service-detail.html` |
| 表單・店家・時段(TaskDraft) | `booking-repair.html` |
| 訂單詳情與時間軸 | `order-detail.html` |
| Calendar | `calendar.html` |
| Group / Community | `group.html`、`community.html`、`community-manage.html` |
| Provider Workspace | `provider.html` |
| aiwave-admin | `admin.html` |
| 輔助(導覽完整性) | `points.html`、`ai.html`、`member.html` |
| 方向 B 對照 | `variant-b/home-public.html`、`variant-b/dashboard.html` |
| 共用資產 | `assets/aiwave.css`、`assets/aiwave.js`、`variant-b/assets/variant-b.css` |
