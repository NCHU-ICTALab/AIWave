"""工具註冊表——規劃器與 MCP 共用的單一能力來源（[ADR-0017]）。

一份定義、雙重曝露：
- 規劃器在行程內呼叫，用來執行 LLM 產生的計畫；
- MCP server 把同一份定義轉成標準工具描述給外部 Agent（如 Lumine one）。

兩個刻意的安全設計：

1. **身分不由模型決定**。`account_id`／`role` 來自登入 session（`ToolContext`），
   工具參數裡不接受身分——否則 LLM 可以要求讀別人的資料。
2. **參數先驗證再執行**。模型指定不存在的工具或不合法的參數時直接拒絕，
   不允許「先跑跑看」。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class ToolError(ValueError):
    """工具不存在、參數不合法，或執行前置條件不滿足。"""


@dataclass(frozen=True)
class ToolContext:
    """呼叫者身分——由 session 提供，不接受模型指定。"""

    account_id: str | None = None
    role: str = "user"
    display_name: str = "住戶"


@dataclass(frozen=True)
class Tool:
    """一項可被規劃器與 MCP 呼叫的能力。"""

    name: str
    description: str
    parameters: dict[str, Any]           # JSON Schema（object）
    handler: Callable[..., Any]
    #: 會寫入資料的工具，規劃器必須先讓使用者確認才執行
    writes: bool = False
    #: 只有這些角色可以呼叫；空集合表示不限
    roles: frozenset[str] = field(default_factory=frozenset)

    def allows(self, role: str) -> bool:
        return not self.roles or role in self.roles

    def to_mcp(self) -> dict[str, Any]:
        """轉成 MCP `tools/list` 的描述格式。"""
        return {"name": self.name, "description": self.description, "inputSchema": self.parameters}


_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    """依 JSON Schema 子集驗證並回傳整理過的參數。

    只支援本專案用得到的部分（object／required／properties／type／enum），
    刻意不引入完整 JSON Schema 相依——驗證邏輯要小到能被完整測試。
    """
    if not isinstance(arguments, dict):
        raise ToolError("參數必須是物件")

    properties: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])

    unknown = set(arguments) - set(properties)
    if unknown:
        raise ToolError(f"不認識的參數：{'、'.join(sorted(unknown))}")

    missing = [name for name in required if arguments.get(name) is None]
    if missing:
        raise ToolError(f"缺少必要參數：{'、'.join(missing)}")

    cleaned: dict[str, Any] = {}
    for name, value in arguments.items():
        if value is None:
            continue
        spec = properties[name]
        expected = spec.get("type")
        python_type = _TYPES.get(expected) if expected else None
        # 整數欄位容忍模型回傳 "3" 這種字串
        if expected == "integer" and isinstance(value, str) and value.strip().lstrip("-").isdigit():
            value = int(value)
        if python_type is not None and not isinstance(value, python_type):
            raise ToolError(f"參數「{name}」型別應為 {expected}")
        if isinstance(value, bool) and expected in ("integer", "number"):
            raise ToolError(f"參數「{name}」型別應為 {expected}")
        allowed = spec.get("enum")
        if allowed and value not in allowed:
            raise ToolError(f"參數「{name}」必須是下列之一：{'、'.join(map(str, allowed))}")
        cleaned[name] = value
    return cleaned


class ToolRegistry:
    """工具的集合；規劃器與 MCP server 都從這裡取得能力。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(f"工具名稱重複：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self, *, role: str | None = None) -> list[Tool]:
        tools = list(self._tools.values())
        if role is not None:
            tools = [tool for tool in tools if tool.allows(role)]
        return sorted(tools, key=lambda tool: tool.name)

    def describe(self, *, role: str | None = None) -> list[dict[str, Any]]:
        return [tool.to_mcp() for tool in self.list(role=role)]

    def call(self, name: str, arguments: dict[str, Any] | None, context: ToolContext) -> Any:
        """驗證後執行；任何一關不過就拋出，不會有「部分執行」。"""
        tool = self.get(name)
        if tool is None:
            raise ToolError(f"沒有這項能力：{name}")
        if not tool.allows(context.role):
            raise ToolError(f"目前身分無法使用「{tool.name}」")
        cleaned = validate_arguments(tool.parameters, arguments or {})
        return tool.handler(context, **cleaned)
