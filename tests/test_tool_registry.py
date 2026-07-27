"""工具註冊表的不變條件。

這一層是 LLM 產出的計畫與真實副作用之間唯一的閘門，所以驗證要嚴：
拒絕得越早，錯誤的計畫就越不可能造成半套的資料異動。
"""

import pytest

from core.tools.registry import (
    Tool,
    ToolContext,
    ToolError,
    ToolRegistry,
    validate_arguments,
)


def _echo(context: ToolContext, **kwargs):
    return {"caller": context.account_id, **kwargs}


def _tool(**overrides) -> Tool:
    defaults = dict(
        name="echo",
        description="回傳收到的參數",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["text"],
        },
        handler=_echo,
    )
    return Tool(**{**defaults, **overrides})


class TestValidateArguments:
    def test_accepts_valid_arguments(self):
        schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        assert validate_arguments(schema, {"text": "漏水"}) == {"text": "漏水"}

    def test_rejects_unknown_parameters(self):
        schema = {"type": "object", "properties": {"text": {"type": "string"}}}
        with pytest.raises(ToolError, match="不認識的參數"):
            validate_arguments(schema, {"text": "漏水", "account_id": "別人的帳號"})

    def test_rejects_missing_required(self):
        schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        with pytest.raises(ToolError, match="缺少必要參數"):
            validate_arguments(schema, {})

    def test_rejects_wrong_type(self):
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        with pytest.raises(ToolError, match="型別"):
            validate_arguments(schema, {"count": "很多"})

    def test_coerces_numeric_strings_because_models_quote_numbers(self):
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        assert validate_arguments(schema, {"count": "3"}) == {"count": 3}

    def test_rejects_boolean_masquerading_as_integer(self):
        # Python 的 bool 是 int 的子類別，天真的 isinstance 會放行 True
        schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
        with pytest.raises(ToolError, match="型別"):
            validate_arguments(schema, {"count": True})

    def test_enforces_enum(self):
        schema = {"type": "object", "properties": {"scope": {"type": "string", "enum": ["individual", "group"]}}}
        with pytest.raises(ToolError, match="必須是下列之一"):
            validate_arguments(schema, {"scope": "community"})

    def test_treats_explicit_null_as_absent(self):
        schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        with pytest.raises(ToolError, match="缺少必要參數"):
            validate_arguments(schema, {"text": None})


class TestToolRegistry:
    def test_calls_a_registered_tool_with_context(self):
        registry = ToolRegistry()
        registry.register(_tool())
        result = registry.call("echo", {"text": "你好"}, ToolContext(account_id="A001"))
        assert result == {"caller": "A001", "text": "你好"}

    def test_rejects_unknown_tool(self):
        registry = ToolRegistry()
        with pytest.raises(ToolError, match="沒有這項能力"):
            registry.call("delete_everything", {}, ToolContext())

    def test_rejects_duplicate_registration(self):
        registry = ToolRegistry()
        registry.register(_tool())
        with pytest.raises(ToolError, match="重複"):
            registry.register(_tool())

    def test_identity_cannot_be_supplied_by_the_caller(self):
        """身分只能來自 session；工具參數裡出現 account_id 一律視為不認識的參數。"""
        registry = ToolRegistry()
        registry.register(_tool())
        with pytest.raises(ToolError, match="不認識的參數"):
            registry.call("echo", {"text": "x", "account_id": "別人"}, ToolContext(account_id="A001"))

    def test_enforces_role_restrictions(self):
        registry = ToolRegistry()
        registry.register(_tool(name="vendor_only", roles=frozenset({"partner"})))
        with pytest.raises(ToolError, match="無法使用"):
            registry.call("vendor_only", {"text": "x"}, ToolContext(role="user"))
        assert registry.call("vendor_only", {"text": "x"}, ToolContext(role="partner"))

    def test_lists_only_tools_the_role_may_use(self):
        registry = ToolRegistry()
        registry.register(_tool(name="everyone"))
        registry.register(_tool(name="vendor_only", roles=frozenset({"partner"})))
        assert [tool.name for tool in registry.list(role="user")] == ["everyone"]
        assert [tool.name for tool in registry.list(role="partner")] == ["everyone", "vendor_only"]

    def test_describes_tools_in_mcp_shape(self):
        registry = ToolRegistry()
        registry.register(_tool())
        described = registry.describe()
        assert described == [
            {
                "name": "echo",
                "description": "回傳收到的參數",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}, "count": {"type": "integer"}},
                    "required": ["text"],
                },
            }
        ]

    def test_does_not_execute_when_validation_fails(self):
        """驗證不過就不能有副作用——這是「計畫作廢」語意的基礎。"""
        calls: list[str] = []

        def _recording(context: ToolContext, **kwargs):
            calls.append("ran")
            return None

        registry = ToolRegistry()
        registry.register(_tool(handler=_recording))
        with pytest.raises(ToolError):
            registry.call("echo", {}, ToolContext())
        assert calls == []
