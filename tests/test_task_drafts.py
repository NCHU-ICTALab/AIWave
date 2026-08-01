from __future__ import annotations

import pytest

from core.task_drafts import DraftConflict, SqliteTaskDraftRepository


OWNER = {
    "demo_workspace_id": "demo-a",
    "workspace_id": "workspace-personal-a",
    "account_id": "a",
}


def test_manual_and_agent_share_draft_but_user_edits_win(tmp_path):
    repository = SqliteTaskDraftRepository(tmp_path / "platform.sqlite3")
    draft = repository.create(
        **OWNER,
        domain_type="booking",
        values={"service": "修繕", "date": "2026-08-01"},
        source="agent",
        idempotency_key="draft-once",
    )
    edited = repository.update_fields(
        draft["id"], **OWNER, expected_version=1,
        values={"date": "2026-08-02", "note": "下午較方便"}, source="user",
    )
    agent_retry = repository.update_fields(
        draft["id"], **OWNER, expected_version=2,
        values={"date": "2026-08-03", "providerSuggestion": "provider-1"}, source="agent",
    )

    assert edited["provenance"]["date"] == "user"
    assert agent_retry["values"]["date"] == "2026-08-02"
    assert agent_retry["ignoredFields"] == ["date"]
    assert agent_retry["values"]["providerSuggestion"] == "provider-1"


def test_draft_is_idempotent_versioned_and_workspace_isolated(tmp_path):
    repository = SqliteTaskDraftRepository(tmp_path / "platform.sqlite3")
    draft = repository.create(
        **OWNER, domain_type="booking", source="user", idempotency_key="same",
    )
    replay = repository.create(
        **OWNER, domain_type="booking", source="user", idempotency_key="same",
    )
    assert replay["id"] == draft["id"]
    assert replay["idempotentReplay"] is True

    with pytest.raises(DraftConflict):
        repository.update_fields(
            draft["id"], **OWNER, expected_version=99, values={"x": 1}, source="user",
        )
    with pytest.raises(Exception, match="查無草稿"):
        repository.require_owned(
            draft["id"], demo_workspace_id="demo-b",
            workspace_id=OWNER["workspace_id"], account_id=OWNER["account_id"],
        )

