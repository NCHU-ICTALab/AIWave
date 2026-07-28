# 10・三條 Agent 競賽垂直閉環

> 狀態：2026-07-28 已實作；外部品牌即時 API、LINE 推播與 AWS 部署仍待接入。

## 為什麼只做三條

2025 各組優勝作品共同呈現的不是功能數量，而是可記住的 3–5 條核心能力、企業資產的
真實使用、可信機制與現場可跑 Demo。本專案因此把廣泛需求收斂成三條可由 Web、內部
Planner 與外部 MCP Agent 共用的垂直流程。

## A・一句話完成生活服務

```text
自然語言 → search_services（匹配證據／信心）→ 使用者選方案
→ 官方題組 → 規則驗證 → submit_inquiry → 可追蹤待報價案件
→ 後續 match_vendors／廠商報價 → 住戶確認／退回／取消 → 履約事件
```

- 「想找人打掃」只回專業清潔、計時家事；寄件與外送為零分，不進候選。
- 模型離線或回傳整份目錄時，由相同的 catalog rules 做高信心保底。
- `submit_inquiry` 不能繞過題組引擎，並由 `ToolContext` 決定住戶身分。

## B・個人化補貨與優惠

```text
官方訂單行為證據 → get_restock_plan → seed 點數／優惠券帳本
→ deterministic pricing → create_order → 訂單事件
→ record_recommendation_feedback／create_restock_reminder
```

- 行為來源與點數帳本來源分開標示，不宣稱為正式 OPENPOINT 即時 API。
- 不感興趣只壓低指定 recommendation id，可復原；其他推薦不受影響。
- 補貨訂單寫入 SQLite `platform_orders`，重新整理後仍可由訂單中心追蹤。

## C・超商生態查詢

```text
商品＋行政區＋門市能力 → search_store_inventory
→ 區內有貨結果／附近替代門市 → 缺貨門市 join_stock_waitlist
```

- 庫存與門市能力是 `competition_seed` connector，回應包含資料時間與來源。
- 候補是平台自有 SQLite 狀態，不是前端假卡；正式通知通路待接 LINE/EventBridge。

## 可信與資安邊界

1. LLM 只規劃；服務排名、價格、庫存過濾與寫入驗證由規則負責。
2. 寫入工具標示 `writes=True`；內部 Planner 必須經使用者確認；MCP 第一次呼叫只回預覽與
   5 分鐘一次性 token，第二次 payload、角色與帳號完全相同才執行，token 使用後立即失效。
3. 工具 schema 不接受 `account_id`，MCP 身分只能來自 deployment context。Web 目前是可選
   展示帳號的競賽假登入，不構成正式驗證邊界；公開部署前必須由 OIDC／API gateway 注入身分，
   並移除 path、query 與 body 的帳號信任。
4. 官方訂單、競賽 seed、平台自有狀態在 DTO 中各自標示來源。
5. 三條主流程、跨角色客服閉環與社區聯合服務共用 45-tool Registry；HTTP 與 MCP 不各自維護商業規則。

## Demo 三句話

1. 「想找人來打掃」：選專業清潔，回答題組並建立諮詢單。
2. 「月初該補貨了，幫我算最省」：看證據與省額，建立訂單及 30 天提醒。
3. 「INQ-… 師傅還沒到」：驗證訂單所有權、呈現規則診斷與 SLA，確認後建立可追蹤客服工單。
3. 「大同區哪間門市有吉伊卡哇限定杯而且可以列印」：看有貨替代門市，對缺貨門市加入候補。
