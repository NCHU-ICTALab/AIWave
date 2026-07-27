# 文件索引：AI 生活服務平台

- 詞彙表：[../CONTEXT.md](../CONTEXT.md)（改動領域概念前先讀這份）
- 品牌與視覺：[brand-spec.md](brand-spec.md)（色彩 token 現行有效）
- 工作追蹤：[work-management/](work-management/)（工作票與驗收條件）
- 封存：[archive/](archive/)（早期提案、設計探索——**歷史參考，非現行依據**）

## 核心規格（必讀，9 份）

| # | 文件 | 內容 | 讀者 |
| --- | --- | --- | --- |
| 00 | [產品與情境](specs/00-product-and-scenarios.md) | 定位、Hero Demo、今日生活中心、場景庫、MOT 與 Demo 腳本 | 全員／簡報 |
| 01 | [系統架構](specs/01-system-architecture.md) | 分層架構、訊息時序、地端優先可移植、多 Agent 升級版 | 全員 |
| 02 | [資料模型](specs/02-data-model.md) | ERD（官方表＋擴充表）、資料字典、seed 計畫 | 後端 |
| 03 | [題組引擎](specs/03-form-engine.md) | 題型、跳題、引導狀態機、三份題組定義 | 後端／Agent |
| 04 | [MCP 與統一 API](specs/04-mcp-and-api.md) | 6 個 MCP server 工具＋其下模擬 REST API＋事件推播 | Agent／後端 |
| 05 | [Web 工作區模組](specs/05-erp-modules.md) | 住戶、社區營運、合作廠商、平台整合四工作區與權限 | 前端／後端 |
| 06 | [系統需求規格書 SRS](specs/06-system-requirements.md) | 正式需求基線（FR 編號＋優先級）、NFR、資料需求、建置階段、待議 | 全員 |
| 07 | [競賽 Demo 垂直切片](specs/07-demo-vertical-slice.md) | 兩條主線、五分鐘腳本、六個主畫面、API／AI／Mock 邊界與 P0 驗收 | 全員／前後端 |
| 08 | [產品體驗](specs/08-product-experience.md) | **從「能 demo」到「能用」**：demo 化痕跡清單、首次使用旅程、零狀態、三項待決策 | 全員／前端 |

> 建議閱讀順序：00 →（決策脈絡看下方 ADR）→ 06 SRS 掌握全貌 → 07 Demo 垂直切片掌握交付範圍 → 依角色深入 01–05。
>
> ⚠️ **08 是對 05／07 的重要修正**：那兩份把四工作區與 demo 動線視為既定；08 指出這正是
> 「使用者不知道怎麼用」的來源。三項分岔決定後，05／07 需一併回填。

## 架構決策紀錄（adr/）

| # | 決策 |
| --- | --- |
| [0001](adr/0001-groupbuy-per-household-orders.md) | 每戶跟團＝一筆 order_type 07 訂單 |
| [0002](adr/0002-shared-form-engine.md) | 修繕、跟團、公設預約三流程共用題組引擎 |
| [0003](adr/0003-scope-as-core-attribute.md) | 「範圍」做成核心屬性，個人／家庭／社區共用一套機制 |
| [0004](adr/0004-local-first-aws-portable.md) | 地端優先開發，設計為可平滑移植 AWS |
| [0005](adr/0005-community-core-personal-extension.md) | 社區服務整合為核心場景，個人生活能力分階段延伸 |
| [0006](adr/0006-single-web-platform-four-workspaces.md) | 單一 RWD 平台承載四個角色工作區 |
| [0007](adr/0007-three-vendor-onboarding-modes.md) | 廠商以三種模式接入統一服務契約 |
| [0008](adr/0008-permission-bound-operations-copilot.md) | AI 採權限受控且確認後執行的營運 Copilot |
| [0009](adr/0009-separate-official-service-source-and-partner-vendor.md) | 官方服務來源與實際合作廠商分離建模 |
| [0010](adr/0010-hero-personal-hub-and-service-breadth.md) | Hero、今日生活中心與廣服務目錄構成競賽版展示 |
| [0011](adr/0011-explainable-hybrid-recommendation.md) | 推薦採可重算特徵計分與 AI 理解/解釋的混合管線 |
| [0012](adr/0012-consented-minimal-personalization-data.md) | 個人化採明確同意、最小保存與群組資料隔離 |
| [0013](adr/0013-vue-responsive-accessible-line-ready-frontend.md) | Vue 前端從第一天落實 RWD、WCAG 2.2 AA 與 LINE WebView 相容性 |
| [0014](adr/0014-line-deep-link-first-liff-optional.md) | LINE 以 Web 深層連結為預設，LIFF 為選配增強層 |
| [0015](adr/0015-role-separated-entry-points.md) | 角色分離入口與登入身分，取代工作區切換器（**修正 0006**） |
| [0016](adr/0016-conversation-first-home.md) | 住戶首頁的主動作是自然語言輸入，不是服務目錄 |
| [0017](adr/0017-llm-plans-rules-execute.md) | LLM 規劃、規則執行；能力即 MCP 工具（**取代 04 的 6-server 拆法**） |
| [0018](adr/0018-aws-sized-for-speed.md) | AWS 以體驗速度為第一優先、規格從寬（**修正 0004 的成本論述**） |

