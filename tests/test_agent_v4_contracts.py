from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.agent_core.contracts import (
    ContractError,
    ProposedAction,
    TaskPatch,
    ToolResult,
    TurnIntent,
)
from core.agent_core.orchestrator import AgentOrchestrator, AgentTurn
from core.agent_core.sessions import AgentSessionError, SqliteAgentSessionStore
from core.agent_core.turns import apply_task_patches, classify_turn_intent
from core.agent_core.turns import validate_proposed_action


OWNER = {
    "demo_workspace_id": "demo-default",
    "workspace_id": "workspace-personal-demo-member",
    "account_id": "demo-member",
}


def test_turn_contracts_round_trip_authoritative_facts_and_actions() -> None:
    result = ToolResult(
        action_id="action-1",
        status="succeeded",
        facts={"providerId": "provider-1", "amount": 1200},
        cards=[{"type": "offering", "offeringId": "offering-1", "amount": 1200}],
        warnings=["展示資料"],
        retry_policy="none",
        audit_ref="audit-1",
    )
    patch = TaskPatch(
        target_id="task-1",
        operation="update",
        expected_version=3,
        changes={"timePreference": "afternoon"},
        source="user",
    )

    assert ToolResult.from_dict(result.to_dict()) == result
    assert TaskPatch.from_dict(patch.to_dict()) == patch
    assert TurnIntent.PLAN.value == "plan"


def test_turn_intent_classifier_keeps_non_transaction_turns_side_effect_free() -> None:
    assert classify_turn_intent("我只是想問 OPENPOINT 怎麼折抵") is TurnIntent.PRODUCT_HELP
    assert classify_turn_intent("中元普渡要準備什麼") is TurnIntent.LIFE_GUIDE
    assert classify_turn_intent("先不要，餐廳保留就好") is TurnIntent.PAUSE_OR_CANCEL
    assert classify_turn_intent("幫我安排清潔和晚餐") is TurnIntent.PLAN
    assert classify_turn_intent("我想比較附近的餐廳") is TurnIntent.EXPLORE
    assert classify_turn_intent("今天天氣不錯") is TurnIntent.CONVERSATION


def test_platform_validates_capability_id_risk_schema_and_principal_boundary() -> None:
    valid = validate_proposed_action(ProposedAction(
        action_id="action-wiki", capability_id="wiki.product_help",
        arguments={"query": "點數"}, risk="read",
    ))
    assert valid.action_id == "action-wiki"
    with pytest.raises(ContractError, match="capability id"):
        validate_proposed_action(ProposedAction(
            action_id="action-unknown", capability_id="model.execute_anything",
        ))
    with pytest.raises(ContractError, match="principal"):
        validate_proposed_action(ProposedAction(
            action_id="action-wiki", capability_id="wiki.product_help",
            arguments={"query": "點數", "accountId": "other"},
        ))


def test_task_patches_only_touch_the_stable_target() -> None:
    subtasks = [
        {"id": "task-1", "status": "ready", "quote": {"payable": 1200}},
        {"id": "task-2", "status": "ready", "quote": {"payable": 800}},
    ]

    updated = apply_task_patches(
        subtasks,
        [TaskPatch("task-1", "pause", 1, {}, "user")],
    )

    assert updated[0]["status"] == "paused"
    assert updated[1] == subtasks[1]


class GroundedLlm:
    def __init__(self, response: object) -> None:
        self.response = response

    def grounded_json(self, messages, **kwargs):  # noqa: ANN001 - tiny test double
        return self.response


def _grounding_orchestrator(response: object) -> AgentOrchestrator:
    return AgentOrchestrator(
        llm_factory=lambda: GroundedLlm(response),
        registry=object(), time_resolver=object(), catalog=object(),
        drafts=object(), points=object(), wiki=None,
    )


def test_grounded_second_stage_uses_authoritative_values() -> None:
    session = {"messages": [{"role": "assistant", "content": "先看畫面上的方案。"}]}
    turn = AgentTurn(
        session=session,
        intent=TurnIntent.PLAN,
        tool_results=[ToolResult(
            action_id="action-1", status="succeeded",
            facts={"amount": 1200}, cards=[{"providerName": "Demo 家", "amount": 1200}],
        )],
    )

    _grounding_orchestrator({
        "answer": "我找到 Demo 家的方案，原價 NT$1,200，請以卡片確認。",
        "usedActionIds": ["action-1"],
    })._apply_grounded_response(turn, user_message="幫我安排")

    assert session["messages"][-1]["content"].startswith("我找到 Demo 家")
    assert turn.grounded_response["source"] == "llm"


