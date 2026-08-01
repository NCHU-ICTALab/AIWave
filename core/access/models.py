from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    MEMBER = "member"
    PARTNER_STAFF = "partner_staff"
    COMMUNITY_MANAGER = "community_manager"
    PLATFORM_OPERATOR = "platform_operator"


class WorkspaceKind(StrEnum):
    PERSONAL = "personal"
    GROUP = "group"
    COMMUNITY = "community"
    PROVIDER = "provider"
    PLATFORM = "platform"


class AccessError(ValueError):
    """The requested account, membership, workspace, or credential is invalid."""


class AccessForbidden(AccessError):
    """A valid principal does not have the required role or scope."""


@dataclass(frozen=True)
class Principal:
    account_id: str
    display_name: str
    membership_id: str
    role: Role
    workspace_id: str
    workspace_kind: WorkspaceKind
    owner_ref: str
    demo_workspace_id: str
    scopes: frozenset[str]
    credential_id: str

    @property
    def provider_id(self) -> str | None:
        return self.owner_ref if self.workspace_kind is WorkspaceKind.PROVIDER else None

    @property
    def community_id(self) -> str | None:
        return self.owner_ref if self.workspace_kind is WorkspaceKind.COMMUNITY else None

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes and "platform:*" not in self.scopes:
            raise AccessForbidden(f"目前授權缺少 {scope} 權限")

    def require_role(self, *roles: Role) -> None:
        if self.role not in roles:
            raise AccessForbidden("目前工作空間的角色無法執行此操作")

    def to_dict(self) -> dict:
        return {
            "accountId": self.account_id,
            "displayName": self.display_name,
            "membershipId": self.membership_id,
            "role": self.role.value,
            "workspace": {
                "id": self.workspace_id,
                "kind": self.workspace_kind.value,
                "ownerRef": self.owner_ref,
            },
            "demoWorkspaceId": self.demo_workspace_id,
            "scopes": sorted(self.scopes),
        }