## 已定案速查

- 產品重心：社區服務整合為核心場景，個人服務為所有人可用的基線
- Web 主展示：Hero 為 DUSKIN 社區冷氣聯合清洗；第二主線為個人「今日生活中心」
- 服務廣度：官方 8 項＋商城購物共 9 項皆可操作；DUSKIN、黑貓、foodomo、EZTABLE、7-ELEVEN 深度整合
- 超商生態：認真做，有界種子 ~15 門市 × ~40 SKU、真實 7-11/OPENPOINT/ibon 品牌情境
- 生活任務：預填就緒＋逐項「確認即執行」可微調；純實體轉提醒
- 點數/優惠券：中度真帳本（可真算）；發票展示層
- 推薦：行為特徵與情境先產生可重算分數，AI 依證據說明；以「不感興趣／復原」逐步調教偏好
- 服務媒合：官方服務來源與實際合作廠商分離；品牌優先採官方素材出現的統一體系業者，做多廠商輕量比較
- 建置階段：共用閉環 → Hero＋廠商 → 今日生活中心 → 服務廣度 → 家庭與延伸情境
- Demo：Hero＋今日生活中心＋平台接入證明；其餘需求保留為場景庫與分期功能
- 地端優先、可移植 AWS（[ADR-0004](adr/0004-local-first-aws-portable.md)）
- MCP：厚 MCP、按域拆 6 server（[04](specs/04-mcp-and-api.md)）
- **技術棧**：Python 後端（Strands Agent＋FastMCP）＋Vue 3/Vite 前端＋Bedrock Claude＋PostgreSQL；地端 Docker（[01 技術棧/Repo](specs/01-system-architecture.md)）
- **前端品質基線**：同一套元件同時通過 RWD、WCAG 2.2 AA 與 LINE WebView safe area；桌機、手機與 LINE 內開啟不是三套前端
- **LINE 延伸策略**：AI Bot 依意圖回傳可點擊的 Web 深層連結；LIFF 不阻塞主流程，只在需要 LINE Login、聊天室或視窗控制時加入
- 服務媒合為**官方核心（P0）**；諮詢單＝官方「留資表單」；題型全用官方 `pms_form_topic.type`（不自訂）
- 詞彙：行為指紋（身分解析）≠ 行為軌跡（行為序列）

## 仍暫緩（見 [SRS §6.5](specs/06-system-requirements.md)）

1. 服務層最終形態：待參考 MCP 官方範例庫後定（repo 已預留 `core/`）
2. AWS 基礎架構細節（資料庫、runtime、Gateway、推播排程）→ 定後補架構圖於 [01](specs/01-system-architecture.md)
3. 多 Agent 升級（可能不採用；條件：單一 Agent 核心閉環 e2e 通過）
