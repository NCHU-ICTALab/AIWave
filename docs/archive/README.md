# 封存區

這裡放**已被取代、但仍有參考價值**的文件與原型。它們記錄了「我們是怎麼走到現在這個
設計的」，但**不再是有效規格**——實作請以 [docs/README.md](../README.md) 索引的現行文件為準。

> 最近封存日期：2026-07-30

## 內容

| 項目 | 是什麼 | 為什麼封存 | 現在看哪份 |
| --- | --- | --- | --- |
| [2026-07-20-提案發想.md](2026-07-20-提案發想.md) | 最早的提案發想稿 | 命題理解與定位都已多次修正 | [00 產品與情境](../specs/00-product-and-scenarios.md) |
| [2026-07-23-構想與決策歷程.md](2026-07-23-構想與決策歷程.md) | 早期構想與 grilling 決策紀錄（原 `ideas.md`） | 結論已固化成 ADR 與 specs；文中部分描述（如命題主題、資料量）在當時記載有誤，後續已更正 | [ADR 目錄](../adr/)、[06 SRS](../specs/06-system-requirements.md) |
| [design-exploration/design-directions/](design-exploration/design-directions/) | 八種 UI 方向與色票的 HTML 探索原型 | 方向已定案為「08 柔和指揮台＋07 青綠琥珀」 | [brand-spec](../brand-spec.md)（色彩 token 現行有效） |
| [design-exploration/demo-prototype/](design-exploration/demo-prototype/) | 低擬真流程原型 | 已由 `web/app` 的 Vue 實作取代 | `web/app/` |
| [design-exploration/chat-harness.html](design-exploration/chat-harness.html) | 早期 vanilla-JS 對話測試頁（原 `web/chat.html`） | 對話已整合進 Vue 的 Copilot；保留兩個前端只會造成 demo 當天開錯 | `web/app` 的 CopilotDrawer |
| [superseded/2026-07-28/specs/](superseded/2026-07-28/specs/) | 舊 00／05／07／08 規格 | 社區 DUSKIN Hero、四工作區及 conversation-first 首頁已由會員生活任務方向取代 | [00](../specs/00-product-and-scenarios.md)、[05](../specs/05-erp-modules.md)、[07](../specs/07-demo-vertical-slice.md)、[08](../specs/08-product-experience.md) |
| [superseded/2026-07-28/adr/](superseded/2026-07-28/adr/) | ADR-0005／0006／0010／0016 | 已由 ADR-0015、0019、0020 的會員優先與角色分離決策取代 | [ADR-0019](../adr/0019-member-first-life-task-orchestration.md)、[ADR-0020](../adr/0020-member-navigation-and-dedicated-ai.md) |
| [superseded/2026-07-28/work-management/](superseded/2026-07-28/work-management/) | 舊 P0 roadmap 與社區 Hero 工作票 | 工作順序與 Destination 已改為單一會員生活任務閉環 | [現行 P0 map](../work-management/p0-map.md) |
| [superseded/2026-07-30/specs/](superseded/2026-07-30/specs/) | 舊 00、01、02、04、05、06、07、08、10、12、14 規格 | 資料模型、角色／scope、Group／Community、廠商選擇、Agent、MCP 與 Demo 故事均已重新定案 | [15 產品與平台定案基線](../specs/15-agreed-product-and-platform-direction.md) |
| [superseded/2026-07-30/adr/](superseded/2026-07-30/adr/) | ADR-0003、0015、0019 | `individual/group`、完全分離角色入口與 Group 包含 Community 的決策已被取代 | [15 產品與平台定案基線](../specs/15-agreed-product-and-platform-direction.md) |
| [superseded/2026-07-30/work-management/](superseded/2026-07-30/work-management/) | 2026-07-28 決策佇列、P0／MCP 交付地圖與進度紀錄 | 舊文件把當時切片標成完成，無法代表新定案的完成度 | [現行工作入口](../work-management/README.md) |

## 為什麼不直接刪除

git 保留了歷史，但**翻 git log 找不到「為什麼」**。這些檔案記錄了被否決的選項與當時的理由，
下次有人提出「要不要改成 X」時，這裡可能已經有答案了。

## 注意

- 封存文件中的事實**不保證仍然正確**（例如早期文件把命題主題記成「智慧生活服務需求主動
  滿足平台」，正確應為「智慧社區服務需求理解與媒合平台」）。
- 引用時請標明是封存內容，不要當作現行依據。
