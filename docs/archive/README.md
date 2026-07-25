# 封存區

這裡放**已被取代、但仍有參考價值**的文件與原型。它們記錄了「我們是怎麼走到現在這個
設計的」，但**不再是有效規格**——實作請以 [docs/README.md](../README.md) 索引的現行文件為準。

> 封存日期：2026-07-26

## 內容

| 項目 | 是什麼 | 為什麼封存 | 現在看哪份 |
| --- | --- | --- | --- |
| [2026-07-20-提案發想.md](2026-07-20-提案發想.md) | 最早的提案發想稿 | 命題理解與定位都已多次修正 | [00 產品與情境](../specs/00-product-and-scenarios.md) |
| [2026-07-23-構想與決策歷程.md](2026-07-23-構想與決策歷程.md) | 早期構想與 grilling 決策紀錄（原 `ideas.md`） | 結論已固化成 ADR 與 specs；文中部分描述（如命題主題、資料量）在當時記載有誤，後續已更正 | [ADR 目錄](../adr/)、[06 SRS](../specs/06-system-requirements.md) |
| [design-exploration/design-directions/](design-exploration/design-directions/) | 八種 UI 方向與色票的 HTML 探索原型 | 方向已定案為「08 柔和指揮台＋07 青綠琥珀」 | [brand-spec](../brand-spec.md)（色彩 token 現行有效） |
| [design-exploration/demo-prototype/](design-exploration/demo-prototype/) | 低擬真流程原型 | 已由 `web/app` 的 Vue 實作取代 | `web/app/` |
| [design-exploration/chat-harness.html](design-exploration/chat-harness.html) | 早期 vanilla-JS 對話測試頁（原 `web/chat.html`） | 對話已整合進 Vue 的 Copilot；保留兩個前端只會造成 demo 當天開錯 | `web/app` 的 CopilotDrawer |

## 為什麼不直接刪除

git 保留了歷史，但**翻 git log 找不到「為什麼」**。這些檔案記錄了被否決的選項與當時的理由，
下次有人提出「要不要改成 X」時，這裡可能已經有答案了。

## 注意

- 封存文件中的事實**不保證仍然正確**（例如早期文件把命題主題記成「智慧生活服務需求主動
  滿足平台」，正確應為「智慧社區服務需求理解與媒合平台」）。
- 引用時請標明是封存內容，不要當作現行依據。
