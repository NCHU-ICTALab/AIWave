from __future__ import annotations

import sqlite3

import pytest

from core.access import AccessError, AccessForbidden, Role, SqliteAccessRepository, WorkspaceKind
from core.groups import SqliteGroupRepository


def test_fixed_credentials_resolve_server_side_role_and_workspace(tmp_path):
    repository = SqliteAccessRepository(tmp_path / "platform.sqlite3")

    member = repository.resolve_bearer("aiwave")
    partner = repository.resolve_bearer("aiwave-partner")
    manager = repository.resolve_bearer("aiwave-manager")
    admin = repository.resolve_bearer("aiwave-admin")

    assert member.role is Role.MEMBER
    assert member.workspace_kind is WorkspaceKind.PERSONAL
    assert partner.provider_id == "vendor-prince-electric"
    assert manager.community_id == "community-sunshine"
    assert admin.role is Role.PLATFORM_OPERATOR
    assert "platform:*" in admin.scopes

    with sqlite3.connect(tmp_path / "platform.sqlite3") as connection:
        stored = {row[0] for row in connection.execute("SELECT key_hash FROM api_credentials")}
    assert "aiwave" not in stored
    assert all(len(value) == 64 for value in stored)


def test_workspace_switch_is_bound_to_membership_not_request_parameters(tmp_path):
    repository = SqliteAccessRepository(tmp_path / "platform.sqlite3")
    member = repository.resolve_bearer("aiwave")
    admin = repository.resolve_bearer("aiwave-admin")

    with pytest.raises(AccessForbidden):
        repository.issue_session(actor=member, membership_id="membership-partner-prince-electric")

    raw_session, switched = repository.issue_session(
        actor=admin, membership_id="membership-partner-prince-electric",
    )
    assert raw_session != "aiwave-partner"
    assert repository.resolve_bearer(raw_session) == switched
    assert switched.provider_id == "vendor-prince-electric"


def test_one_account_can_hold_multiple_explicit_workspace_memberships(tmp_path):
    repository = SqliteAccessRepository(tmp_path / "platform.sqlite3")
    member = repository.resolve_bearer("aiwave")
    repository.register_workspace_membership(
        account_id=member.account_id,
        display_name=member.display_name,
        workspace_id="workspace-community-second",
        kind=WorkspaceKind.COMMUNITY,
        owner_ref="community-second",
        workspace_name="第二社區",
        role=Role.MEMBER,
    )

    memberships = repository.list_memberships(member.account_id)
    assert {item["workspace"]["kind"] for item in memberships} == {"personal", "community"}


def test_leaving_group_revokes_workspace_membership_and_issued_session(tmp_path):
    path = tmp_path / "platform.sqlite3"
    access = SqliteAccessRepository(path)
    groups = SqliteGroupRepository(path, seed=False, access=access)
    owner = access.resolve_bearer("aiwave")
    member = access.resolve_bearer("aiwave-chen")
    group = groups.create(
        name="週末任務群組", account_id=owner.account_id, display_name=owner.display_name,
    )
    groups.join(
        invite_code=group["inviteCode"], account_id=member.account_id,
        display_name=member.display_name,
    )
    membership_id = f"membership-group-{group['id']}-{member.account_id}"
    session, switched = access.issue_session(actor=member, membership_id=membership_id)
    assert switched.workspace_kind is WorkspaceKind.GROUP

    groups.leave(group["id"], account_id=member.account_id)
    with pytest.raises(AccessError):
        access.resolve_bearer(session)
    assert membership_id not in {
        item["membershipId"] for item in access.list_memberships(member.account_id)
    }