def test_grounded_second_stage_discards_a_conflicting_number() -> None:
    session = {"messages": [{"role": "assistant", "content": "請以權威卡片為準。"}]}
    turn = AgentTurn(
        session=session,
        intent=TurnIntent.PLAN,
        tool_results=[ToolResult(
            action_id="action-1", status="succeeded", facts={"amount": 1200},
        )],
    )

    _grounding_orchestrator({
        "answer": "已確定是 NT$999，而且已經送出了。",
        "usedActionIds": ["action-1"],
    })._apply_grounded_response(turn, user_message="幫我安排")

    assert session["messages"][-1]["content"] == "請以權威卡片為準。"
    assert turn.grounded_response["source"] == "safe-summary"


def test_grounded_second_stage_discards_unknown_provider_and_status_claims() -> None:
    session = {"messages": [{"role": "assistant", "content": "請以權威卡片為準。"}]}
    turn = AgentTurn(
        session=session,
        intent=TurnIntent.PLAN,
        tool_results=[ToolResult(
            action_id="action-1", status="succeeded",
            facts={"providerName": "Demo 家", "status": "pending_provider"},
        )],
    )

    _grounding_orchestrator({
        "answer": "服務商：另一家店；狀態：已完成。",
        "usedActionIds": ["action-1"],
    })._apply_grounded_response(turn, user_message="幫我安排")

    assert session["messages"][-1]["content"] == "請以權威卡片為準。"
    assert turn.grounded_response["source"] == "safe-summary"


def test_session_lifecycle_has_metadata_occ_and_owner_isolation(tmp_path) -> None:
    store = SqliteAgentSessionStore(tmp_path / "agent.sqlite3")
    created = store.create(**OWNER)

    assert created["title"] == "新對話"
    assert created["status"] == "active"
    assert [item["id"] for item in store.list(**OWNER)] == [created["id"]]

    renamed = store.rename(created["id"], title="爸媽週末安排", expected_version=created["version"], **OWNER)
    assert renamed["title"] == "爸媽週末安排"

    with pytest.raises(AgentSessionError, match="版本"):
        store.rename(created["id"], title="過期寫入", expected_version=created["version"], **OWNER)

    archived = store.archive(
        created["id"], expected_version=renamed["version"], **OWNER,
    )
    assert archived["status"] == "archived"
    assert store.list(**OWNER) == []
    assert store.list(include_archived=True, **OWNER)[0]["id"] == created["id"]

    restored = store.restore(
        created["id"], expected_version=archived["version"], **OWNER,
    )
    assert restored["status"] == "active"

    with pytest.raises(AgentSessionError):
        store.get(created["id"], demo_workspace_id=OWNER["demo_workspace_id"],
                  workspace_id="workspace-other", account_id=OWNER["account_id"])


def test_session_lifecycle_api_is_workspace_scoped(tmp_path) -> None:
    client = TestClient(create_app(demo_db_path=tmp_path / "api.sqlite3", today=date(2026, 8, 1)))
    headers = {"Authorization": "Bearer aiwave"}

    created = client.post("/api/v1/platform/agent/sessions", headers=headers, json={
        "title": "Demo 對話",
    })
    assert created.status_code == 200, created.text
    session = created.json()["data"]
    session_id = session["id"]

    listed = client.get("/api/v1/platform/agent/sessions", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == session_id

    renamed = client.patch(
        f"/api/v1/platform/agent/sessions/{session_id}",
        headers=headers,
        json={"title": "已命名", "expected_version": session["version"]},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["title"] == "已命名"

    archived = client.post(
        f"/api/v1/platform/agent/sessions/{session_id}/archive",
        headers=headers,
        json={"expected_version": renamed.json()["data"]["version"]},
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"

    other = client.get(
        f"/api/v1/platform/agent/sessions/{session_id}",
        headers={"Authorization": "Bearer aiwave-chen"},
    )
    assert other.status_code == 404


def test_product_help_turn_is_grounded_and_has_no_draft_side_effect(tmp_path) -> None:
    client = TestClient(create_app(demo_db_path=tmp_path / "wiki-api.sqlite3", today=date(2026, 8, 1)))
    response = client.post(
        "/api/v1/platform/agent/messages",
        headers={"Authorization": "Bearer aiwave"},
        json={"message": "OPENPOINT 怎麼折抵"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["turn"]["intent"] == "product_help"
    assert data["turn"]["citedKnowledge"]
    assert data["session"]["subtasks"] == []
    assert data["session"]["grantId"] is None
