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

## 能力一覽（`MCP_ROLE=user` 時 14 項）

| 工具 | 寫入 | 說明 |
| --- | --- | --- |
| `list_services` | | 服務目錄 |
| `get_service_form` | | 該服務的諮詢單題組 |
| `estimate_price` | | 參考價與可用折扣 |
| `match_vendors` | | **FR-S-04 服務媒合**：依地區／時段／預算／緊急程度／評分列 2–3 家並附理由 |
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

`MCP_ROLE=manager` 另有 `open_group_buy`、`close_group_buy`；
`MCP_ROLE=partner` 另有 `list_vendor_workload`、`submit_quote`、`complete_inquiry`。

標記 ✎ 的會寫入資料。系統內的規劃器對這類工具一律先向使用者確認才執行
（見 [ADR-0008](../docs/adr/0008-permission-bound-operations-copilot.md)）；
外部 Agent 呼叫時則由該 Agent 自行負責確認流程。
