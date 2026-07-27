# 品牌與視覺規格

> 狀態：**現行有效**。此處的色彩 token 已實作於 `web/app/src/styles/main.css`，
> 並由 `tests/accessibilityBaseline.spec.ts` 驗證 WCAG AA 對比。
> 正式名稱、Logo 與合作品牌官方資產尚待補齊。
>
> 產出過程（八種 UI 方向與色票探索）已封存於 [archive/design-exploration/](archive/design-exploration/)。

## 核心資產

### 平台識別

- 平台名稱：`生活 AI 管家`（暫名）
- Logo：尚未提供；原型僅使用文字標籤「生活 AI 管家」與「名稱待定」，不仿製 Logo。
- 合作品牌：DUSKIN、7-ELEVEN、CITY CAFE、黑貓等僅以純文字名稱呈現。
- 禁用：從官方簡報截取低解析 Logo、手繪仿製 Logo、把原型配色宣稱為品牌官方色。

## 輔助視覺系統

2026-07-27 改版：採 ui-ux-pro-max 的 **Claymorphism 教育平台**方向
（styles.csv「Claymorphism」＋ colors.csv「Educational App」），取代先前的青綠琥珀。
質感要點：靛白背景（不用純白）、粗邊框 3px、圓角 16–28px、雙層陰影
（外柔靛色調＋內上高光）、按鈕底座陰影與按壓回彈。

- Primary：`#4F46E5`（deep `#3730A3` 作按鈕底座）
- Primary soft：`#E0E7FF`
- Accent：`#C2410C`（skill 原表 `#EA580C` 當白字底色僅 3.6:1，降為 orange-700 過 4.5:1；
  更亮的 `#F97316` 只做漸層等裝飾，不承載文字）
- Accent soft：`#FFEDD5`／Accent ink：`#9A3412`
- Background：`#EEF2FF`
- Surface：`#FFFFFF`／Surface 2：`#E4E9FC`
- Ink：`#1E1B4B`
- Muted：`#475569`
- Border：`#C7D2FE`
- Danger：`#B91C1C`／Success：`#15803D`
- Shadow：靛色調柔陰影（`rgb(79 70 229 / …)`）＋內上白高光，構成黏土的 double shadow。

## 字型

- Display：`Nunito`（800/900，圓端點）→ 中文回落 `Noto Sans TC`。
- Body：`DM Sans` → `Noto Sans TC`；無網路時回退至 `Microsoft JhengHei`。
- Data／Code：`IBM Plex Mono`；無網路時回退至 `Consolas`。
- 掛載方式：`@fontsource` 自帶打包，不走 Google Fonts CDN（部署後不多外部往返，
  LINE WebView 離線也不缺字）。

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
