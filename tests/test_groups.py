from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from core.groups import SqliteGroupRepository
from tests.auth import MEMBER_HEADERS, SECOND_MEMBER_HEADERS


class UnusedLlm:
    def complete(self, *args, **kwargs):  # pragma: no cover - these endpoints never call an LLM
        raise AssertionError("group endpoints must not call an LLM")


def test_member_can_create_invite_join_and_manage_a_group(tmp_path):
    groups = SqliteGroupRepository(tmp_path / "groups.sqlite3", seed=False)
    client = TestClient(create_app(groups=groups, llm_factory=UnusedLlm))

    created_response = client.post(
        "/api/v1/groups",
        headers={**MEMBER_HEADERS, "Idempotency-Key": "group-create-one"},
        json={"name": "我們的生活群組", "display_name": "小圓"},
    )
    assert created_response.status_code == 200
    created = created_response.json()["data"]
    assert "groupType" not in created
    assert created["myRole"] == "admin"
    assert created["inviteCode"]
    replay = client.post(
        "/api/v1/groups",
        headers={**MEMBER_HEADERS, "Idempotency-Key": "group-create-one"},
        json={"name": "我們的生活群組", "display_name": "小圓"},
    )
    assert replay.json()["data"]["id"] == created["id"]
    assert replay.json()["data"]["idempotentReplay"] is True

    assert client.get("/api/v1/groups", headers=SECOND_MEMBER_HEADERS).json()["data"] == []

    joined_response = client.post(
        "/api/v1/groups/join",
        headers={**SECOND_MEMBER_HEADERS, "Idempotency-Key": "group-join-one"},
        json={"invite_code": created["inviteCode"], "display_name": "陳伯伯"},
    )
    assert joined_response.status_code == 200
    assert {member["displayName"] for member in joined_response.json()["data"]["members"]} == {"小圓", "陳伯伯"}

    forbidden = client.patch(
        f"/api/v1/groups/{created['id']}",
        headers={**SECOND_MEMBER_HEADERS, "Idempotency-Key": "group-rename-forbidden"},
        json={"name": "不能亂改"},
    )
    assert forbidden.status_code == 403

    renamed = client.patch(
        f"/api/v1/groups/{created['id']}",
        headers={**MEMBER_HEADERS, "Idempotency-Key": "group-rename-one"},
        json={"name": "週末家庭任務"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "週末家庭任務"

    left = client.delete(
        f"/api/v1/groups/{created['id']}/members/me",
        headers={**SECOND_MEMBER_HEADERS, "Idempotency-Key": "group-leave-one"},
    )
    assert left.status_code == 200
    assert len(left.json()["data"]["members"]) == 1
    left_replay = client.delete(
        f"/api/v1/groups/{created['id']}/members/me",
        headers={**SECOND_MEMBER_HEADERS, "Idempotency-Key": "group-leave-one"},
    )
    assert left_replay.status_code == 200
    assert left_replay.json()["data"]["idempotentReplay"] is True
