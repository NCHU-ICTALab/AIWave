from __future__ import annotations

import pytest

from core.agent_core.contracts import TaskPatch, TurnIntent
from core.agent_core.sessions import SqliteAgentSessionStore
from core.agent_core.turns import apply_task_patches, classify_turn_intent


OWNER = {
    "demo_workspace_id": "demo-default",
    "workspace_id": "workspace-personal-demo-member",
    "account_id": "demo-member",
}


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("浴室照明故障，想找人處理", TurnIntent.PLAN),
        ("爸媽週末來，幫我安排到府清潔", TurnIntent.PLAN),
        ("我想訂四人的聚餐", TurnIntent.PLAN),
        ("我只是想了解點數怎麼折抵", TurnIntent.PRODUCT_HELP),
        ("中元準備有哪些差異", TurnIntent.LIFE_GUIDE),
        ("先保留餐廳，清潔先不要", TurnIntent.PAUSE_OR_CANCEL),
        ("我只是想看看附近有哪些選擇", TurnIntent.EXPLORE),
    ],
)
def test_semantic_rewrites_route_to_the_same_safe_intent(message: str, intent: TurnIntent) -> None:
    assert classify_turn_intent(message) is intent


def test_context_patch_and_reversal_keep_unrelated_tasks_intact() -> None:
    original = [
        {"id": "cleaning", "status": "ready", "version": 2, "goal": "清潔"},
        {"id": "dining", "status": "ready", "version": 2, "goal": "餐廳"},
    ]
    updated = apply_task_patches(original, [
        TaskPatch("cleaning", "pause", 2, {}, "user"),
    ])
    assert updated[0]["status"] == "paused"
    assert updated[0]["version"] == 3
    assert updated[1] == original[1]


def test_non_transaction_and_new_session_boundaries_are_explicit(tmp_path) -> None:
    assert classify_turn_intent("今天天氣不錯") is TurnIntent.CONVERSATION
    store = SqliteAgentSessionStore(tmp_path / "sessions.sqlite3")
    first = store.create(**OWNER)
    second = store.create(**{**OWNER, "account_id": "demo-member-chen"})
    assert first["id"] != second["id"]
    assert [item["id"] for item in store.list(**OWNER)] == [first["id"]]
    assert [item["id"] for item in store.list(**{**OWNER, "account_id": "demo-member-chen"})] == [second["id"]]
