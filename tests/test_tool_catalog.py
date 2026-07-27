"""能力層：規劃器與 MCP 共用的同一份工具（ADR-0017）。

重點不在「每個工具都會動」，而在**這一層不能偷偷放寬既有的規則**——
身分隔離、狀態機、角色權限，包成工具之後都必須照樣成立。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from core.community.group_buy import SqliteGroupBuyRepository
from core.forms.service_catalog import list_services
from core.inquiries import SqliteInquiryRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext, ToolError

TODAY = date(2026, 7, 27)
FEEDBACK = {"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "燈具／開關", "answerId": 1071}]}]}

# 官方訂單資料裡訂單數最多的真實帳號（31 筆）
OFFICIAL_ACCOUNT = "019e6c8c-a061-7197-be0f-b7d341dbafdd"


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(account_id="A001", role="user", display_name="王小明")


@pytest.fixture
def services(tmp_path: Path) -> LifeServicesService:
    repository = SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3",
        now=lambda: datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    return LifeServicesService(repository, today=TODAY)


@pytest.fixture
def group_buys(tmp_path: Path) -> SqliteGroupBuyRepository:
    return SqliteGroupBuyRepository(tmp_path / "groupbuys.sqlite3")


@pytest.fixture
def registry(services: LifeServicesService, group_buys: SqliteGroupBuyRepository):
    return build_registry(services=services, group_buys=group_buys, today=TODAY)


class TestCatalogShape:
    def test_every_tool_declares_an_object_schema(self, registry):
        for tool in registry.list():
            assert tool.parameters["type"] == "object", tool.name
            for name, spec in tool.parameters.get("properties", {}).items():
                assert "type" in spec, f"{tool.name}.{name} 缺少型別"

    def test_no_tool_accepts_an_identity_parameter(self, registry):
        """身分只能來自 session。工具一旦收 account_id，LLM 就能指定讀誰的資料。"""
        for tool in registry.list():
            properties = set(tool.parameters.get("properties", {}))
            assert not properties & {"account_id", "role", "user_id"}, tool.name

    def test_write_tools_are_marked_so_the_planner_can_ask_first(self, registry):
        writers = {tool.name for tool in registry.list() if tool.writes}
        assert writers == {
            "close_group_buy",
            "complete_inquiry",
            "confirm_quote",
            "join_group_buy",
            "open_group_buy",
            "submit_quote",
        }

    def test_descriptions_tell_the_model_when_to_use_the_tool(self, registry):
        # 描述是提示詞的一部分；太短就等於沒給模型判斷依據
        for tool in registry.list():
            assert len(tool.description) >= 20, tool.name


class TestReadOnlyTools:
    def test_lists_the_service_catalog(self, registry, context):
        result = registry.call("list_services", {}, context)
        assert any(service["id"] == "service-aircon" for service in result)

    def test_returns_the_form_for_a_service(self, registry, context):
        form = registry.call("get_service_form", {"service_id": "service-aircon"}, context)
        assert form["fields"]

    def test_rejects_an_unknown_service_instead_of_returning_nothing(self, registry, context):
        with pytest.raises(ToolError, match="必須是下列之一"):
            registry.call("get_service_form", {"service_id": "service-teleport"}, context)

    def test_service_ids_are_enumerated_in_the_schema(self, registry):
        """代碼合法值放進 schema，幻覺的簡寫（如 cleaning）在驗證就被擋掉。"""
        catalog = {service.id for service in list_services()}
        for name in ("get_service_form", "estimate_price", "match_vendors"):
            spec = registry.get(name).parameters["properties"]["service_id"]
            assert set(spec["enum"]) == catalog, name


class TestIdentityIsolation:
    def test_residents_only_see_their_own_inquiries(self, registry, services):
        services.submit_inquiry(
            form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id="A001"
        )
        services.submit_inquiry(
            form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id="B002"
        )

        mine = registry.call("list_my_inquiries", {}, ToolContext(account_id="A001", role="user"))
        assert [record["account_id"] for record in mine] == ["A001"]

    def test_cannot_read_another_residents_inquiry_by_id(self, registry, services, context):
        other = services.submit_inquiry(
            form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id="B002"
        )
        with pytest.raises(ToolError, match="查無諮詢單"):
            registry.call("get_inquiry", {"inquiry_id": other["id"]}, context)

    def test_cannot_confirm_another_residents_quote(self, registry, services, context):
        other = services.submit_inquiry(
            form_id=105, feedback_content=FEEDBACK, service_id="service-repair", account_id="B002"
        )
        services.quote_inquiry(other["id"], items=[{"name": "施工", "amount": 900}], vendor_name="快修")
        with pytest.raises(ToolError, match="查無諮詢單"):
            registry.call("confirm_quote", {"inquiry_id": other["id"]}, context)

    def test_requires_a_login_for_personal_data(self, registry):
        with pytest.raises(ToolError, match="需要先登入"):
            registry.call("list_my_inquiries", {}, ToolContext(account_id=None, role="user"))


class TestRoleBoundaries:
    def test_residents_cannot_open_a_group_buy(self, registry, context):
        with pytest.raises(ToolError, match="無法使用"):
            registry.call(
                "open_group_buy",
                {"title": "米", "item_name": "池上米", "unit_price": 350},
                context,
            )

    def test_residents_cannot_quote_on_behalf_of_a_vendor(self, registry, context):
        with pytest.raises(ToolError, match="無法使用"):
            registry.call(
                "submit_quote",
                {"inquiry_id": "INQ-1", "items": [], "vendor_name": "假廠商"},
                context,
            )

    def test_a_resident_sees_only_resident_and_shared_tools(self, registry):
        names = {tool.name for tool in registry.list(role="user")}
        assert "list_my_inquiries" in names
        assert "list_services" in names
        assert "open_group_buy" not in names
        assert "submit_quote" not in names


class TestGroupBuyTools:
    def test_joining_uses_the_logged_in_household(self, registry, group_buys, context):
        campaign = group_buys.create_campaign(title="中秋", item_name="文旦", unit_price=300)
        result = registry.call(
            "join_group_buy", {"campaign_id": campaign["id"], "quantity": 3}, context
        )
        assert result["totalQuantity"] == 3
        assert result["joins"][0]["account_id"] == "A001"
        assert result["joins"][0]["display_name"] == "王小明"

    def test_the_state_machine_still_applies_through_the_tool_layer(self, registry, group_buys, context):
        campaign = group_buys.create_campaign(title="中秋", item_name="文旦", unit_price=300)
        group_buys.close_campaign(campaign["id"])
        with pytest.raises(Exception, match="無法再跟團"):
            registry.call("join_group_buy", {"campaign_id": campaign["id"], "quantity": 1}, context)


class TestInsightTools:
    def test_recommendations_carry_evidence_from_real_orders(self, registry):
        result = registry.call(
            "get_recommendations", {}, ToolContext(account_id=OFFICIAL_ACCOUNT, role="user")
        )
        assert result, "官方帳號應該算得出推薦"
        for rec in result:
            assert rec["computedBy"] == "rules"
            assert rec["evidence"]

    def test_the_trail_is_newest_first_so_conversation_starts_with_recent_events(self, registry):
        trail = registry.call(
            "get_activity_trail", {"limit": 5}, ToolContext(account_id=OFFICIAL_ACCOUNT, role="user")
        )
        assert len(trail) <= 5
        dates = [event["occurredOn"] for event in trail if event["occurredOn"]]
        assert dates == sorted(dates, reverse=True)
