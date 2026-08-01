from __future__ import annotations

import pytest

from core.access import SqliteAccessRepository
from core.communities import CommunityError, CommunityPermissionError, SqliteCommunityRepository


def test_group_and_community_are_separate_and_member_can_join_multiple_communities(tmp_path):
    path = tmp_path / "platform.sqlite3"
    access = SqliteAccessRepository(path)
    communities = SqliteCommunityRepository(path, access=access)
    member = access.resolve_bearer("aiwave")

    rows = communities.list_available(member.account_id)
    assert len([row for row in rows if row["membership"]]) == 2
    assert sum(bool(row["membership"] and row["membership"]["isDefault"]) for row in rows) == 1
    assert all("groupType" not in row for row in rows)

    memberships = access.list_memberships(member.account_id)
    assert {item["workspace"]["kind"] for item in memberships} >= {"personal", "community"}


def test_join_request_requires_manager_of_that_community_and_is_idempotent(tmp_path):
    path = tmp_path / "platform.sqlite3"
    access = SqliteAccessRepository(path)
    communities = SqliteCommunityRepository(path, access=access)

    created = communities.request_join(
        "community-greenfield",
        account_id="new-member",
        display_name="新住戶",
        note="A 棟住戶",
        idempotency_key="join-once",
    )
    replay = communities.request_join(
        "community-greenfield",
        account_id="new-member",
        display_name="新住戶",
        idempotency_key="join-once",
    )
    assert replay["id"] == created["id"]
    assert replay["idempotentReplay"] is True

    with pytest.raises(CommunityPermissionError):
        communities.review_request(
            created["id"], manager_account_id="someone-else", approve=True,
            idempotency_key="review-once",
        )


def test_invite_approval_and_default_selection(tmp_path):
    path = tmp_path / "platform.sqlite3"
    access = SqliteAccessRepository(path)
    communities = SqliteCommunityRepository(path, access=access)
    manager = access.resolve_bearer("aiwave-manager")

    invite = communities.create_invite(
        "community-sunshine", manager_account_id=manager.account_id, max_uses=1,
    )
    joined = communities.join_with_invite(
        code=invite["code"], account_id="invitee", display_name="受邀住戶",
    )
    assert joined["status"] == "active"
    replay = communities.join_with_invite(
        code=invite["code"], account_id="invitee", display_name="受邀住戶",
    )
    assert replay["idempotentReplay"] is True
    assert communities.set_default("community-sunshine", account_id="invitee")["isDefault"] is True
    with pytest.raises(CommunityError, match="使用上限"):
        communities.join_with_invite(code=invite["code"], account_id="other", display_name="另一人")
