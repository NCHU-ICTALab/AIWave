"""Web、Agent/MCP registry 與平台 proxy 讀寫同一個廠商 HTTP 狀態。"""

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.community.group_buy import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from core.life_tasks import LifeTaskService, SqliteLifeTaskRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext
from core.vendors import MockVendorClient, VendorService
from fake_upstreams.vendor_app import create_fake_vendor_app
from mcp_server.server import create_server
from tests.auth import MEMBER_HEADERS, MEMBER_ID, PARTNER_HEADERS

CONTROL_KEY = "platform-vendor-test"
NOW = lambda: datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)  # noqa: E731


class UnusedLlm:
    def chat(self, *args, **kwargs):
        raise AssertionError("vendor deterministic flow must not call LLM")

    def json(self, *args, **kwargs):
        raise AssertionError("vendor deterministic flow must not call LLM")


async def _call_mcp(server, name: str, arguments: dict) -> dict:
    from mcp.types import CallToolRequest, CallToolRequestParams

    handler = server.request_handlers[CallToolRequest]
    result = await handler(CallToolRequest(
        method="tools/call", params=CallToolRequestParams(name=name, arguments=arguments),
    ))
    return json.loads(result.root.content[0].text)


async def _confirm_mcp(server, name: str, arguments: dict) -> dict:
    preview = await _call_mcp(server, name, arguments)
    assert preview["ok"] is True and preview["requiresConfirmation"] is True
    return await _call_mcp(server, name, {
        **arguments, "_confirmation_token": preview["confirmationToken"],
    })


def _inquiry_payload() -> dict:
    return {
        "accountId": MEMBER_ID, "serviceId": "service-repair", "vendorId": "vendor-prince-electric",
        "consumer": {"name": "林小美", "phone": "0912-000-111", "email": "lin@example.com"},
        "location": {"countyCode": "01", "countyName": "臺北市", "districtCode": "002",
                     "districtName": "大同區", "postalCode": "103", "address": "103臺北市大同區民生西路1號"},
        "preferredSlots": ["weekend"], "budget": 2000, "urgency": "normal",
        "answers": {"description": "浴室燈不亮"}, "summary": "週六浴室燈修繕",
    }


@pytest.mark.anyio
async def test_web_proxy_and_mcp_registry_share_vendor_contract_and_source(tmp_path):
    upstream = TestClient(create_fake_vendor_app(control_key=CONTROL_KEY))
    adapter = MockVendorClient(base_url="http://vendor-fake", client=upstream)
    platform = TestClient(create_app(
        repository=SqliteInquiryRepository(tmp_path / "platform.sqlite3", now=NOW),
        vendor_client=adapter, llm_factory=UnusedLlm,
    ))

    web_match = platform.get(
        "/api/v1/match/service-repair",
        params={"district": "大同區", "county": "台北市", "budget": 2000, "urgent": "true"},
    )
    assert web_match.status_code == 200
    assert web_match.json()["data"]["meta"]["connectorMode"] == "mock_http"
    assert web_match.json()["data"]["vendors"][0]["vendorName"] == "王子水電"

    registry = build_registry(
        services=LifeServicesService(SqliteInquiryRepository(tmp_path / "mcp.sqlite3", now=NOW), today=date(2026, 7, 28)),
        group_buys=SqliteGroupBuyRepository(tmp_path / "group.sqlite3"),
        vendors=VendorService(adapter), today=date(2026, 7, 28),
    )
    mcp = create_server(registry, ToolContext(account_id="A001", role="user"))
    mcp_match = await _call_mcp(mcp, "match_vendors", {
        "service_id": "service-repair", "district": "大同區", "county": "台北市",
        "budget": 2000, "urgent": True,
    })
    assert mcp_match["ok"] is True
    assert mcp_match["result"]["vendors"][0]["vendorId"] == web_match.json()["data"]["vendors"][0]["vendorId"]
    assert mcp_match["result"]["meta"]["dataSource"] == "fake_vendor:vendor_demo_seed_v1"

    created = platform.post(
        "/api/v1/vendor-api/inquiries", headers={
            **MEMBER_HEADERS, "Idempotency-Key": "web-create-once",
        },
        json=_inquiry_payload(),
    )
    assert created.status_code == 200
    inquiry_id = created.json()["data"]["id"]
    assert adapter.get_inquiry(inquiry_id)["data"]["summary"] == "週六浴室燈修繕"

    own = platform.get(
        "/api/v1/vendor-api/inquiries", params={"vendor_id": "vendor-prince-electric"},
        headers=PARTNER_HEADERS,
    )
    assert own.status_code == 200
    denied = platform.get(
        "/api/v1/vendor-api/inquiries", params={"vendor_id": "vendor-duskin"},
        headers=PARTNER_HEADERS,
    )
    assert denied.status_code == 403


