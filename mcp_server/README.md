# MCP Server

命題明文的交付要求：「將 API 包裝成符合標準的 **MCP Server**，以利後續讓 Lumine one 等
外部 Agent 進行調用。」

依 [ADR-0017](../docs/adr/0017-llm-plans-rules-execute.md)「能力即 MCP 工具」，這個 server
**不定義任何新能力**——它與系統內的規劃器共用同一份 `core.tools` 註冊表：

```text
規劃器（行程內）  ─┐
                   ├─→ ToolRegistry ─→ core/ 服務層 ─→ 資料
MCP（stdio）      ─┘
```

因此不會出現「MCP 版落後於 Web 版」的兩份規則漂移。
`tests/test_mcp_server.py` 有一條測試直接驗證兩邊的工具清單完全相同。

## 啟動

```bash
uv run python -m mcp_server.server
```

以 stdio 協定溝通，供 Claude Desktop、Lumine one 或任何標準 MCP 用戶端掛載。

## 掛載設定

```json
{
  "mcpServers": {
    "smart-living-butler": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "<專案根目錄>",
      "env": {
        "MCP_ACCOUNT_ID": "019e6c8c-a061-7197-be0f-b7d341dbafdd",
        "MCP_ROLE": "user",
        "MCP_DISPLAY_NAME": "王小明"
      }
    }
  }
}
```

## 身分模型

**身分由部署時的環境變數決定，不由工具參數決定。** 工具的 JSON Schema 裡沒有
`account_id` 這種參數，所以外部 Agent 無法要求讀取別人的資料——它只能以
「這個 server 實例所代表的使用者」的身分操作。

| 變數 | 說明 | 預設 |
| --- | --- | --- |
| `MCP_ACCOUNT_ID` | 代表哪個帳號。留空則只有公開能力可用（服務目錄、媒合） | 無 |
| `MCP_ROLE` | `user`（住戶）／`manager`（管委會）／`partner`（廠商） | `user` |
| `MCP_DISPLAY_NAME` | 寫入類操作要記錄的顯示名稱 | `住戶` |

`MCP_ROLE` 同時決定**曝露哪些工具**：住戶身分連 `open_group_buy` 都不會出現在
`tools/list` 裡，不只是呼叫時被拒絕。

上 AWS 後這裡要換成由 OIDC token 解出身分，`ToolContext` 的建構是唯一需要改的地方。

## 能力一覽（完整 Registry 36 項）

| 工具 | 寫入 | 說明 |
| --- | --- | --- |
| `list_services` | | 服務目錄 |
| `search_services` | | 依自然語言與匹配證據回傳相關服務，零分服務不進候選 |
| `get_service_form` | | 該服務的諮詢單題組 |
| `estimate_price` | | 參考價與可用折扣 |
| `match_vendors` | | **FR-S-04 服務媒合**：依地區／時段／預算／緊急程度／評分列 2–3 家並附理由 |
| `submit_inquiry` | ✎ | 驗證題組後建立可追蹤諮詢單 |
| `list_my_inquiries` | | 我的委託與進度 |
| `get_inquiry` | | 單一委託詳情 |
| `confirm_quote` | ✎ | 同意廠商報價 |
| `request_quote_revision` | ✎ | 議價或想換一家：案件退回待報價，附住戶說明 |
| `cancel_inquiry` | ✎ | 取消委託（限施工開始前） |
| `list_group_buys` | | 社區團購活動 |
| `join_group_buy` | ✎ | 跟團 |
| `get_behavior_summary` | | 跨服務使用摘要 |
| `get_activity_trail` | | 行為軌跡 |
| `get_recommendations` | | 可解釋推薦（附官方訂單證據） |
| `get_restock_plan` | | 官方行為證據＋競賽帳本的補貨與最佳優惠方案 |
| `record_recommendation_feedback` | ✎ | 單筆不感興趣／復原，不關閉其他推薦 |
| `create_restock_reminder` | ✎ | 建立週期補貨提醒 |
| `list_reminders` | | 查看提醒 |
| `create_order` | ✎ | 題組驗證與規則計價後建立持久化訂單 |
| `list_my_orders` | | 查看平台訂單與事件 |
| `search_store_inventory` | | 查商品、門市能力、庫存與替代門市 |
| `join_stock_waitlist` | ✎ | 缺貨門市加入候補 |
| `list_stock_watches` | | 查看到貨候補 |
| `diagnose_order_issue` | | 驗證本人訂單並以規則判斷問題類型、優先級與 SLA |
| `create_support_ticket` | ✎ | 以 `diagnose_order_issue` 的短效 token 為本人訂單建立可追蹤客服工單 |
| `list_my_support_tickets` | | 查看本人的客服進度與事件 |

完整 Registry 共 36 項；實際 `tools/list` 仍依角色過濾。`MCP_ROLE=manager` 另有 `open_group_buy`、`close_group_buy`、`list_support_queue`、`start_support_ticket`、`resolve_support_ticket`；
`MCP_ROLE=partner` 另有 `list_vendor_workload`、`submit_quote`、`complete_inquiry`。

標記 ✎ 的會寫入資料。系統內的規劃器對這類工具一律先向使用者確認才執行
（見 [ADR-0008](../docs/adr/0008-permission-bound-operations-copilot.md)）；
MCP transport 也強制二階段確認：第一次呼叫只回傳完整參數預覽與 5 分鐘一次性
`_confirmation_token`，外部 Agent 必須先向使用者展示；第二次以完全相同的參數、角色與帳號
帶回 token 才會執行。token 與 payload 綁定且使用後失效，不能拿去確認另一筆操作。
