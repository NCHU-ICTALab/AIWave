"""Stable contracts shared by the conversational layer and deterministic tools.

The model may propose these values, but the platform owns validation and side
effects.  Keeping the contracts in a small module makes the same shapes usable
by HTTP, the Agent runtime, and the future MCP adapter without making any of
those transports a second application service.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TurnIntent(str, Enum):
    CONVERSATION = "conversation"
    PRODUCT_HELP = "product_help"
    LIFE_GUIDE = "life_guide"
    EXPLORE = "explore"
    PLAN = "plan"
    EXECUTE = "execute"
    PAUSE_OR_CANCEL = "pause_or_cancel"


class ContractError(ValueError):
    """A proposed model contract is malformed or outside the platform shape."""


@dataclass(frozen=True)
class ProposedAction:
    action_id: str
    capability_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    risk: str = "read"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProposedAction":
        action_id = str(payload.get("action_id") or "").strip()
        capability_id = str(payload.get("capability_id") or "").strip()
        if not action_id or not capability_id:
            raise ContractError("proposed action 必須有 action_id 與 capability_id")
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ContractError("proposed action arguments 必須是物件")
        return cls(action_id, capability_id, dict(arguments), str(payload.get("risk") or "read"))


@dataclass(frozen=True)
class ToolResult:
    action_id: str
    status: str
    facts: dict[str, Any] = field(default_factory=dict)
    cards: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_policy: str = "none"
    audit_ref: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"succeeded", "needs_confirmation", "unavailable", "failed", "unknown"}:
            raise ContractError(f"不支援的 ToolResult status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "actionId": self.action_id,
            "status": self.status,
            "facts": self.facts,
            "cards": self.cards,
            "warnings": self.warnings,
            "retryPolicy": self.retry_policy,
            "auditRef": self.audit_ref,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolResult":
        action_id = str(payload.get("actionId", payload.get("action_id", ""))).strip()
        if not action_id:
            raise ContractError("ToolResult 必須有 actionId")
        facts = payload.get("facts") or {}
        cards = payload.get("cards") or []
        warnings = payload.get("warnings") or []
        if not isinstance(facts, dict) or not isinstance(cards, list) or not isinstance(warnings, list):
            raise ContractError("ToolResult facts/cards/warnings 形狀錯誤")
        return cls(
            action_id=action_id,
            status=str(payload.get("status") or "failed"),
            facts=dict(facts),
            cards=[dict(card) for card in cards if isinstance(card, dict)],
            warnings=[str(item) for item in warnings],
            retry_policy=str(payload.get("retryPolicy", payload.get("retry_policy", "none"))),
            audit_ref=payload.get("auditRef", payload.get("audit_ref")),
        )


@dataclass(frozen=True)
class TaskPatch:
    target_id: str
    operation: str
    expected_version: int
    changes: dict[str, Any] = field(default_factory=dict)
    source: str = "agent"

    def __post_init__(self) -> None:
        if self.operation not in {"add", "update", "pause", "resume", "remove", "select"}:
            raise ContractError(f"不支援的 TaskPatch operation: {self.operation}")
        if self.expected_version < 1:
            raise ContractError("TaskPatch expectedVersion 必須大於 0")
        if self.source not in {"user", "agent"}:
            raise ContractError("TaskPatch source 必須是 user 或 agent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "targetId": self.target_id,
            "operation": self.operation,
            "expectedVersion": self.expected_version,
            "changes": self.changes,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskPatch":
        return cls(
            target_id=str(payload.get("targetId", payload.get("target_id", ""))),
            operation=str(payload.get("operation") or "update"),
            expected_version=int(payload.get("expectedVersion", payload.get("expected_version", 1))),
            changes=dict(payload.get("changes") or {}),
            source=str(payload.get("source") or "agent"),
        )


@dataclass(frozen=True)
class ConversationTurn:
    assistant_message: str
    intent: TurnIntent
    task_patches: list[TaskPatch] = field(default_factory=list)
    proposed_actions: list[ProposedAction] = field(default_factory=list)
    clarification: str | None = None
    cited_knowledge: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    grounded_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "assistantMessage": self.assistant_message,
            "intent": self.intent.value,
            "taskPatches": [patch.to_dict() for patch in self.task_patches],
            "proposedActions": [action.to_dict() for action in self.proposed_actions],
            "clarification": self.clarification,
            "citedKnowledge": self.cited_knowledge,
            "toolResults": [result.to_dict() for result in self.tool_results],
            "groundedResponse": self.grounded_response,
        }
