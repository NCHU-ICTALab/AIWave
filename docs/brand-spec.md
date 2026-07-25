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

以下 token 來自已選定的 `08 柔和指揮台＋07 青綠琥珀` UI 方向，只代表本產品原型：

- Primary：`#0E5E6F`
- Primary soft：`#E1ECEF`
- Accent：`#C77400`
- Accent soft：`#FBF1DF`
- Background：`#F4F6F8`
- Surface：`#FFFFFF`
- Ink：`#17242B`
- Muted：`#4A5A63`
- Border：`#C8D1D6`
- Danger：`#A33B2E`
- Shadow：中性黑低透明度，不使用彩色陰影。

## 字型

- Display／Body：`Noto Sans TC`；無網路時回退至 `Microsoft JhengHei`。
- Data／Code：`IBM Plex Mono`；無網路時回退至 `Consolas`。

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
