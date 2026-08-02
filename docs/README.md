# AIWave 文件索引

> 現行基線日期：2026-08-01。若文件互相衝突，以 [15 產品與平台定案基線](specs/15-agreed-product-and-platform-direction.md) 為最高依據；v4 主動生活管家與自然 Agent 的具體規則分別以 [16](specs/16-proactive-life-butler-and-commercial-loop.md) 與 [17](specs/17-conversational-agent-session-and-llm-wiki.md) 為準。封存文件不是實作依據，寫入規格也不代表功能已完成。

## 必先閱讀

0. [**功能總覽（現在有哪些功能）**](feature-inventory.md) — 從這裡開始：功能 → 程式碼 → 端點 → 測試的對照表，以及資料真實性分級與明確「還沒有」的清單
1. [15 產品與平台定案基線](specs/15-agreed-product-and-platform-direction.md)
2. [16 主動生活管家、在地生活圈與商業閉環](specs/16-proactive-life-butler-and-commercial-loop.md)
3. [17 自然對話 Agent、Session 與 LLM Wiki](specs/17-conversational-agent-session-and-llm-wiki.md)
4. [領域詞彙](../CONTEXT.md)
5. [現況、完成證據與後續差距](status/2026-07-30-current-state-and-gap.md)
6. [競賽策略與奪冠證據](strategy/competition-winning-strategy.md)
7. [v4 五分鐘 Demo runbook](testing/v4-five-minute-demo-runbook.md)
8. [LLM Wiki 內容規範](knowledge/README.md)

## 現行規格

| # | 文件 | 狀態與用途 |
| --- | --- | --- |
| 03 | [題組引擎](specs/03-form-engine.md) | 官方題型、跳題、填答及驗證的現行基礎 |
| 09 | [AWS 架構](specs/09-aws-architecture.md) | 探索性部署文件；記錄競賽環境規範與限制 |
| 11 | [訂單異常與客服](specs/11-order-exception-support.md) | 例外、工單與復原的支援規格 |
| 13 | [Retail fake upstream](specs/13-fake-upstream-server.md) | 既有零售 connector 參考 |
| 15 | [產品與平台定案基線](specs/15-agreed-product-and-platform-direction.md) | **最高依據**：產品、角色、服務閉環、Agent、Provider、Web 與順序 |
| 16 | [主動生活管家、在地生活圈與商業閉環](specs/16-proactive-life-butler-and-commercial-loop.md) | v4 Demo-first 功能、證據邊界、生活指南、點數與成功服務費 |
| 17 | [自然對話 Agent、Session 與 LLM Wiki](specs/17-conversational-agent-session-and-llm-wiki.md) | 多輪 Agent、兩階段工具回合、Session 與 Wiki 的詳細設計 |

以下原路徑只保留「已封存」指引，完整舊版位於日期化封存區：00、01、02、04、05、06、07、08、10、12、14。

## Demo 與驗收

- [M0～M3 測試與操作手冊](testing/demo-runbook.md)：只證明既有里程碑與現行程式。
- [Demo 影片錄製：九幕分鏡與自動駕駛](testing/demo-video-recording.md)：現行錄影腳本，搭配 `web/app/tools/demo-drive.mjs`；**取代 v4 runbook §3 作為錄影用逐秒腳本**。
- [v4 五分鐘 Demo runbook](testing/v4-five-minute-demo-runbook.md)：可執行的內部主線、外部 gate、預演檢查與備援；未通過的人工／外部項目會明確停在 blocker。**§3 逐秒腳本已過時**（舊主線），其餘章節仍有效。
- [v4 驗收矩陣](testing/v4-acceptance-matrix.md)：Agent、Wiki、生活圈、關懷、任務包、成果與前端的可失敗測試入口。
- [前端與 WCAG 事實基線](product-facts.md)。

## LLM Wiki

- [內容格式、治理與載入規則](knowledge/README.md)。
- `knowledge/life-guides/`：中元、颱風、搬家／入厝等生活指南；中元有明確標示的內部 Demo 版本，正式／授權內容仍須逐篇建立。
- `knowledge/product-help/`：點數、預約／取消、任務、通知／行事曆及生活圈 FAQ；已發布文章只能描述實際發布功能，生活圈文章仍待地理資料人工檢查。

