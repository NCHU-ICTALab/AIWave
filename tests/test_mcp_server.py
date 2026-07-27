"""MCP Server：命題明文的交付要求。

這裡驗證的核心命題是 **ADR-0017 的「一份定義、雙重曝露」真的成立**——
MCP 看到的工具清單，就是規劃器看到的那一份，不是另外維護的副本。
一旦兩者能各自漂移，「不必為 demo 和交付各做一套」這個決策就形同虛設。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from core.community.group_buy import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext
from mcp_server.server import SERVER_NAME, SERVER_VERSION, create_server

TODAY = date(2026, 7, 27)


@pytest.fixture
def registry(tmp_path: Path):
    services = LifeServicesService(
        SqliteInquiryRepository(tmp_path / "inquiries.sqlite3", now=lambda: datetime(2026, 7, 27, tzinfo=timezone.utc)),
        today=TODAY,
    )
    return build_registry(
        services=services,
        group_buys=SqliteGroupBuyRepository(tmp_path / "groupbuys.sqlite3"),
        today=TODAY,
    )


async def _list_tools(server):
    handler = server.request_handlers[__import__("mcp.types", fromlist=["ListToolsRequest"]).ListToolsRequest]
    from mcp.types import ListToolsRequest

    result = await handler(ListToolsRequest(method="tools/list"))
    return result.root.tools


async def _call_raw(server, name: str, arguments: dict) -> str:
    from mcp.types import CallToolRequest, CallToolRequestParams

    handler = server.request_handlers[CallToolRequest]
    result = await handler(
        CallToolRequest(method="tools/call", params=CallToolRequestParams(name=name, arguments=arguments))
    )
    return result.root.content[0].text


async def _call_tool(server, name: str, arguments: dict):
    return json.loads(await _call_raw(server, name, arguments))


@pytest.mark.anyio
async def test_exposes_exactly_the_registry_tools(registry):
    """MCP 清單 ≡ 註冊表清單。多一個或少一個，都代表有第二份定義偷偷長出來了。"""
    context = ToolContext(account_id="A001", role="user")
    server = create_server(registry, context)

    exposed = {tool.name for tool in await _list_tools(server)}
    assert exposed == {tool.name for tool in registry.list(role="user")}


@pytest.mark.anyio
async def test_every_exposed_tool_carries_its_schema(registry):
    server = create_server(registry, ToolContext(account_id="A001", role="user"))
    for tool in await _list_tools(server):
        assert tool.description
        assert tool.inputSchema["type"] == "object"


@pytest.mark.anyio
async def test_a_read_only_tool_returns_real_data(registry):
    server = create_server(registry, ToolContext(account_id="A001", role="user"))
    payload = await _call_tool(server, "list_services", {})

    assert payload["ok"] is True
    assert any(service["id"] == "service-aircon" for service in payload["result"])


@pytest.mark.anyio
async def test_matching_is_callable_over_mcp(registry):
    """FR-S-04 的媒合也必須是外部 Agent 叫得到的能力，不只是我們自己的畫面。"""
    server = create_server(registry, ToolContext(account_id="A001", role="user"))
    payload = await _call_tool(
        server, "match_vendors", {"service_id": "service-repair", "district": "大同區", "urgent": True}
    )

    assert payload["ok"] is True
    assert payload["result"]["vendors"], "台北市大同區應該媒合得到水電廠商"
    assert payload["result"]["vendors"][0]["supportsUrgent"] is True


@pytest.mark.anyio
async def test_business_errors_come_back_as_readable_results_not_dropped_connections(registry):
    server = create_server(registry, ToolContext(account_id="A001", role="user"))
    payload = await _call_tool(server, "get_inquiry", {"inquiry_id": "INQ-不存在"})

    assert payload["ok"] is False
    assert "查無諮詢單" in payload["error"]


@pytest.mark.anyio
async def test_schema_violations_are_caught_before_the_handler_runs(registry):
    """service_id 的 enum 讓 MCP 協定層自己就擋掉幻覺代碼，外部 Agent 立刻收到明確錯誤。"""
    server = create_server(registry, ToolContext(account_id="A001", role="user"))
    message = await _call_raw(server, "get_service_form", {"service_id": "service-teleport"})

    assert "service-teleport" in message
    assert "not one of" in message or "沒有這項服務" in message


@pytest.mark.anyio
async def test_role_restrictions_hold_over_mcp_too(registry):
    """權限不能因為換了傳輸層就放寬——外部 Agent 也受同一套角色限制。"""
    server = create_server(registry, ToolContext(account_id="A001", role="user"))

    exposed = {tool.name for tool in await _list_tools(server)}
    assert "open_group_buy" not in exposed

    payload = await _call_tool(server, "open_group_buy", {"title": "米", "item_name": "池上米", "unit_price": 350})
    assert payload["ok"] is False
    assert "無法使用" in payload["error"]


@pytest.mark.anyio
async def test_an_unauthenticated_server_still_serves_public_tools(registry):
    """未指定身分時，目錄與媒合這類公開能力仍可用；個人資料則要求登入。"""
    server = create_server(registry, ToolContext(account_id=None, role="user"))

    assert (await _call_tool(server, "list_services", {}))["ok"] is True
    personal = await _call_tool(server, "list_my_inquiries", {})
    assert personal["ok"] is False
    assert "需要先登入" in personal["error"]


def test_server_identifies_itself_as_this_product_not_the_sdk(registry):
    """握手時外部 Agent 看到的名稱與版本必須是我們的，不是 MCP SDK 的。"""
    server = create_server(registry, ToolContext())
    assert server.name == SERVER_NAME
    assert server.version == SERVER_VERSION
