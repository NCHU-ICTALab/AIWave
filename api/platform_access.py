from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from core.access import AccessError, AccessForbidden, Principal, Role, SqliteAccessRepository
from core.communities import CommunityError, CommunityPermissionError, SqliteCommunityRepository
from core.data.personas import PERSONAS


class SwitchWorkspaceReq(BaseModel):
    membership_id: str


class CommunityJoinReq(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class CommunityAnnouncementReq(BaseModel):
    title: str
    body: str


class CommunityReviewReq(BaseModel):
    approve: bool


class CommunityInviteReq(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=100)
    valid_days: int = Field(default=7, ge=1, le=30)


class CommunityInviteJoinReq(BaseModel):
    code: str = Field(min_length=6, max_length=30)
    display_name: str = Field(min_length=1, max_length=80)


def build_principal_dependency(access: SqliteAccessRepository) -> Callable[..., Principal]:
    def principal(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> Principal:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=401,
                detail="請提供 Bearer 存取憑證",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return access.resolve_bearer(authorization[7:].strip())
        except AccessForbidden as exc:
            raise HTTPException(403, str(exc)) from exc
        except AccessError as exc:
            raise HTTPException(
                status_code=401,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    return principal


def build_access_router(
    *,
    access: SqliteAccessRepository,
    communities: SqliteCommunityRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["Platform access"])
    current_principal = build_principal_dependency(access)

    def require_role(principal: Principal, *roles: Role) -> None:
        try:
            principal.require_role(*roles)
        except AccessForbidden as exc:
            raise HTTPException(403, str(exc)) from exc

    def require_scope(principal: Principal, scope: str) -> None:
        try:
            principal.require_scope(scope)
        except AccessForbidden as exc:
            raise HTTPException(403, str(exc)) from exc

    @router.get("/auth/me")
    def get_me(principal: Principal = Depends(current_principal)) -> dict:
        return {"data": principal.to_dict()}

    @router.get("/auth/workspaces")
    def list_workspaces(principal: Principal = Depends(current_principal)) -> dict:
        return {"data": access.list_memberships(principal.account_id)}

    @router.post("/auth/workspace-session")
    def switch_workspace(
        req: SwitchWorkspaceReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        try:
            token, switched = access.issue_session(actor=principal, membership_id=req.membership_id)
            return {"data": {"accessToken": token, "principal": switched.to_dict()}}
        except AccessForbidden as exc:
            raise HTTPException(403, str(exc)) from exc
        except AccessError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/admin/demo-personas")
    def list_demo_personas(principal: Principal = Depends(current_principal)) -> dict:
        require_role(principal, Role.PLATFORM_OPERATOR)
        require_scope(principal, "demo:switch")
        rows = [access.describe_membership(membership_id) for membership_id in (
            "membership-member-xiaoyuan",
            f"membership-member-{PERSONAS[1].id}",
            f"membership-member-{PERSONAS[2].id}",
            "membership-member-new",
            "membership-partner-prince-electric",
            "membership-partner-duskin",
            "membership-partner-21plus",
            "membership-partner-smile",
            "membership-partner-blackcat",
            "membership-partner-cosmed",
            "membership-partner-711shop",
            "membership-partner-resort",
            "membership-partner-foodomo",
            "membership-partner-711c2c",
            "membership-partner-iopenmall",
            "membership-partner-ibonticket",
            "membership-manager-sunshine",
            "membership-platform-operator",
        )]
        return {"data": rows}

    @router.get("/platform/communities")
    def list_communities(principal: Principal = Depends(current_principal)) -> dict:
        require_role(principal, Role.MEMBER, Role.COMMUNITY_MANAGER, Role.PLATFORM_OPERATOR)
        return {"data": communities.list_available(principal.account_id)}

    @router.post("/platform/communities/{community_id}/join-requests")
    def request_community_join(
        community_id: str,
        req: CommunityJoinReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER)
        try:
            return {"data": communities.request_join(
                community_id,
                account_id=principal.account_id,
                display_name=req.display_name,
                note=req.note,
                idempotency_key=idempotency_key,
            )}
        except CommunityError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/platform/communities/{community_id}/announcements")
    def list_community_announcements(
        community_id: str,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER, Role.COMMUNITY_MANAGER)
        try:
            return {"data": communities.list_announcements(
                community_id, account_id=principal.account_id,
            )}
        except CommunityPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except CommunityError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/platform/communities/{community_id}/announcements")
    def publish_community_announcement(
        community_id: str,
        req: CommunityAnnouncementReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.COMMUNITY_MANAGER)
        try:
            return {"data": communities.publish_announcement(
                community_id, manager_account_id=principal.account_id,
                title=req.title, body=req.body, idempotency_key=idempotency_key,
            )}
        except CommunityPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except CommunityError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/platform/communities/{community_id}/join-requests")
    def list_community_requests(
        community_id: str,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.COMMUNITY_MANAGER)
        if principal.community_id != community_id:
            raise HTTPException(403, "不可查看其他社區的加入申請")
        try:
            return {"data": communities.list_requests(
                community_id, manager_account_id=principal.account_id,
            )}
        except CommunityPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc

    @router.post("/platform/community-join-requests/{request_id}/review")
    def review_community_request(
        request_id: str,
        req: CommunityReviewReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.COMMUNITY_MANAGER)
        try:
            return {"data": communities.review_request(
                request_id,
                manager_account_id=principal.account_id,
                approve=req.approve,
                idempotency_key=idempotency_key,
            )}
        except CommunityPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except CommunityError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/platform/communities/{community_id}/invites")
    def create_community_invite(
        community_id: str,
        req: CommunityInviteReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.COMMUNITY_MANAGER)
        if principal.community_id != community_id:
            raise HTTPException(403, "不可建立其他社區的邀請")
        try:
            return {"data": communities.create_invite(
                community_id,
                manager_account_id=principal.account_id,
                max_uses=req.max_uses,
                valid_days=req.valid_days,
                idempotency_key=idempotency_key,
            )}
        except CommunityPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except CommunityError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/platform/community-invites/join")
    def join_community_invite(
        req: CommunityInviteJoinReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER)
        try:
            return {"data": communities.join_with_invite(
                code=req.code,
                account_id=principal.account_id,
                display_name=req.display_name,
                idempotency_key=idempotency_key,
            )}
        except CommunityError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.put("/platform/communities/{community_id}/default")
    def set_default_community(
        community_id: str,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER)
        try:
            return {"data": communities.set_default(community_id, account_id=principal.account_id)}
        except CommunityPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc

    return router
