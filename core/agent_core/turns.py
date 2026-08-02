"""Small deterministic helpers around the model-facing v4 turn contracts."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .contracts import ContractError, ProposedAction, TaskPatch, TurnIntent


_PRODUCT_HELP = (
    "aiwave", "openpoint", "點數", "折抵", "取消", "退款", "通知", "行事曆",
    "taskdraft", "草稿", "授權", "生活圈", "到府服務範圍", "怎麼用", "如何操作",
    "你能做什麼", "可以做什麼", "有什麼服務", "提供哪些服務", "功能有哪些",
)
_LIFE_GUIDE = ("中元", "普渡", "颱風", "防災", "搬家", "入厝", "祭拜")
_PAUSE = ("先不要", "不要了", "不用了", "停止", "暫停", "撤回", "反悔", "取消這個")
_EXPLORE = ("比較", "看看", "查一下", "有哪些", "找附近", "可不可以", "價格多少")
_EXECUTE = ("送出", "下單", "預約", "執行", "核准", "幫我訂", "幫我買")
_PLAN = ("幫我", "安排", "找人", "想找", "需要", "要訂", "要買", "想要", "想")
_SERVICE_HINTS = (
    "修繕", "水電", "燈", "清潔", "打掃", "家事", "餐廳", "訂位", "外送", "洗車",
    "宅配", "寄件", "領藥", "藥局", "購物", "預購", "訂房", "門票", "洗衣",
)


def classify_turn_intent(message: str, *, has_task_context: bool = False) -> TurnIntent:
    """Classify the turn only for routing and safety, never for authoritative facts."""

    text = re.sub(r"\s+", "", message.strip().lower())
    if not text:
        return TurnIntent.CONVERSATION
    if any(marker in text for marker in _PAUSE):
        return TurnIntent.PAUSE_OR_CANCEL
    if any(marker in text for marker in _LIFE_GUIDE):
        return TurnIntent.LIFE_GUIDE
    if any(marker in text for marker in _PRODUCT_HELP) and not any(
        marker in text for marker in _SERVICE_HINTS
    ):
        return TurnIntent.PRODUCT_HELP
    if any(marker in text for marker in _EXECUTE) and has_task_context:
        return TurnIntent.EXECUTE
    if any(marker in text for marker in _EXPLORE):
        return TurnIntent.EXPLORE
    if any(marker in text for marker in _PLAN) or any(marker in text for marker in _SERVICE_HINTS) or has_task_context and any(
        marker in text for marker in ("第二個", "前一個", "改下午", "保留", "刪掉")
    ):
        return TurnIntent.PLAN
    return TurnIntent.CONVERSATION


def apply_task_patches(subtasks: list[dict[str, Any]], patches: Iterable[TaskPatch]) -> list[dict[str, Any]]:
    """Apply stable-ID patches without rebuilding unrelated subtasks.

    This function intentionally returns copies.  Callers can validate every
    patch first and only persist the resulting list after all patches succeed.
    """

    updated = [dict(item) for item in subtasks]
    by_id = {str(item.get("id")): index for index, item in enumerate(updated)}
    for patch in patches:
        if patch.operation == "add":
            item = dict(patch.changes)
            item.setdefault("id", patch.target_id)
            item.setdefault("version", 1)
            updated.append(item)
            by_id[item["id"]] = len(updated) - 1
            continue
        if patch.target_id not in by_id:
            raise ContractError(f"找不到 TaskPatch targetId: {patch.target_id}")
        index = by_id[patch.target_id]
        item = dict(updated[index])
        current_version = int(item.get("version", 1))
        if current_version != patch.expected_version:
            raise ContractError(f"TaskPatch 版本衝突: {patch.target_id}")
        if patch.operation == "pause":
            item["status"] = "paused"
        elif patch.operation == "resume":
            item["status"] = "ready" if item.get("selected") else "resolved"
        elif patch.operation == "remove":
            item["status"] = "removed"
        else:
            item.update(patch.changes)
        item["version"] = current_version + 1
        updated[index] = item
    return updated


def capability_descriptions() -> list[dict[str, Any]]:
    """The bounded capability list exposed to an LLM or future MCP adapter."""

    return [
        {"id": "catalog.search", "risk": "read", "schema": {"service": "string", "date": "string?"}},
        {"id": "service.recommend", "risk": "read", "schema": {"domains": "string[]", "preferences": "object?"}},
        {"id": "community.wiki", "risk": "read", "schema": {"query": "string"}},
        {"id": "community.group_buy", "risk": "draft", "schema": {"product": "string", "quantity": "number?"}},
        {"id": "life_circle.search", "risk": "read", "schema": {"category": "string?", "minutes": "number?"}},
        {"id": "calendar.organize", "risk": "draft", "schema": {"title": "string", "date": "string"}},
        {"id": "task_draft.patch", "risk": "draft", "schema": {"targetId": "string", "operation": "string"}},
        {"id": "wiki.product_help", "risk": "read", "schema": {"query": "string"}},
        {"id": "wiki.life_guide", "risk": "read", "schema": {"query": "string"}},
        {"id": "execution_grant.propose", "risk": "external", "schema": {"taskIds": "string[]"}},
        {"id": "conversation.pause", "risk": "none", "schema": {}},
    ]


def validate_proposed_action(action: ProposedAction) -> ProposedAction:
    """Validate the model-facing capability envelope at the platform seam."""

    descriptions = {item["id"]: item for item in capability_descriptions()}
    description = descriptions.get(action.capability_id)
    if description is None:
        raise ContractError(f"不支援的 capability id: {action.capability_id}")
    if action.risk != description["risk"]:
        raise ContractError(f"capability risk 不一致: {action.capability_id}")
    forbidden_principal_keys = {
        "accountId", "workspaceId", "demoWorkspaceId", "principal", "role", "apiKey",
    }
    if forbidden_principal_keys.intersection(action.arguments):
        raise ContractError("capability 不得由模型指定 principal")
    if action.capability_id == "wiki.product_help" and not isinstance(action.arguments.get("query"), str):
        raise ContractError("product-help query 必須是字串")
    if action.capability_id == "wiki.life_guide" and not isinstance(action.arguments.get("query"), str):
        raise ContractError("life-guide query 必須是字串")
    if action.capability_id == "task_draft.patch":
        if not isinstance(action.arguments.get("targetId"), str) or not isinstance(action.arguments.get("operation"), str):
            raise ContractError("TaskPatch action 缺少 targetId 或 operation")
    if action.capability_id == "execution_grant.propose":
        task_ids = action.arguments.get("taskIds")
        if not isinstance(task_ids, list) or not task_ids or not all(isinstance(item, str) for item in task_ids):
            raise ContractError("grant action taskIds 必須是非空字串陣列")
    return action
