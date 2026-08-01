# AIWave 文件索引

> 現行基線日期：2026-07-30。若文件互相衝突，以「15 產品與平台定案基線」為最高依據，其次是 2026-07-30 後新增的 ADR，再其次才是支援規格。封存文件與原路徑的「已封存」指引不是實作依據。

## 必先閱讀

1. [15 產品與平台定案基線](specs/15-agreed-product-and-platform-direction.md)
2. [領域詞彙](../CONTEXT.md)
3. [M0 程式碼盤點與保護基線](status/2026-07-30-m0-code-audit.md)
4. [2026-07-30 現況、完成證據與後續差距](status/2026-07-30-current-state-and-gap.md)
5. [M0～M3 測試與操作手冊](testing/demo-runbook.md)
6. [競賽策略與奪冠證據](strategy/competition-winning-strategy.md)
7. [題組引擎](specs/03-form-engine.md)

## 現行規格

| # | 文件 | 狀態與用途 |
| --- | --- | --- |
| 03 | [題組引擎](specs/03-form-engine.md) | 官方題型、跳題、填答及驗證的現行基礎 |
| 09 | [AWS 架構](specs/09-aws-architecture.md) | 探索性部署文件；含官方競賽環境規範與限制（2026-07-22 公告）的收錄與影響分析 |
| 11 | [訂單異常與客服](specs/11-order-exception-support.md) | 例外、工單與復原的支援規格 |
| 13 | [Retail fake upstream](specs/13-fake-upstream-server.md) | 既有零售查詢 connector 參考；現行 Partner fake 另見 fake upstream 手冊 |
| 15 | [產品與平台定案基線](specs/15-agreed-product-and-platform-direction.md) | **最高依據**：產品、角色、服務閉環、Agent、MCP、Partner API、Web、測試與順序 |

以下原路徑只保留「已封存」指引，完整舊版位於日期化封存區：00、01、02、04、05、06、07、08、10、12、14。

## 現行 ADR

| # | 決策 | 與 15 的關係 |
| --- | --- | --- |
| [0001](adr/0001-groupbuy-per-household-orders.md) | 群組團購每次參與產生個人訂單 | 保留，但 Group 不再有家庭／朋友 type |
| [0002](adr/0002-shared-form-engine.md) | 多流程共用官方題型引擎 | 保留 |
| [0004](adr/0004-local-first-aws-portable.md) | 地端優先、AWS 可移植 | 保留 |
| [0007](adr/0007-three-vendor-onboarding-modes.md) | 標準、Adapter、工作台三種合作方接入 | 保留；統一稱 ProviderConnector |
| [0008](adr/0008-permission-bound-operations-copilot.md) | Agent 沿用角色權限並對高影響操作要求確認 | 保留；確認模型擴充為 ExecutionGrant |
| [0009](adr/0009-separate-official-service-source-and-partner-vendor.md) | 官方服務來源與合作服務提供者分開建模 | 保留 |
| [0011](adr/0011-explainable-hybrid-recommendation.md) | 可重算規則＋AI 理解與解釋 | 保留；推薦分成任務／個人化／推廣 |
| [0012](adr/0012-consented-minimal-personalization-data.md) | 個人化明確同意與最小保存 | 保留 |
| [0013](adr/0013-vue-responsive-accessible-line-ready-frontend.md) | Vue、RWD、WCAG 2.2 AA | Web／WCAG 保留；LINE 延後 |
| [0014](adr/0014-line-deep-link-first-liff-optional.md) | Web 深層連結優先、LIFF 選配 | 延後，不是目前實作要求 |
| [0017](adr/0017-llm-plans-rules-execute.md) | LLM 規劃、規則執行 | 核心保留；MCP 架構以 15 為準 |
| [0018](adr/0018-aws-sized-for-speed.md) | AWS 以 Demo 體驗速度優先 | 僅供未來部署評估，不限制 Learner Lab 探索 |
| [0020](adr/0020-member-navigation-and-dedicated-ai.md) | 資訊總覽首頁、獨立 AI、五頁籤 | 保留；另加入共用 Agent 側欄 |
| [0021](adr/0021-vendor-api-contract-and-fake-server.md) | OpenAPI、獨立 fake server、可替換 client | 核心保留；命名與 reset 依 15 |

ADR-0003、0015、0019 已於 2026-07-30 封存；原路徑保留取代說明。

## 現行決策速查

- 產品以個人會員為主；`Group` 是使用者自建共享集合，`Community` 是獨立真實組織。
- 一個 Account 可有多個 RoleMembership，透過明確 Workspace 切換；Demo 另有固定快速登入人物。
- 手動流程先完整；Agent 與手動 UI 共用 TaskDraft，使用者每一步都能接手修改。
- Agent 可自主規劃與選工具；交易只在 ExecutionGrant 範圍內執行，確定性規則掌管時間、金額、權限與狀態。
- Provider 不做黑箱自動媒合；平台可排序建議，但使用者從核准店家、方案、資源與真實時段選擇。
- Web、Agent、合作方工作台與 MCP 共用訂單、StatusEvent、點數、通知和行事曆資料。
- MCP 是讓遠端 AI 操作 AIWave 的 Streamable HTTP Gateway，只呼叫 Platform API，不直連 DB。
- Partner API 以 OpenAPI 3.0 為真相來源；獨立 fake upstream 可 seed、reset、延遲與故障注入。
- 公開首頁和登入後介面須先提交兩組 HTML 方向，取得核准後才改正式 Vue。
- Web-first；醫療與語音 P2，LINE／Discord 與正式 AWS 延後。

## 其他文件

- [前端與 WCAG 事實基線](product-facts.md)
- [M0 程式碼盤點與保護基線](status/2026-07-30-m0-code-audit.md)
- [現況、完成證據與後續差距](status/2026-07-30-current-state-and-gap.md)
- [2025 優勝作品與智生活研究](research/2025-winners-and-smartdaily.md)
- [品牌與視覺](brand-spec.md)
- [現行工作管理入口](work-management/README.md)
- [M0～M3 測試與操作手冊](testing/demo-runbook.md)
- [封存索引](archive/README.md)