@pytest.mark.anyio
async def test_external_agents_can_complete_the_same_cross_service_task_over_mcp(tmp_path):
    upstream = TestClient(create_fake_vendor_app(control_key=CONTROL_KEY))
    adapter = MockVendorClient(base_url="http://vendor-fake", client=upstream)
    vendor_service = VendorService(adapter)
    tasks = LifeTaskService(
        SqliteLifeTaskRepository(tmp_path / "shared.sqlite3", now=NOW),
        vendors=vendor_service, today=date(2026, 7, 28),
    )
    registry = build_registry(
        services=LifeServicesService(
            SqliteInquiryRepository(tmp_path / "shared.sqlite3", now=NOW), today=date(2026, 7, 28),
        ),
        group_buys=SqliteGroupBuyRepository(tmp_path / "groups.sqlite3"),
        vendors=vendor_service, life_tasks=tasks, today=date(2026, 7, 28),
    )
    resident = create_server(registry, ToolContext(account_id="A001", role="user", display_name="小圓"))
    hero = "爸媽週六要來，浴室燈壞了、冷氣也很久沒洗，幫我安排一下，OPENPOINT 能省就省。"

    drafted = await _confirm_mcp(resident, "create_life_task_draft", {"message": hero})
    task = drafted["result"]
    configured = await _confirm_mcp(resident, "configure_life_task", {
        "task_id": task["id"], "expected_version": task["version"], "scheduled_date": "2026-08-01",
        "address_choice": "home", "scope": "personal",
    })
    ready = configured["result"]
    submitted = await _confirm_mcp(resident, "confirm_life_task", {
        "task_id": ready["id"], "expected_version": ready["version"],
    })
    assert submitted["result"]["status"] == "submitted"

    for item in submitted["result"]["items"]:
        partner = create_server(registry, ToolContext(
            account_id=item["vendorId"], role="partner", display_name=item["vendorName"],
        ))
        inquiries = await _call_mcp(partner, "list_external_vendor_inquiries", {})
        assert item["externalInquiryId"] in {row["id"] for row in inquiries["result"]}
        quoted = await _confirm_mcp(partner, "submit_external_vendor_quote", {
            "inquiry_id": item["externalInquiryId"], "valid_until": "2026-08-05",
            "items": [{"name": item["title"], "quantity": 1, "unitPrice": item["basePrice"]}],
        })
        assert quoted["result"]["vendorId"] == item["vendorId"]

    quoted_task = (await _call_mcp(resident, "get_life_task", {"task_id": task["id"]}))["result"]
    assert quoted_task["status"] == "quoted"
    ordered = await _confirm_mcp(resident, "accept_life_task_quotes", {
        "task_id": task["id"], "expected_version": quoted_task["version"],
    })
    assert ordered["result"]["status"] == "ordered"

    for item in ordered["result"]["items"]:
        partner = create_server(registry, ToolContext(
            account_id=item["vendorId"], role="partner", display_name=item["vendorName"],
        ))
        completed = await _confirm_mcp(partner, "update_external_vendor_order", {
            "order_id": item["externalOrderId"], "status": "completed", "note": "服務完成",
        })
        assert completed["result"]["status"] == "completed"

    finished = await _call_mcp(resident, "get_life_task", {"task_id": task["id"]})
    assert finished["result"]["status"] == "completed"
