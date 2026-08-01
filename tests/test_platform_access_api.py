from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app


class UnusedLlm:
    def complete(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("access routes must not call an LLM")


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_bearer_principal_cannot_be_overridden_by_query_or_headers(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))

    me = client.get(
        "/api/v1/auth/me?account_id=someone-else",
        headers={**bearer("aiwave"), "X-Account-Id": "someone-else", "X-Role": "partner"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["role"] == "member"
    assert me.json()["data"]["workspace"]["kind"] == "personal"

    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer("wrong-key")).status_code == 401


def test_admin_can_switch_only_to_fixed_demo_personas(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))

    rows = client.get("/api/v1/admin/demo-personas", headers=bearer("aiwave-admin"))
    assert rows.status_code == 200
    assert {row["role"] for row in rows.json()["data"]} == {
        "member", "partner_staff", "community_manager", "platform_operator",
    }
    assert client.get("/api/v1/admin/demo-personas", headers=bearer("aiwave")).status_code == 403

    switched = client.post(
        "/api/v1/auth/workspace-session",
        headers=bearer("aiwave-admin"),
        json={"membership_id": "membership-partner-prince-electric"},
    )
    assert switched.status_code == 200
    issued = switched.json()["data"]["accessToken"]
    me = client.get("/api/v1/auth/me", headers=bearer(issued)).json()["data"]
    assert me["workspace"]["ownerRef"] == "vendor-prince-electric"


def test_community_api_enforces_active_community_workspace(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))

    member_rows = client.get("/api/v1/platform/communities", headers=bearer("aiwave"))
    assert member_rows.status_code == 200
    assert len([row for row in member_rows.json()["data"] if row["membership"]]) == 2

    own_requests = client.get(
        "/api/v1/platform/communities/community-sunshine/join-requests",
        headers=bearer("aiwave-manager"),
    )
    assert own_requests.status_code == 200
    other_requests = client.get(
        "/api/v1/platform/communities/community-greenfield/join-requests",
        headers=bearer("aiwave-manager"),
    )
    assert other_requests.status_code == 403


def test_community_join_request_review_is_scoped_and_idempotent(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))
    request_headers = {**bearer("aiwave-new"), "Idempotency-Key": "community-request-one"}
    created = client.post(
        "/api/v1/platform/communities/community-sunshine/join-requests",
        headers=request_headers,
        json={"display_name": "新住戶", "note": "A 棟"},
    )
    replay = client.post(
        "/api/v1/platform/communities/community-sunshine/join-requests",
        headers=request_headers,
        json={"display_name": "新住戶", "note": "A 棟"},
    )
    assert created.status_code == replay.status_code == 200
    assert replay.json()["data"]["id"] == created.json()["data"]["id"]
    assert replay.json()["data"]["idempotentReplay"] is True

    request_id = created.json()["data"]["id"]
    review_headers = {**bearer("aiwave-manager"), "Idempotency-Key": "community-review-one"}
    reviewed = client.post(
        f"/api/v1/platform/community-join-requests/{request_id}/review",
        headers=review_headers, json={"approve": True},
    )
    reviewed_replay = client.post(
        f"/api/v1/platform/community-join-requests/{request_id}/review",
        headers=review_headers, json={"approve": True},
    )
    assert reviewed.status_code == reviewed_replay.status_code == 200
    assert reviewed_replay.json()["data"]["idempotentReplay"] is True
    workspaces = client.get("/api/v1/auth/workspaces", headers=bearer("aiwave-new")).json()["data"]
    assert any(row["workspace"]["ownerRef"] == "community-sunshine" for row in workspaces)


def test_community_invite_create_and_join_replay_without_consuming_twice(tmp_path):
    client = TestClient(create_app(demo_db_path=tmp_path / "platform.sqlite3", llm_factory=UnusedLlm))
    invite_headers = {**bearer("aiwave-manager"), "Idempotency-Key": "community-invite-one"}
    created = client.post(
        "/api/v1/platform/communities/community-sunshine/invites",
        headers=invite_headers, json={"max_uses": 1, "valid_days": 7},
    )
    replay = client.post(
        "/api/v1/platform/communities/community-sunshine/invites",
        headers=invite_headers, json={"max_uses": 1, "valid_days": 7},
    )
    assert created.status_code == replay.status_code == 200
    assert replay.json()["data"]["code"] == created.json()["data"]["code"]
    assert replay.json()["data"]["idempotentReplay"] is True

    join_headers = {**bearer("aiwave-new"), "Idempotency-Key": "community-invite-join-one"}
    payload = {"code": created.json()["data"]["code"], "display_name": "新住戶"}
    joined = client.post("/api/v1/platform/community-invites/join", headers=join_headers, json=payload)
    joined_replay = client.post("/api/v1/platform/community-invites/join", headers=join_headers, json=payload)
    assert joined.status_code == joined_replay.status_code == 200
    assert joined_replay.json()["data"]["idempotentReplay"] is True
