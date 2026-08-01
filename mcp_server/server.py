"""Legacy stdio MCP compatibility proxy for the AIWave Platform API.

This transport intentionally owns no repositories and never opens a database.  It
discovers and invokes capabilities over the same authenticated Platform API used by
the Web client.  The future SDK v2 Streamable HTTP Gateway is a later milestone; this
module only keeps the existing stdio development entry point boundary-safe.

執行：
    MCP_API_KEY=aiwave uv run python -m mcp_server.server
"""

from __future__ import annotations

import json
import os
import secrets
import time
from copy import deepcopy
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool as McpTool

from core.tools.registry import Tool, ToolContext, ToolError, ToolRegistry, validate_arguments

SERVER_NAME = "smart-living-butler"
#: 外部 Agent 在握手時看到的版本。不指定的話會顯示 MCP SDK 的版本，那不是我們的東西。
SERVER_VERSION = "0.1.0"


class PlatformApiRegistry:
    """ToolRegistry-compatible client whose only application boundary is HTTP."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 5.0,
        client: Any | None = None,
    ) -> None:
        if not base_url.strip() or not api_key.strip():
            raise ValueError("MCP_PLATFORM_API_URL 與 MCP_API_KEY 不可空白")
        self.api_key = api_key
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds,
        )
        self._tools: dict[str, Tool] = {}
        self.refresh()

    def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self.client.request(
                method,
                path,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json=json_body,
            )
        except httpx.HTTPError as exc:
            raise ToolError(f"AIWave Platform API 無法連線：{exc}") from exc
        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("detail") or body.get("error", {}).get("message")
            except (ValueError, TypeError, AttributeError):
                detail = None
            raise ToolError(str(detail or f"AIWave Platform API 回應 {response.status_code}"))
        try:
            return response.json()["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ToolError("AIWave Platform API 回應格式不完整") from exc

    def refresh(self) -> None:
        described = self._request("GET", "/api/v1/assistant/tools")
        if not isinstance(described, list):
            raise ToolError("AIWave Platform API 工具清單格式錯誤")
        tools: dict[str, Tool] = {}
        for item in described:
            try:
                tool = Tool(
                    name=str(item["name"]),
                    description=str(item["description"]),
                    parameters=deepcopy(item["inputSchema"]),
                    handler=lambda _context, **_arguments: None,
                    writes=bool(item.get("writes")),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ToolError("AIWave Platform API 工具定義格式錯誤") from exc
            tools[tool.name] = tool
        self._tools = tools

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self, *, role: str | None = None) -> list[Tool]:
        # The Platform API already filtered this catalog by its Bearer principal.
        return sorted(self._tools.values(), key=lambda tool: tool.name)

    def call(
        self, name: str, arguments: dict[str, Any] | None, context: ToolContext,
    ) -> Any:
        tool = self.get(name)
        if tool is None:
            raise ToolError(f"沒有這項能力：{name}")
        cleaned = validate_arguments(tool.parameters, arguments or {})
        plan = self._request(
            "POST",
            "/api/v1/assistant/plan/execute",
            json_body={
                "message": f"MCP 呼叫 {name}",
                "steps": [{"tool": name, "arguments": cleaned, "why": "MCP compatibility proxy"}],
                "approved": [0],
            },
        )
        try:
            step = plan["steps"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ToolError("AIWave Platform API 未回傳工具執行結果") from exc
        if step.get("status") != "done":
            raise ToolError(str(step.get("error") or "AIWave Platform API 未完成工具執行"))
        return step.get("result")


def build_default_registry() -> PlatformApiRegistry:
    """Build an HTTP-only registry; the Platform API must already be running."""
    return PlatformApiRegistry(
        base_url=os.getenv("MCP_PLATFORM_API_URL", "http://127.0.0.1:8000"),
        api_key=os.getenv("MCP_API_KEY", "aiwave"),
        timeout_seconds=float(os.getenv("MCP_PLATFORM_TIMEOUT_SECONDS", "5.0")),
    )


def context_from_env() -> ToolContext:
    """外部 Agent 的身分：由部署時的環境變數決定，不由呼叫參數決定。"""
    return ToolContext(
        account_id=os.getenv("MCP_ACCOUNT_ID") or None,
        role=os.getenv("MCP_ROLE", "user"),
        display_name=os.getenv("MCP_DISPLAY_NAME", "住戶"),
    )


def create_server(
    registry: ToolRegistry | PlatformApiRegistry | None = None,
    context: ToolContext | None = None,
) -> Server:
    """Build the stdio proxy; injected registries remain available for unit tests."""
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