沒有來源或尚未與實際版本核對的文章不得標記 `published`；目前已發布的是可由現行程式與測試核對的 product-help，以及明確標示為內部 Demo 的中元指南。

## 現行 ADR

| # | 決策 | 現行解讀 |
| --- | --- | --- |
| [0001](adr/0001-groupbuy-per-household-orders.md) | 群組團購每次參與產生個人訂單 | Group 不再有家庭／朋友 type |
| [0002](adr/0002-shared-form-engine.md) | 多流程共用官方題型引擎 | 保留 |
| [0004](adr/0004-local-first-aws-portable.md) | 地端優先、AWS 可移植 | 保留 |
| [0007](adr/0007-three-vendor-onboarding-modes.md) | 標準、Adapter、工作台三種接入 | 統一為 ProviderConnector |
| [0008](adr/0008-permission-bound-operations-copilot.md) | 高影響操作要求確認 | 擴充為 ExecutionGrant |
| [0009](adr/0009-separate-official-service-source-and-partner-vendor.md) | 官方服務來源與 Provider 分開 | 保留 |
| [0011](adr/0011-explainable-hybrid-recommendation.md) | 規則＋AI 理解與解釋 | facts 以權威卡片呈現 |
| [0012](adr/0012-consented-minimal-personalization-data.md) | 個人化明確同意與最小保存 | 擴及主動關懷與定位 |
| [0013](adr/0013-vue-responsive-accessible-line-ready-frontend.md) | Vue、RWD、WCAG 2.2 AA | Web／WCAG 保留，LINE 延後 |
| [0014](adr/0014-line-deep-link-first-liff-optional.md) | Web 深層連結優先 | 延後 |
| [0017](adr/0017-llm-plans-rules-execute.md) | LLM 規劃、規則執行 | 保留並擴充成自然對話＋兩階段工具回合 |
| [0018](adr/0018-aws-sized-for-speed.md) | AWS 以 Demo 體驗速度優先 | 供未來部署評估 |
| [0020](adr/0020-member-navigation-and-dedicated-ai.md) | 資訊總覽首頁、獨立 AI | 加入 Session 歷史與共用側欄 |
| [0021](adr/0021-vendor-api-contract-and-fake-server.md) | OpenAPI、獨立 fake server | 保留 |

## 現行決策速查

- 會員是唯一授權主體；受益人與服務地點分開，不建立家庭共同帳號。
- 手動流程先完整；Agent 與手動 UI 共用 TaskDraft。
- LLM 主導自然對話、上下文、規劃與 grounded 解釋；確定性平台掌管 facts 與副作用。
- Conversation Session 可新建、重開、重命名及封存；新對話不刪除正式任務。
- 生活圈分成會員前往的時間可達範圍與 Provider 到府服務範圍。
- 生活指南與產品 FAQ 是兩個隔離 Wiki；競賽版小語料全量 context，不先建向量庫。
- 推播先提供生活價值，會員主動開啟後才進入協助式商務。
- 任務包逐項可編輯，最後一次有界授權；跨 Provider 逐項執行。
- 點數折抵、活動回饋、生活成果、成就提示與 Provider 費用各自分開。
- 北極星指標是生活任務完成率。

## 架構與部署

- [AWS 正式環境架構](architecture/aws-production-architecture.md)（另有[圖解版](architecture/aws-production-architecture.html)）：`infra/` CloudFormation 對應的目標架構。
- [v4 關懷送達政策](architecture/v4-care-delivery-policy.md)：quiet／balanced／caring 三檔、頻率上限與安靜時段的判定規則，對應 `core/proactive_care/policy.py`。

## 其他文件

- [2026-08-01 初步提案](strategy/2026-08-01-preliminary-proposal.md)
- [競賽策略與奪冠證據](strategy/competition-winning-strategy.md)
- [廠商名單與代表性表單](廠商and表單.md)：產品負責人提供的統一集團官方名單，`fake_upstreams/partner_seed.py` 的品牌唯一依據
- [品牌與視覺](brand-spec.md)
- [M0 程式碼盤點與保護基線](status/2026-07-30-m0-code-audit.md)
- [現況、完成證據與後續差距](status/2026-07-30-current-state-and-gap.md)
- [2025 優勝作品與智生活研究](research/2025-winners-and-smartdaily.md)
- [現行工作管理入口](work-management/README.md)
- [封存索引](archive/README.md)
