# Local MCP stdio compatibility proxy

這個目錄保留既有 stdio MCP 開發入口，但它不再組裝 repository、開啟 SQLite 或直接呼叫
domain service。工具清單與執行一律透過已啟動的 AIWave Platform API：

~~~text
外部 MCP client → stdio compatibility proxy → Bearer Platform API → application services
~~~

因此 Web 與 MCP 受同一個 Account、RoleMembership、Workspace、Provider、scope、schema 與
稽核邊界控制。M0～M3 尚未包含未來 mcp==2.0.0 Streamable HTTP Gateway；本模組不能被用來
宣稱 M9 已完成。

## 啟動

先依根目錄 README 啟動 Partner fake、legacy Vendor fake 與 Platform API，再開 stdio proxy：

~~~bash
export MCP_PLATFORM_API_URL="http://127.0.0.1:8000"
export MCP_API_KEY="aiwave"
export MCP_ROLE="user"
export MCP_DISPLAY_NAME="小圓"
uv run python -m mcp_server.server
~~~

Platform API 必須已啟動；proxy 啟動時會以 Bearer key 呼叫
GET /api/v1/assistant/tools。無法連線或 token 無效時會明確失敗，不會退回本地資料庫。

## 掛載設定

~~~json
{
  "mcpServers": {
    "smart-living-butler": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "<專案根目錄>",
      "env": {
        "MCP_PLATFORM_API_URL": "http://127.0.0.1:8000",
        "MCP_API_KEY": "aiwave",
        "MCP_ROLE": "user",
        "MCP_DISPLAY_NAME": "小圓"
      }
    }
  }
}
~~~

## 身分與確認

- 真正權限只由 MCP_API_KEY 對應的 Platform API Bearer principal 決定。
- MCP_ROLE 與 MCP_DISPLAY_NAME 僅用於既有 stdio transport 的確認預覽與 fingerprint，不能
  擴張 Bearer token 權限。
- tools/list 已由 Platform API 依 principal 過濾。
- 寫入工具第一次呼叫只回傳 payload-bound、5 分鐘、一次性的 _confirmation_token。
- 第二次帶回完全相同的參數才會由 Platform API 執行；竄改、逾時或 replay 都會被拒絕。
- Platform API 仍會重新驗證 tool、schema 與角色，不信任 MCP 傳回的步驟。

競賽固定 key 見根目錄 README。這些 key 只適用隔離 Demo，正式 Gateway 會改用 OAuth／OIDC
與更細的 scopes。

## 驗證

tests/test_mcp_server.py 同時驗證：

- 注入 registry 時既有 stdio schema 與二階段確認行為。
- production compatibility registry 透過 Platform API 發現及呼叫工具。
- 角色限制、schema error 與 business error 會成為可讀結果。

此外，production mcp_server/server.py 不允許 import SQLite repository；任何新增 transport
也必須維持「只能呼叫 Platform API」的邊界。
