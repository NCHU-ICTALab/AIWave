# AIWave 文件索引

> 現行基線日期：2026-07-28。若文件互相衝突，依序以新 ADR、00／07／08／14、06 SRS、其餘舊規格為準。封存區不是實作依據。

## 必先閱讀

1. [領域詞彙](../CONTEXT.md)
2. [競賽策略與奪冠證據](strategy/competition-winning-strategy.md)
3. [00 產品定位與情境](specs/00-product-and-scenarios.md)
4. [07 競賽 Demo 垂直切片](specs/07-demo-vertical-slice.md)
5. [08 會員產品體驗與 AI 互動](specs/08-product-experience.md)
6. [14 Vendor API、fake server 與 Client](specs/14-vendor-api-contract.md)

## 現行規格

| # | 文件 | 內容 |
| --- | --- | --- |
| 00 | [產品定位與情境](specs/00-product-and-scenarios.md) | 會員優先定位、產品邊界、資訊架構、招牌能力與 Hero |
| 01 | [系統架構](specs/01-system-architecture.md) | 分層、時序、部署與 Agent 架構 |
| 02 | [資料模型](specs/02-data-model.md) | 官方資料、平台擴充實體與 seed |
| 03 | [題組引擎](specs/03-form-engine.md) | 官方題型、跳題、填答及落地流程 |
| 04 | [MCP 與統一 API](specs/04-mcp-and-api.md) | API 與 MCP 能力藍圖；server 拆分以 ADR-0017 為準 |
| 05 | [Web 模組](specs/05-erp-modules.md) | 會員、群組／營運、廠商與平台模組；角色入口以 ADR-0015 為準 |
| 06 | [SRS](specs/06-system-requirements.md) | 正式功能與非功能需求；產品優先序以 00／07 為準 |
| 07 | [競賽 Demo](specs/07-demo-vertical-slice.md) | 單一 Hero、五分鐘節奏、失敗橋段與 P0 驗收 |
| 08 | [產品體驗](specs/08-product-experience.md) | 首頁、點數、全頁 AI、服務、訂單、會員中心與 WCAG |
| 09 | [AWS 架構](specs/09-aws-architecture.md) | 競賽部署、速度與環境契約 |
| 10 | [三條 Agent 流程](specs/10-three-agent-vertical-flows.md) | Agent 垂直流程；Hero 選擇以 07 為準 |
| 11 | [訂單異常與客服](specs/11-order-exception-support.md) | 訂單例外、工單與回復 |
| 12 | [群組聯合服務](specs/12-community-joint-service.md) | 社區聯合服務；現為 Group 延伸能力，不是產品主體 |
| 13 | [Retail fake upstream](specs/13-fake-upstream-server.md) | 既有零售查詢 connector 與韌性測試 |
| 14 | [Vendor API 生態](specs/14-vendor-api-contract.md) | 廠商 OpenAPI、獨立 server、Client seam、seed 與切換 |

## 現行 ADR

| # | 決策 |
| --- | --- |
| [0001](adr/0001-groupbuy-per-household-orders.md) | 群組團購每次參與產生個人訂單 |
| [0002](adr/0002-shared-form-engine.md) | 多流程共用官方題型引擎 |
| [0003](adr/0003-scope-as-core-attribute.md) | individual／group scope 是核心屬性 |
| [0004](adr/0004-local-first-aws-portable.md) | 地端優先、AWS 可移植 |
| [0007](adr/0007-three-vendor-onboarding-modes.md) | 標準、Adapter、工作台三種廠商接入 |
| [0008](adr/0008-permission-bound-operations-copilot.md) | AI 沿用角色權限並對高影響操作要求確認 |
| [0009](adr/0009-separate-official-service-source-and-partner-vendor.md) | 官方服務來源與合作廠商分開建模 |
| [0011](adr/0011-explainable-hybrid-recommendation.md) | 可重算規則＋AI 理解與解釋的混合推薦 |
| [0012](adr/0012-consented-minimal-personalization-data.md) | 個人化明確同意、最小保存、群組隔離 |
| [0013](adr/0013-vue-responsive-accessible-line-ready-frontend.md) | Vue、RWD、WCAG 2.2 AA、LINE safe area |
| [0014](adr/0014-line-deep-link-first-liff-optional.md) | Web 深層連結優先，LIFF 選配 |
| [0015](adr/0015-role-separated-entry-points.md) | 會員、廠商及平台入口分離 |
| [0017](adr/0017-llm-plans-rules-execute.md) | LLM 規劃、規則執行，能力即 MCP tool |
| [0018](adr/0018-aws-sized-for-speed.md) | AWS 以 Demo 體驗速度優先 |
| [0019](adr/0019-member-first-life-task-orchestration.md) | 會員優先、生活任務編排、群組槓桿 |
| [0020](adr/0020-member-navigation-and-dedicated-ai.md) | 資訊總覽首頁＋獨立全頁 AI＋五頁籤 |
| [0021](adr/0021-vendor-api-contract-and-fake-server.md) | OpenAPI＋獨立 fake server＋可替換 VendorClient |

被 0019／0020 取代的 ADR 已移至[日期化封存區](archive/superseded/2026-07-28/)。

## 其他文件

- [前端與 WCAG 事實基線](product-facts.md)
- [2025 優勝作品與智生活研究](research/2025-winners-and-smartdaily.md)
- [品牌與視覺](brand-spec.md)
- [工作管理](work-management/)
- [封存索引](archive/README.md)

## 現行決策速查

- 主要行為者是會員；家庭、情侶、宿舍與社區是不同 `group_type`。
- 差異化是跨點數、廠商、群組的生活任務編排，不是第二個 OPENPOINT 或智生活。
- 會員頁籤：首頁、點數兌換、AI、服務、會員中心。
- 首頁是資訊總覽並保留輕量 AI；完整聊天在獨立 AI 頁。
- AI 讀取／導覽可直接做；設定／表單先預覽；交易／兌換／下單／取消須確認。
- 廠商採 OpenAPI 3.0、獨立 fake server、`VendorClient` seam，由平台後端 `VENDOR_MODE` 切換。
- 第一版 vendor seed：8–12 品牌、約 30 據點、約 120 案件／報價，使用台灣中文情境及可驗證品牌 allowlist。
- Web-first；LINE Bot 與語音在核心 Web 完成後延伸。
