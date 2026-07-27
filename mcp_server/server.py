"""MCP Server：把同一份工具註冊表曝露給外部 Agent（命題明文的交付要求）。

命題要求「將 API 包裝成符合標準的 MCP Server，以利 Lumine one 等外部 Agent 調用」。
依 [ADR-0017]「能力即 MCP 工具」，這裡**不定義任何新能力**——它只是
`core.tools.catalog.build_registry()` 的另一個傳輸層：

    規劃器（行程內） ─┐
                      ├─→ ToolRegistry ─→ core/ 服務層 ─→ 資料
    MCP（stdio/HTTP）─┘

這樣「給評審看的 demo」和「給 Lumine one 調用的介面」是同一套實作，
不會出現「MCP 版落後於 Web 版」這種兩份規則漂移的問題。

身分不由呼叫端的工具參數決定（見 `core.tools.registry`）——外部 Agent 的身分由
啟動時的環境變數指定，等同於「這個 MCP server 實例代表某位使用者」。
真上雲時這裡要換成 OIDC token 解出的身分。

執行：
    uv run python -m mcp_server.server            # stdio，供 Claude Desktop / Lumine one 掛載
"""

from __future__ import annotations

import json
import os
import secrets
import time
from copy import deepcopy
from datetime import date

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool as McpTool

from core.community.group_buy import SqliteGroupBuyRepository
from core.config import get_settings
from core.inquiries import SqliteInquiryRepository
from core.personalization import PersonalizationService, SqlitePersonalizationRepository
from core.orders import SqliteOrderRepository
from core.retail import RetailService, SqliteRetailRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext, ToolError, ToolRegistry, validate_arguments

SERVER_NAME = "smart-living-butler"
#: 外部 Agent 在握手時看到的版本。不指定的話會顯示 MCP SDK 的版本，那不是我們的東西。
SERVER_VERSION = "0.1.0"


def build_default_registry(*, today: date | None = None) -> ToolRegistry:
    """用與 HTTP API 相同的相依組出註冊表。"""
    config = get_settings()
    resolved_today = today or config.demo_today
    return build_registry(
        services=LifeServicesService(
            SqliteInquiryRepository(config.inquiry_db_path),
            orders=SqliteOrderRepository(config.inquiry_db_path),
            today=resolved_today,
        ),
        group_buys=SqliteGroupBuyRepository(config.group_buy_db_path),
        personalization=PersonalizationService(
            SqlitePersonalizationRepository(config.inquiry_db_path), today=resolved_today
        ),
        retail=RetailService(SqliteRetailRepository(config.inquiry_db_path)),
        today=resolved_today,
    )


def context_from_env() -> ToolContext:
    """外部 Agent 的身分：由部署時的環境變數決定，不由呼叫參數決定。"""
    return ToolContext(
        account_id=os.getenv("MCP_ACCOUNT_ID") or None,
        role=os.getenv("MCP_ROLE", "user"),
        display_name=os.getenv("MCP_DISPLAY_NAME", "住戶"),
    )


def create_server(registry: ToolRegistry | None = None, context: ToolContext | None = None) -> Server:
    """組出 MCP server；參數可注入，方便測試不碰真實資料庫。"""
    resolved_registry = registry or build_default_registry()
    resolved_context = context or context_from_env()
    server: Server = Server(SERVER_NAME, version=SERVER_VERSION)
    # MCP 沒有內建 human-in-the-loop 欄位。寫入工具採一次性、短效、payload-bound token：
    # 第一次呼叫只回預覽；外部 Agent 顯示給人確認後，原封不動帶 token 再呼叫才會寫入。
    confirmations: dict[str, tuple[str, float]] = {}

    def fingerprint(name: str, arguments: dict) -> str:
        return json.dumps({
            "tool": name,
            "arguments": arguments,
            "accountId": resolved_context.account_id,
            "role": resolved_context.role,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @server.list_tools()
    async def list_tools() -> list[McpTool]:
        exposed: list[McpTool] = []
        for tool in resolved_registry.list(role=resolved_context.role):
            schema = deepcopy(tool.parameters)
            if tool.writes:
                schema.setdefault("properties", {})["_confirmation_token"] = {
                    "type": "string",
                    "description": "第一次呼叫取得的一次性確認 token；只有使用者確認完全相同的預覽後才可帶入。",
                }
            exposed.append(McpTool(name=tool.name, description=tool.description, inputSchema=schema))
        return exposed

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        # 錯誤照樣回傳成文字結果，而不是讓連線炸掉——外部 Agent 需要看得懂為什麼失敗
        try:
            supplied = dict(arguments or {})
            confirmation_token = supplied.pop("_confirmation_token", None)
            tool = resolved_registry.get(name)
            if tool is not None and not tool.allows(resolved_context.role):
                raise ToolError(f"目前身分無法使用「{tool.name}」")
            if tool is not None and tool.writes:
                cleaned = validate_arguments(tool.parameters, supplied)
                expected = fingerprint(name, cleaned)
                if not confirmation_token:
                    token = secrets.token_urlsafe(24)
                    confirmations[token] = (expected, time.monotonic() + 300)
                    payload = {
                        "ok": True,
                        "requiresConfirmation": True,
                        "confirmationToken": token,
                        "expiresInSeconds": 300,
                        "preview": {
                            "tool": name,
                            "description": tool.description,
                            "arguments": cleaned,
                        },
                    }
                else:
                    pending = confirmations.pop(str(confirmation_token), None)
                    if pending is None or pending[1] < time.monotonic():
                        raise ValueError("確認已失效，請重新取得預覽")
                    if pending[0] != expected:
                        raise ValueError("確認內容與本次寫入不一致，已拒絕執行")
                    result = resolved_registry.call(name, cleaned, resolved_context)
                    payload = {"ok": True, "result": result}
            else:
                result = resolved_registry.call(name, supplied, resolved_context)
                payload = {"ok": True, "result": result}
        except Exception as error:  # noqa: BLE001
            payload = {"ok": False, "error": str(error)}
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, default=str))]

    return server


async def main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
