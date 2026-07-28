# P0 競賽展示工作地圖

> 狀態：九個 P0 工作包皆已完成；live 彩排由操作手冊重現
> 最後更新：2026-07-28  
> 規格基線：[競賽策略](../strategy/competition-winning-strategy.md)、[00](../specs/00-product-and-scenarios.md)、[07](../specs/07-demo-vertical-slice.md)、[08](../specs/08-product-experience.md)、[14](../specs/14-vendor-api-contract.md)

## Destination

完成一條可在五分鐘穩定展示的會員生活任務閉環：自然語言多意圖 → 點數／廠商／時段方案 → 一次確認 → fake vendor server 建單 → 廠商履約 → 會員追蹤，並以群組聚合、MCP 共用及故障恢復形成差異化證據。

## 已有基礎

- 官方題型、地區與訂單資料讀取。
- 題組引擎、服務媒合、推薦回饋、點數／價格規則及訂單事件。
- Planner、capability registry、HTTP／MCP 共用 tools。
- 會員、廠商、群組、客服及零售 connector 的部分垂直流程。
- Vue、RWD／WCAG 自動化基線與 AI 對話雛形。

這些能力不是完成標準；必須收束到同一 Hero 且由真實平台狀態串起。

## 新 P0 工作包

| 順序 | 工作包 | 完成定義 | 狀態 |
| --- | --- | --- | --- |
| 1 | 產品殼與會員 IA | 首頁、點數、AI、服務、會員中心依新導覽運作；舊角色切換與 demo 控制消失 | 完成 |
| 2 | 成熟 AI 對話體驗 | 固定 composer、正確捲動、自動增高、左右訊息、選項、streaming 進度、可恢復錯誤 | 完成並通過捲動稽核 |
| 3 | Hero task plan | 固定句子穩定拆解修繕、清潔、時程、點數，補齊資料並產生一次確認 | 完成：LifeTask 聚合、版本控制、廠商比較與點數規則 |
| 4 | Vendor contract | OpenAPI 3.0、8–12 品牌、約 30 據點、約 120 案件／報價 seed | 完成：OpenAPI 3.0.3、10 品牌、30 據點、120 諮詢／120 報價 |
| 5 | 獨立 fake vendor server | data/control plane、reset、慢速、503、逾時、格式錯誤與可重現測試 | 完成：獨立 8020 server、受保護控制面與可重現生命週期測試 |
| 6 | Client seam | `VendorClient`、`MockVendorClient`、`RealVendorClient`、後端 `VENDOR_MODE` 與 README | 完成：Web／MCP 同源 HTTP adapter、env-only 切換與手動說明 |
| 7 | 廠商履約回流 | 會員確認後廠商看見案件；報價與狀態回流 AI、首頁及訂單 accordion | 完成：兩廠商報價／履約與三處會員回流 |
| 8 | 群組槓桿 | active scope、角色、同意、共同需求／時段或家庭代辦至少完成一條 | 完成：個人仍為主體，社區群組明確同意、匿名去重與需求／時段聚合 |
| 9 | 競賽證據與硬化 | 基準量測、MCP 共用、故障橋段、390／1440、WCAG AA、五分鐘彩排 | 完成：流程量測、MCP 全生命週期、慢速／503／timeout／格式錯誤、安全重試與操作手冊 |

## 不阻塞 P0

- 正式 OPENPOINT／uniopen API、正式支付及正式廠商 API。
- LINE Bot、LIFF、語音進出與主動推播通路。
- 完整社區管理、AIoT、門禁、包裹與管理費。
- 旅遊、考試週、小賣家、ibon 文件及所有情境模板。
- 為了顯示廣度而把每個服務做成獨立頁面。

## 仍待使用者決定

只保留會實際改變產品或外部整合的事項，見[決策佇列](decision-queue.md)。沒有未決項目阻擋上述九個工作包的規格化與本機實作。
