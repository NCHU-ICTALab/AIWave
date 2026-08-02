# 品牌與視覺規格

> 狀態：**現行有效**。此處的色彩 token 已實作於 `web/app/src/styles/main.css`，
> 並由 `tests/accessibilityBaseline.spec.ts` 驗證 WCAG AA 對比。
> 正式名稱、Logo 與合作品牌官方資產尚待補齊。
>
> 產出過程（八種 UI 方向與色票探索）已封存於 [archive/design-exploration/](archive/design-exploration/)。

## 核心資產

### 平台識別

- 平台名稱：`社區小統`（對外唯一稱呼；repo 內的 `AIWave`／`aiwave-*` 是內部代號與憑證 key，不改）
- 品牌標記：`aiwave.ico`（產品負責人 2026-08-02 提供的**自有原創圖示**：房屋輪廓＋節點狀人形，深藍單色）。
  用於瀏覽器 favicon（`web/app/public/aiwave.ico`）與畫面左上角 wordmark（`web/app/src/assets/aiwave.ico`，
  走 bundler import——`public/` 路徑在 vitest 解析不到）。**不是統一集團的 Logo，也不衍生自任何合作品牌。**
- 合作品牌：DUSKIN、7-ELEVEN、CITY CAFE、黑貓等僅以純文字名稱呈現。
- 合作品牌：DUSKIN、7-ELEVEN、CITY CAFE、黑貓等僅以純文字名稱呈現。
- 禁用：從官方簡報截取低解析 Logo、手繪仿製 Logo、把原型配色宣稱為品牌官方色。

## 輔助視覺系統

2026-07-27 改版（二）：**完全對齊 uupm.cc/demo/educational-platform（LearnHub）**，
色票與元件公式直接取自該站 CSS（chunk `059f045659212c06`）。
質感要點：奶油底（不用純白）、白卡＋**3px 深墨邊框**＋**硬偏移陰影**
（卡片 `6px 6px 0 ink, inset 0 -4px 0 10%黑`、按鈕 `4px 4px 0`，hover 位移吃掉陰影）、
粉彩磚＋emoji icon、圓角 24／16。

- Ink `#2D3748`（demo `--text`：文字＝邊框＝陰影，三位一體）
- Background `#FFF9F5`（demo `--bg-cream`）／Surface `#FFFFFF`／Surface 2 `#FDF1EC`
- CTA 綠 `#22C55E`（hover `#1FBA59`）——**只做填色**；承載文字的綠用 `#15803D`（AA）。demo 的 hover `#16A34A` 與深墨字對比不足，故微調亮度
- 粉彩磚：蜜桃 `#FDBCB4`（dark `#F5A69D`）、嬰兒藍 `#ADD8E6`、薄荷 `#98FF98`、薰衣草 `#E6E6FA`
- Muted `#5A6478`（demo `#64748B` 微降過 AA）／Line `#E2E8F0`
- Danger `#B91C1C`／Success `#15803D`

與 demo 的兩處刻意偏離（demo 本身非 AA）：綠底按鈕文字用深墨不用白
（白字 2.28:1 vs 深墨 5.26:1，且與 demo 藍底次要按鈕的深字語彙一致）；muted 微降。

## 字型

- 全站：`Nunito`（demo 的 `:root` 就只有它）→ 中文回落 `Noto Sans TC` → `Microsoft JhengHei`。
- Data／Code：`IBM Plex Mono`；無網路時回退至 `Consolas`。
- 掛載方式：`@fontsource` 自帶打包，不走 Google Fonts CDN（部署後不多外部往返，
  LINE WebView 離線也不缺字）。

## Icon

服務磚用 emoji（demo 本身就在粉彩磚裡放 emoji），glyph 定義在後端服務目錄
（`core/forms/service_catalog.py`，單一事實來源），旁邊必有文字名稱，不構成 icon-only。

## 氣質關鍵詞

- 可信
- 清楚
- 有生活溫度
- 可操作
- 跨角色一致

## 版面參考

- OPENPOINT App 服務頁只作資訊架構參考：搜尋 → 常用功能 → 活動／情境 → 分類服務。
- 不複製 OPENPOINT 綠色外框、底部導覽、品牌圖示或活動 Banner；改用本原型青綠／琥珀 token 與文字素材預留位。
- 服務名稱以官方 `raw_data/相關主檔設定.json` 八項服務，加上商城購物，共九項。
