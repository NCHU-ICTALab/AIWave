from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.access import AccessForbidden, Principal, Role, SqliteAccessRepository, WorkspaceKind
from core.calendar import CalendarConflict, CalendarError, SqliteCalendarRepository
from core.catalog import (
    CatalogNotFound,
    CatalogSyncService,
    DomainError,
    QuoteError,
    SqliteCatalogRepository,
    estimate,
    get_domain,
    status_label,
    validate_draft_values,
)
from core.agent_core import GrantError
from core.agent_core.sessions import AgentSessionError
from core.catalog.listing import listings_for
from core.fulfillment import FulfillmentConflict, FulfillmentError, SqliteFulfillmentRepository
from core.notifications import NotificationError, SqliteNotificationRepository
from core.payments import DemoPaymentError, SqliteDemoPaymentAdapter
from core.points import PointsError, SqlitePointsLedger
from core.providers import ProviderBookingError, ProviderBookingService
from core.task_drafts import DraftConflict, DraftError, SqliteTaskDraftRepository

from .platform_access import build_principal_dependency


class DraftCreateReq(BaseModel):
    domain_type: str = Field(min_length=1, max_length=80)
    values: dict[str, Any] = Field(default_factory=dict)
    source: Literal["provider_default", "profile", "agent", "user"] = "user"


class DraftUpdateReq(BaseModel):
    expected_version: int = Field(ge=1)
    values: dict[str, Any]
    source: Literal["provider_default", "profile", "agent", "user"] = "user"


class DraftTransitionReq(BaseModel):
    expected_version: int = Field(ge=1)
    status: Literal["drafting", "ready", "confirmed", "abandoned"]


class BookingCreateReq(BaseModel):
    provider_id: str
    location_id: str
    offering_id: str
    resource_id: str | None = None
    slot_id: str
    starts_at: str
    ends_at: str


class TransitionReq(BaseModel):
    expected_version: int = Field(ge=1)
    status: str
    note: str | None = Field(default=None, max_length=500)


class RescheduleReq(BaseModel):
    slot_id: str
    starts_at: str
    ends_at: str
    reason: str | None = Field(default=None, max_length=500)


class RescheduleReviewReq(BaseModel):
    accept: bool


class OrderItemReq(BaseModel):
    offering_id: str
    name: str
    quantity: int = Field(gt=0)
    unit_price: int = Field(ge=0)


class OrderCreateReq(BaseModel):
    provider_id: str
    items: list[OrderItemReq] = Field(min_length=1)
    discount: int = Field(default=0, ge=0)


class PointsEntryReq(BaseModel):
    account_id: str
    workspace_id: str
    entry_type: Literal["earn", "redeem", "refund", "reversal", "expiry", "adjustment"]
    amount: int
    description: str
    reference_type: str
    reference_id: str
    expires_at: str | None = None


class PaymentCreateReq(BaseModel):
    subject_type: Literal["booking", "commerce_order"]
    subject_id: str
    amount: int = Field(ge=0)
    points_redeemed: int = Field(default=0, ge=0)
    outcome: Literal["pending", "success", "failure"]


class PaymentRefundReq(BaseModel):
    amount: int = Field(ge=0)
    points: int = Field(ge=0)


class QuietHoursReq(BaseModel):
    start: str | None = None
    end: str | None = None
    timezone: str = "Asia/Taipei"


class CalendarCreateReq(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    starts_at: str
    ends_at: str
    all_day: bool = False
    note: str | None = Field(default=None, max_length=1000)
    recurrence: dict[str, Any] | None = None


class CalendarChangeReq(BaseModel):
    mode: Literal["this", "future", "all"]
    occurrence_start: str | None = None
    changes: dict[str, Any]


class QuoteReq(BaseModel):
    offering_id: str
    quantity: int = Field(default=1, ge=1)
    points_to_redeem: int = Field(default=0, ge=0)


class DraftSubmitReq(BaseModel):
    expected_version: int = Field(ge=1)


class MemberCancelReq(BaseModel):
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=500)


class WorkbenchCatalogReq(BaseModel):
    seedVersion: str
    provider: dict[str, Any]
    locations: list[dict[str, Any]]
    offerings: list[dict[str, Any]]
    resources: list[dict[str, Any]]


class WorkbenchAvailabilityReq(BaseModel):
    slots: list[dict[str, Any]]


class AgentMessageReq(BaseModel):
    """一輪 Agent 互動:自由文字訊息,或前端按鈕的結構化動作(不經 LLM)。"""

    session_id: str | None = None
    message: str | None = Field(default=None, max_length=2000)
    action: dict[str, Any] | None = None


def build_platform_core_router(
    *,
    access: SqliteAccessRepository,
    drafts: SqliteTaskDraftRepository,
    fulfillment: SqliteFulfillmentRepository,
    points: SqlitePointsLedger,
    payments: SqliteDemoPaymentAdapter,
    notifications: SqliteNotificationRepository,
    calendar: SqliteCalendarRepository,
    provider_bookings: ProviderBookingService,
    catalog_projection: SqliteCatalogRepository | None = None,
    catalog_sync: CatalogSyncService | None = None,
    agent_orchestrator: Any | None = None,
    agent_sessions: Any | None = None,
    agent_grants: Any | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/platform", tags=["Platform core"])
    current_principal = build_principal_dependency(access)

    def require_role(principal: Principal, *roles: Role) -> None:
        try:
            principal.require_role(*roles)
        except AccessForbidden as exc:
            raise HTTPException(403, str(exc)) from exc

    def member_scope(principal: Principal) -> tuple[str, str]:
        require_role(principal, Role.MEMBER)
        if principal.workspace_kind not in {WorkspaceKind.PERSONAL, WorkspaceKind.GROUP, WorkspaceKind.COMMUNITY}:
            raise HTTPException(403, "目前工作空間不能建立會員生活資料")
        return principal.workspace_kind.value, principal.owner_ref

    def provider(principal: Principal) -> str:
        require_role(principal, Role.PARTNER_STAFF)
        if principal.provider_id is None:
            raise HTTPException(403, "合作方角色未綁定 Provider")
        return principal.provider_id

    def _offering_display(offering_id: str) -> tuple[str, str | None]:
        """回傳 (顯示名稱, domain_type);投影缺資料時退回原始 id。"""
        if catalog_projection is not None:
            try:
                offering = catalog_projection.get_offering(offering_id)
                return offering.get("name") or offering_id, offering.get("domainType")
            except CatalogNotFound:
                pass
        return offering_id, None

    def publish_booking_projection(booking: dict, *, event_suffix: str) -> None:
        name, domain_type = _offering_display(booking["offeringId"])
        label = status_label(domain_type, kind="booking", status=booking["status"])
        if booking["status"] in {"cancelled", "rejected"}:
            calendar.cancel_projection(
                demo_workspace_id=booking["demoWorkspaceId"],
                source_type="booking", source_id=booking["id"], note=f"狀態：{label}",
            )
        else:
            calendar.upsert_projection(
                demo_workspace_id=booking["demoWorkspaceId"], workspace_id=booking["workspaceId"],
                account_id=booking["accountId"], scope_type="personal", scope_id=booking["accountId"],
                source_type="booking", source_id=booking["id"], title=f"{name}",
                starts_at=booking["startsAt"], ends_at=booking["endsAt"], note=f"狀態：{label}",
            )
        notifications.publish(
            demo_workspace_id=booking["demoWorkspaceId"], workspace_id=booking["workspaceId"],
            account_id=booking["accountId"], scope_type="personal", scope_id=booking["accountId"],
            category="booking_status", title=f"{name}進度更新", body=f"目前狀態：{label}",
            deep_link=f"/orders/{booking['id']}", subject_type="booking", subject_id=booking["id"],
            idempotency_key=f"booking:{booking['id']}:{event_suffix}",
        )

    def _refresh_provider_slots(provider_id: str) -> None:
        """建單/取消會改變上游 slot 容量;成功後刷新該 Provider 的投影,
        讓探索與精靈的時段清單不會長時間提供已被訂走的空檔。失敗不擋主流程。"""
        if catalog_sync is None:
            return
        try:
            catalog_sync.sync_provider(provider_id)
        except Exception:  # noqa: BLE001 - 投影新鮮度是輔助,不影響交易正確性
            pass

    def _refund_subject_payments(
        *, demo_workspace_id: str, subject_type: str, subject_id: str, reason: str,
    ) -> list[dict]:
        """交易取消後把 succeeded/partially_refunded 的 Demo 支付全額退回(含點數沖銷)。"""
        results = []
        for payment in payments.list_by_subject(
            demo_workspace_id=demo_workspace_id, subject_type=subject_type, subject_id=subject_id,
        ):
            if payment["status"] not in {"succeeded", "partially_refunded"}:
                continue
            remaining_amount = payment["amount"] - payment["refundedAmount"]
            remaining_points = payment["pointsRedeemed"] - payment["refundedPoints"]
            if remaining_amount <= 0 and remaining_points <= 0:
                continue
            results.append(payments.refund(
                payment["id"], demo_workspace_id=demo_workspace_id,
                workspace_id=payment["workspaceId"], account_id=payment["accountId"],
                amount=max(remaining_amount, 0), points=max(remaining_points, 0),
                idempotency_key=f"auto-refund:{subject_type}:{subject_id}:{payment['id']}",
            ))
        return results

    @router.post("/task-drafts")
    def create_draft(
        req: DraftCreateReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": drafts.create(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, domain_type=req.domain_type,
                values=req.values, source=req.source, idempotency_key=idempotency_key,
            )}
        except DraftError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/task-drafts")
    def list_drafts(principal: Principal = Depends(current_principal)) -> dict:
        member_scope(principal)
        return {"data": drafts.list_owned(
            demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
            account_id=principal.account_id,
        )}

    @router.get("/task-drafts/{draft_id}")
    def get_draft(draft_id: str, principal: Principal = Depends(current_principal)) -> dict:
        member_scope(principal)
        try:
            return {"data": drafts.require_owned(
                draft_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )}
        except DraftError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.patch("/task-drafts/{draft_id}")
    def update_draft(
        draft_id: str, req: DraftUpdateReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": drafts.update_fields(
                draft_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
                expected_version=req.expected_version, values=req.values, source=req.source,
            )}
        except DraftConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except DraftError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/task-drafts/{draft_id}/transition")
    def transition_draft(
        draft_id: str, req: DraftTransitionReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": drafts.transition(
                draft_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
                expected_version=req.expected_version, status=req.status,
            )}
        except DraftConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except DraftError as exc:
            raise HTTPException(404, str(exc)) from exc

    # ── M4:服務目錄探索(讀平台投影,不依賴 upstream 存活) ──────────

    @router.get("/catalog/providers")
    def list_catalog_providers(
        scene: str | None = Query(default=None),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER, Role.PARTNER_STAFF, Role.PLATFORM_OPERATOR)
        if catalog_projection is None:
            raise HTTPException(503, "平台目錄尚未啟用")
        return {"data": catalog_projection.list_providers(scene=scene)}

    @router.get("/catalog/providers/{provider_id}")
    def get_catalog_provider(
        provider_id: str,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER, Role.PARTNER_STAFF, Role.PLATFORM_OPERATOR)
        if catalog_projection is None:
            raise HTTPException(503, "平台目錄尚未啟用")
        try:
            return {"data": catalog_projection.get_provider(provider_id)}
        except CatalogNotFound as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/catalog/listings")
    def list_catalog_listings(
        scene: str | None = Query(default=None),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        """tier-2 目錄陳列:統一體系品牌卡(不可下單,誠實標示)。名單來源:廠商and表單.md。"""
        require_role(principal, Role.MEMBER, Role.PARTNER_STAFF, Role.PLATFORM_OPERATOR)
        return {"data": listings_for(scene)}

    @router.get("/catalog/availability")
    def list_catalog_availability(
        provider_id: str = Query(alias="providerId"),
        offering_id: str | None = Query(default=None, alias="offeringId"),
        starts_after: str | None = Query(default=None, alias="startsAfter"),
        starts_before: str | None = Query(default=None, alias="startsBefore"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER, Role.PARTNER_STAFF, Role.PLATFORM_OPERATOR)
        if catalog_projection is None:
            raise HTTPException(503, "平台目錄尚未啟用")
        return {"data": catalog_projection.list_slots(
            provider_id, offering_id=offering_id,
            starts_after=starts_after, starts_before=starts_before,
        )}

    @router.post("/catalog/sync")
    def sync_catalog(principal: Principal = Depends(current_principal)) -> dict:
        """從各 Provider connector 重新同步目錄投影(operator 全部,partner 只同步自己)。"""
        require_role(principal, Role.PARTNER_STAFF, Role.PLATFORM_OPERATOR)
        if catalog_sync is None:
            raise HTTPException(503, "平台目錄同步尚未啟用")
        if principal.role is Role.PARTNER_STAFF:
            return {"data": catalog_sync.sync_provider(provider(principal))}
        return {"data": catalog_sync.sync_all()}

    @router.get("/catalog/health")
    def catalog_health(principal: Principal = Depends(current_principal)) -> dict:
        require_role(principal, Role.PLATFORM_OPERATOR)
        if catalog_projection is None:
            raise HTTPException(503, "平台目錄尚未啟用")
        return {"data": catalog_projection.health()}

    # ── M4:價格與點數試算(確定性,讀會員實際可用點數) ─────────────

    @router.post("/quotes")
    def create_quote(
        req: QuoteReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        if catalog_projection is None:
            raise HTTPException(503, "平台目錄尚未啟用")
        try:
            offering = catalog_projection.get_offering(req.offering_id)
        except CatalogNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        balance = points.balance(
            demo_workspace_id=principal.demo_workspace_id,
            workspace_id=principal.workspace_id, account_id=principal.account_id,
        )
        try:
            return {"data": estimate(
                offering=offering, quantity=req.quantity,
                points_to_redeem=req.points_to_redeem, points_balance=balance,
            )}
        except QuoteError as exc:
            raise HTTPException(422, str(exc)) from exc

    # ── M4:TaskDraft submit —— 草稿是唯一入口,手動與 Agent 共用 ───────

    @router.post("/task-drafts/{draft_id}/submit")
    def submit_draft(
        draft_id: str, req: DraftSubmitReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            draft = drafts.require_owned(
                draft_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )
        except DraftError as exc:
            raise HTTPException(404, str(exc)) from exc
        if draft["resultSubjectId"]:
            # 重複提交保護:同一草稿永遠回到同一筆交易
            return {"data": {"draft": draft, "subjectType": draft["resultSubjectType"],
                             "subjectId": draft["resultSubjectId"], "idempotentReplay": True}}
        if draft["status"] not in {"ready", "drafting"}:
            raise HTTPException(409, f"草稿狀態 {draft['status']} 不可送出")
        if draft["version"] != req.expected_version:
            raise HTTPException(409, "草稿版本已更新，請重新載入")
        values = draft["values"]
        try:
            spec = get_domain(draft["domainType"])
            validate_draft_values(draft["domainType"], values)
        except DomainError as exc:
            raise HTTPException(422, str(exc)) from exc
        submit_key = f"draft:{draft_id}:submit"
        if spec.fulfillment_kind == "booking":
            for field_name in ("provider_id", "location_id", "offering_id", "slot_id", "starts_at", "ends_at"):
                if not str(values.get(field_name) or "").strip():
                    raise HTTPException(422, f"草稿缺少預約必要欄位:{field_name}")
            try:
                booking = provider_bookings.create_booking(
                    demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                    account_id=principal.account_id, provider_id=values["provider_id"],
                    location_id=values["location_id"], offering_id=values["offering_id"],
                    resource_id=values.get("resource_id"), slot_id=values["slot_id"],
                    starts_at=values["starts_at"], ends_at=values["ends_at"],
                    idempotency_key=submit_key,
                    # 個資最小化:只把 domain 定義的履約欄位交給廠商端,
                    # 不傳整份草稿(排除交易/選位技術欄位)。
                    details={
                        field_name: values[field_name]
                        for field_name in spec.required_fields
                        if str(values.get(field_name) or "").strip()
                    } or None,
                )
            except ProviderBookingError as exc:
                raise HTTPException(
                    503 if exc.recoverable else 422,
                    {"message": str(exc), "bookingId": exc.booking_id,
                     "stateUnknown": exc.state_unknown, "recoverable": exc.recoverable},
                ) from exc
            except FulfillmentError as exc:
                raise HTTPException(400, str(exc)) from exc
            publish_booking_projection(booking, event_suffix="created")
            _refresh_provider_slots(booking["providerId"])
            updated = drafts.record_result(
                draft_id, demo_workspace_id=principal.demo_workspace_id,
                subject_type="booking", subject_id=booking["id"],
            )
            return {"data": {"draft": updated, "subjectType": "booking",
                             "subjectId": booking["id"], "booking": booking}}
        # commerce:品項價格由平台目錄決定,不信任 client 傳入的價格
        if catalog_projection is None:
            raise HTTPException(503, "平台目錄尚未啟用")
        offering_id = str(values.get("offering_id") or "").strip()
        if not offering_id:
            raise HTTPException(422, "草稿缺少商品欄位:offering_id")
        try:
            offering = catalog_projection.get_offering(offering_id)
        except CatalogNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        quantity = int(values.get("quantity") or 1)
        try:
            order = fulfillment.create_order(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, provider_id=offering["providerId"],
                items=[{
                    "offeringId": offering["id"], "name": offering["name"],
                    "quantity": quantity, "unitPrice": int(offering["basePrice"]),
                }],
                discount=0, idempotency_key=submit_key,
            )
        except FulfillmentError as exc:
            raise HTTPException(400, str(exc)) from exc
        notifications.publish(
            demo_workspace_id=order["demoWorkspaceId"], workspace_id=order["workspaceId"],
            account_id=order["accountId"], scope_type="personal", scope_id=order["accountId"],
            category="order_status", title=f"{offering['name']}訂單已建立",
            body=f"訂單金額 NT${order['total']}",
            deep_link=f"/orders/{order['id']}", subject_type="commerce_order", subject_id=order["id"],
            idempotency_key=f"order:{order['id']}:created",
        )
        updated = drafts.record_result(
            draft_id, demo_workspace_id=principal.demo_workspace_id,
            subject_type="commerce_order", subject_id=order["id"],
        )
        return {"data": {"draft": updated, "subjectType": "commerce_order",
                         "subjectId": order["id"], "order": order}}

    @router.post("/bookings")
    def create_booking(
        req: BookingCreateReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            booking = provider_bookings.create_booking(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, provider_id=req.provider_id,
                location_id=req.location_id, offering_id=req.offering_id,
                resource_id=req.resource_id, slot_id=req.slot_id,
                starts_at=req.starts_at, ends_at=req.ends_at, idempotency_key=idempotency_key,
            )
            publish_booking_projection(booking, event_suffix="created")
            _refresh_provider_slots(booking["providerId"])
            return {"data": booking}
        except ProviderBookingError as exc:
            raise HTTPException(
                503 if exc.recoverable else 422,
                {
                    "message": str(exc), "bookingId": exc.booking_id,
                    "stateUnknown": exc.state_unknown, "recoverable": exc.recoverable,
                },
            ) from exc
        except (FulfillmentError, CalendarError, NotificationError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/bookings/{booking_id}/provider-sync")
    def retry_booking_provider_sync(
        booking_id: str,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            booking = provider_bookings.retry_create(
                booking_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )
            publish_booking_projection(booking, event_suffix="provider-sync")
            return {"data": booking}
        except ProviderBookingError as exc:
            raise HTTPException(
                503 if exc.recoverable else 422,
                {
                    "message": str(exc), "bookingId": exc.booking_id,
                    "stateUnknown": exc.state_unknown, "recoverable": exc.recoverable,
                },
            ) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc

    def _resolve_provider_id(principal: Principal, requested: str | None) -> str | None:
        """Partner 一律綁自己的 Provider;會員可指定要查的 Provider。"""
        if principal.role is Role.PARTNER_STAFF:
            return provider(principal)
        return requested

    @router.get("/provider/catalog")
    def get_provider_catalog(
        provider_id: str | None = Query(default=None, alias="providerId"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER, Role.PARTNER_STAFF)
        try:
            return {"data": provider_bookings.catalog(_resolve_provider_id(principal, provider_id))}
        except ProviderBookingError as exc:
            raise HTTPException(502, str(exc)) from exc

    @router.get("/provider/availability")
    def get_provider_availability(
        provider_id: str | None = Query(default=None, alias="providerId"),
        offering_id: str | None = Query(default=None, alias="offeringId"),
        starts_after: str | None = Query(default=None, alias="startsAfter"),
        starts_before: str | None = Query(default=None, alias="startsBefore"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.MEMBER, Role.PARTNER_STAFF)
        try:
            return {"data": provider_bookings.availability(
                _resolve_provider_id(principal, provider_id),
                offeringId=offering_id, startsAfter=starts_after, startsBefore=starts_before,
            )}
        except ProviderBookingError as exc:
            raise HTTPException(502, str(exc)) from exc

    @router.get("/provider/snapshot")
    def get_provider_snapshot(
        provider_id: str | None = Query(default=None, alias="providerId"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.PARTNER_STAFF, Role.PLATFORM_OPERATOR)
        try:
            resolved = provider(principal) if principal.role is Role.PARTNER_STAFF else provider_id
            return {"data": provider_bookings.snapshot(resolved)}
        except ProviderBookingError as exc:
            raise HTTPException(502, str(exc)) from exc

    @router.put("/provider/catalog")
    def workbench_replace_catalog(
        req: WorkbenchCatalogReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        """工作台接入:沒有 API 的廠商由平台工作台維護自己的 catalog。"""
        provider_id = provider(principal)
        if req.provider.get("id") != provider_id:
            raise HTTPException(403, "不可寫入其他 Provider 的 catalog")
        connector = provider_bookings.connectors.get(provider_id) or provider_bookings.connector
        if not hasattr(connector, "save_catalog"):
            raise HTTPException(409, "此 Provider 不是工作台接入,catalog 由廠商系統維護")
        connector.save_catalog(req.model_dump())
        result = catalog_sync.sync_provider(provider_id) if catalog_sync else None
        return {"data": {"saved": True, "sync": result}}

    @router.put("/provider/availability")
    def workbench_replace_availability(
        req: WorkbenchAvailabilityReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        provider_id = provider(principal)
        if any(item.get("providerId") != provider_id for item in req.slots):
            raise HTTPException(403, "不可寫入其他 Provider 的 availability")
        connector = provider_bookings.connectors.get(provider_id) or provider_bookings.connector
        if not hasattr(connector, "save_availability"):
            raise HTTPException(409, "此 Provider 不是工作台接入,availability 由廠商系統維護")
        connector.save_availability(req.slots)
        result = catalog_sync.sync_provider(provider_id) if catalog_sync else None
        return {"data": {"saved": True, "sync": result}}

    @router.get("/bookings")
    def list_bookings(principal: Principal = Depends(current_principal)) -> dict:
        if principal.role is Role.MEMBER:
            rows = fulfillment.list_bookings(
                demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )
        else:
            rows = fulfillment.list_bookings(
                demo_workspace_id=principal.demo_workspace_id, provider_id=provider(principal),
            )
        return {"data": rows}

    @router.get("/bookings/{booking_id}")
    def get_booking(booking_id: str, principal: Principal = Depends(current_principal)) -> dict:
        try:
            if principal.role is Role.MEMBER:
                row = fulfillment.get_booking(
                    booking_id, demo_workspace_id=principal.demo_workspace_id,
                    workspace_id=principal.workspace_id, account_id=principal.account_id,
                )
            else:
                row = fulfillment.get_booking(
                    booking_id, demo_workspace_id=principal.demo_workspace_id,
                    workspace_id=principal.workspace_id, provider_id=provider(principal),
                )
            return {"data": row}
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/bookings/{booking_id}/transition")
    def transition_booking(
        booking_id: str, req: TransitionReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        try:
            booking = provider_bookings.transition_booking(
                booking_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id,
                provider_id=provider(principal), expected_version=req.expected_version,
                to_status=req.status, actor_account_id=principal.account_id,
                idempotency_key=idempotency_key, note=req.note,
            )
            publish_booking_projection(booking, event_suffix=idempotency_key)
            return {"data": booking}
        except ProviderBookingError as exc:
            raise HTTPException(
                503 if exc.recoverable else 409,
                {
                    "message": str(exc), "bookingId": exc.booking_id,
                    "stateUnknown": exc.state_unknown, "recoverable": exc.recoverable,
                },
            ) from exc
        except FulfillmentConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/bookings/{booking_id}/cancellation")
    def member_cancel_booking(
        booking_id: str, req: MemberCancelReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        """會員自助取消:上游取消 → 本地轉移 → 自動退款與點數沖銷 → 通知與行事曆同步。"""
        member_scope(principal)
        try:
            booking = provider_bookings.member_cancel(
                booking_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
                expected_version=req.expected_version,
                idempotency_key=idempotency_key, note=req.note,
            )
        except ProviderBookingError as exc:
            raise HTTPException(
                503 if exc.recoverable else 409,
                {"message": str(exc), "bookingId": exc.booking_id,
                 "stateUnknown": exc.state_unknown, "recoverable": exc.recoverable},
            ) from exc
        except FulfillmentConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc
        refunds = _refund_subject_payments(
            demo_workspace_id=principal.demo_workspace_id,
            subject_type="booking", subject_id=booking_id, reason="member_cancel",
        )
        publish_booking_projection(booking, event_suffix=f"cancelled:{idempotency_key}")
        _refresh_provider_slots(booking["providerId"])  # 取消釋放的時段回到探索清單
        return {"data": {**booking, "refunds": refunds}}

    @router.post("/commerce-orders/{order_id}/cancellation")
    def member_cancel_order(
        order_id: str, req: MemberCancelReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        """會員取消購物訂單:出貨前(placed/payment_failed/accepted/preparing)可取消。"""
        member_scope(principal)
        try:
            order = fulfillment.get_order(
                order_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc
        if order["status"] not in {"placed", "payment_failed", "accepted", "preparing"}:
            raise HTTPException(409, f"訂單狀態 {order['status']} 已出貨,請改走退貨流程")
        try:
            updated = fulfillment.transition_order(
                order_id, demo_workspace_id=principal.demo_workspace_id,
                provider_id=order["providerId"], expected_version=req.expected_version,
                to_status="cancelled", actor_account_id=principal.account_id,
                idempotency_key=idempotency_key, note=req.note, actor_role="member",
            )
        except FulfillmentConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc
        refunds = _refund_subject_payments(
            demo_workspace_id=principal.demo_workspace_id,
            subject_type="commerce_order", subject_id=order_id, reason="member_cancel",
        )
        notifications.publish(
            demo_workspace_id=updated["demoWorkspaceId"], workspace_id=updated["workspaceId"],
            account_id=updated["accountId"], scope_type="personal", scope_id=updated["accountId"],
            category="order_status", title="訂單已取消",
            body="款項與點數將依原路退回" if refunds else "訂單已取消",
            deep_link=f"/orders/{order_id}", subject_type="commerce_order", subject_id=order_id,
            idempotency_key=f"order:{order_id}:cancelled:{idempotency_key}",
        )
        return {"data": {**updated, "refunds": refunds}}

    @router.post("/bookings/{booking_id}/reschedule-requests")
    def request_reschedule(
        booking_id: str, req: RescheduleReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            request = fulfillment.request_reschedule(
                booking_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
                slot_id=req.slot_id, starts_at=req.starts_at, ends_at=req.ends_at,
                reason=req.reason, idempotency_key=idempotency_key,
            )
        except FulfillmentConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc
        notifications.publish(
            demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
            account_id=principal.account_id, scope_type="personal", scope_id=principal.account_id,
            category="booking_status", title="改期申請已送出", body="等待廠商回覆改期結果",
            deep_link=f"/orders/{booking_id}", subject_type="booking", subject_id=booking_id,
            idempotency_key=f"reschedule:{request['id']}:requested",
        )
        return {"data": request}

    @router.post("/booking-reschedule-requests/{request_id}/review")
    def review_reschedule(
        request_id: str, req: RescheduleReviewReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        try:
            result = fulfillment.review_reschedule(
                request_id, demo_workspace_id=principal.demo_workspace_id,
                provider_id=provider(principal), actor_account_id=principal.account_id,
                accept=req.accept, idempotency_key=idempotency_key,
            )
        except FulfillmentConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc
        booking_id = result.get("bookingId")
        if booking_id and not result.get("idempotentReplay"):
            booking = fulfillment.get_booking(
                booking_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, provider_id=provider(principal),
            )
            if req.accept:
                # 改期成立:行事曆與通知跟著新時段走(Booking 是事實來源)
                publish_booking_projection(booking, event_suffix=f"rescheduled:{idempotency_key}")
            else:
                notifications.publish(
                    demo_workspace_id=booking["demoWorkspaceId"], workspace_id=booking["workspaceId"],
                    account_id=booking["accountId"], scope_type="personal", scope_id=booking["accountId"],
                    category="booking_status", title="改期申請未通過", body="原時段維持不變",
                    deep_link=f"/orders/{booking_id}", subject_type="booking", subject_id=booking_id,
                    idempotency_key=f"reschedule:{request_id}:rejected",
                )
        return {"data": result}

    @router.post("/commerce-orders")
    def create_order(
        req: OrderCreateReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            order = fulfillment.create_order(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, provider_id=req.provider_id,
                items=[{
                    "offeringId": item.offering_id, "name": item.name,
                    "quantity": item.quantity, "unitPrice": item.unit_price,
                } for item in req.items],
                discount=req.discount, idempotency_key=idempotency_key,
            )
            notifications.publish(
                demo_workspace_id=order["demoWorkspaceId"], workspace_id=order["workspaceId"],
                account_id=order["accountId"], scope_type="personal", scope_id=order["accountId"],
                category="order_status", title="Demo 訂單已建立", body=f"訂單金額 NT${order['total']}",
                deep_link=f"/orders/{order['id']}", subject_type="commerce_order", subject_id=order["id"],
                idempotency_key=f"order:{order['id']}:created",
            )
            return {"data": order}
        except (FulfillmentError, NotificationError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/commerce-orders")
    def list_orders(principal: Principal = Depends(current_principal)) -> dict:
        if principal.role is Role.MEMBER:
            rows = fulfillment.list_orders(
                demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )
        else:
            rows = fulfillment.list_orders(
                demo_workspace_id=principal.demo_workspace_id, provider_id=provider(principal),
            )
        return {"data": rows}

    @router.post("/commerce-orders/{order_id}/transition")
    def transition_order(
        order_id: str, req: TransitionReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        try:
            order = fulfillment.transition_order(
                order_id, demo_workspace_id=principal.demo_workspace_id,
                provider_id=provider(principal), expected_version=req.expected_version,
                to_status=req.status, actor_account_id=principal.account_id,
                idempotency_key=idempotency_key, note=req.note,
            )
            first_offering = (order.get("items") or [{}])[0].get("offeringId", "")
            _, order_domain = _offering_display(first_offering)
            label = status_label(order_domain, kind="commerce", status=order["status"])
            notifications.publish(
                demo_workspace_id=order["demoWorkspaceId"], workspace_id=order["workspaceId"],
                account_id=order["accountId"], scope_type="personal", scope_id=order["accountId"],
                category="order_status", title="訂單進度已更新", body=f"目前狀態：{label}",
                deep_link=f"/orders/{order['id']}", subject_type="commerce_order", subject_id=order["id"],
                idempotency_key=f"order:{order['id']}:{idempotency_key}",
            )
            return {"data": order}
        except FulfillmentConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get("/points")
    def get_points(principal: Principal = Depends(current_principal)) -> dict:
        member_scope(principal)
        return {"data": points.list_entries(
            demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
            account_id=principal.account_id,
        )}

    @router.post("/admin/points")
    def post_points(
        req: PointsEntryReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.PLATFORM_OPERATOR)
        try:
            return {"data": points.post(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=req.workspace_id,
                account_id=req.account_id, entry_type=req.entry_type, amount=req.amount,
                description=req.description, reference_type=req.reference_type,
                reference_id=req.reference_id, expires_at=req.expires_at,
                idempotency_key=idempotency_key,
            )}
        except PointsError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/payments")
    def create_payment(
        req: PaymentCreateReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        # 付款主體必須是呼叫者自己的交易(IDOR 防護);404 不洩漏他人資料存在性
        try:
            if req.subject_type == "booking":
                subject = fulfillment.get_booking(
                    req.subject_id, demo_workspace_id=principal.demo_workspace_id,
                    workspace_id=principal.workspace_id, account_id=principal.account_id,
                )
            else:
                subject = fulfillment.get_order(
                    req.subject_id, demo_workspace_id=principal.demo_workspace_id,
                    workspace_id=principal.workspace_id, account_id=principal.account_id,
                )
        except FulfillmentError as exc:
            raise HTTPException(404, str(exc)) from exc
        try:
            result = payments.create(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, subject_type=req.subject_type,
                subject_id=req.subject_id, amount=req.amount, points_redeemed=req.points_redeemed,
                outcome=req.outcome, idempotency_key=idempotency_key,
            )
            # 付款結果驅動購物訂單狀態:失敗 → payment_failed;重付成功 → 回到 placed
            if req.subject_type == "commerce_order" and not result.get("idempotentReplay"):
                if result["status"] == "failed" and subject["status"] == "placed":
                    fulfillment.transition_order(
                        req.subject_id, demo_workspace_id=principal.demo_workspace_id,
                        provider_id=subject["providerId"], expected_version=subject["version"],
                        to_status="payment_failed", actor_account_id=principal.account_id,
                        idempotency_key=f"payment-failed:{result['id']}",
                        note="Demo 付款失敗", actor_role="member",
                    )
                elif result["status"] == "succeeded" and subject["status"] == "payment_failed":
                    fulfillment.transition_order(
                        req.subject_id, demo_workspace_id=principal.demo_workspace_id,
                        provider_id=subject["providerId"], expected_version=subject["version"],
                        to_status="placed", actor_account_id=principal.account_id,
                        idempotency_key=f"payment-recovered:{result['id']}",
                        note="重新付款成功", actor_role="member",
                    )
            notifications.publish(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, scope_type="personal", scope_id=principal.account_id,
                category="payment", title="Demo 支付結果", body=f"狀態：{result['status']}",
                deep_link=f"/orders/{req.subject_id}", subject_type="payment", subject_id=result["id"],
                idempotency_key=f"payment:{result['id']}:{result['status']}",
            )
            return {"data": result}
        except DemoPaymentError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/payments/{payment_id}/cancel")
    def cancel_payment(
        payment_id: str,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": payments.cancel(
                payment_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
                idempotency_key=idempotency_key,
            )}
        except DemoPaymentError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/payments/{payment_id}/refund")
    def refund_payment(
        payment_id: str, req: PaymentRefundReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        require_role(principal, Role.PLATFORM_OPERATOR)
        try:
            owner = payments.get_in_demo(payment_id, demo_workspace_id=principal.demo_workspace_id)
            return {"data": payments.refund(
                payment_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=owner["workspaceId"], account_id=owner["accountId"],
                amount=req.amount, points=req.points, idempotency_key=idempotency_key,
            )}
        except DemoPaymentError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/notifications")
    def list_notifications(
        unread_only: bool = Query(default=False),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        return {"data": notifications.list_owned(
            demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
            account_id=principal.account_id, unread_only=unread_only,
        )}

    @router.post("/notifications/{notification_id}/read")
    def read_notification(
        notification_id: str,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": notifications.mark_read(
                notification_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
            )}
        except NotificationError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.put("/notification-preferences/quiet-hours")
    def set_quiet_hours(
        req: QuietHoursReq,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": notifications.set_quiet_hours(
                principal.account_id, start=req.start, end=req.end, timezone_name=req.timezone,
            )}
        except NotificationError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/calendar/events")
    def list_calendar_events(
        start: str | None = None, end: str | None = None,
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        memberships = access.list_memberships(principal.account_id)
        allowed = tuple(item["workspace"]["id"] for item in memberships)
        return {"data": calendar.list_owned(
            demo_workspace_id=principal.demo_workspace_id, account_id=principal.account_id,
            allowed_workspaces=allowed, start=start, end=end,
        )}

    @router.post("/calendar/events")
    def create_calendar_event(
        req: CalendarCreateReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        scope_type, scope_id = member_scope(principal)
        try:
            return {"data": calendar.create_manual(
                demo_workspace_id=principal.demo_workspace_id, workspace_id=principal.workspace_id,
                account_id=principal.account_id, scope_type=scope_type, scope_id=scope_id,
                title=req.title, starts_at=req.starts_at, ends_at=req.ends_at,
                all_day=req.all_day, note=req.note, recurrence=req.recurrence,
                idempotency_key=idempotency_key,
            )}
        except CalendarError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.patch("/calendar/events/{event_id}")
    def change_calendar_event(
        event_id: str, req: CalendarChangeReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_principal),
    ) -> dict:
        member_scope(principal)
        try:
            return {"data": calendar.change_manual_series(
                event_id, demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id, account_id=principal.account_id,
                mode=req.mode, occurrence_start=req.occurrence_start,
                changes=req.changes, idempotency_key=idempotency_key,
            )}
        except CalendarConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except CalendarError as exc:
            raise HTTPException(400, str(exc)) from exc

    # ── M8 Agent(spec 15 §4):與手動共用同一批服務實例與 submit/payment 閉包 ──
    if agent_orchestrator is not None and agent_sessions is not None and agent_grants is not None:

        def _agent_owner(principal: Principal) -> dict:
            member_scope(principal)
            return {
                "demo_workspace_id": principal.demo_workspace_id,
                "workspace_id": principal.workspace_id,
                "account_id": principal.account_id,
            }

        def _load_session(req_session_id: str | None, owner: dict) -> dict:
            if req_session_id:
                return agent_sessions.get(req_session_id, **owner)
            return agent_sessions.create(**owner)

        def _ready_subtasks(session: dict) -> list[dict]:
            return [item for item in session["subtasks"] if item["status"] == "ready"]

        def _propose_grant_if_needed(session: dict, owner: dict, principal: Principal) -> None:
            """全部子任務備齊且尚無授權 → 產生一張涵蓋全部子任務的 ExecutionGrant 提案。"""
            ready = _ready_subtasks(session)
            pending = [item for item in session["subtasks"]
                       if item["status"] in {"resolved", "fields", "clarify"}]
            if not ready or pending or session.get("grantId"):
                return
            providers = sorted({item["selected"]["providerId"] for item in ready})
            budget = sum(int(item.get("quote", {}).get("payable", 0)) for item in ready)
            dates = [item["selected"]["slot"]["startsAt"][:10]
                     for item in ready if item["selected"].get("slot")]
            window_start = min(dates) if dates else agent_orchestrator.time_resolver.today().isoformat()
            window_end = max(dates) if dates else window_start
            names = "、".join(item["selected"]["providerName"] for item in ready)
            grant = agent_grants.propose(
                **owner, session_id=session["id"], provider_ids=providers,
                window_start=window_start, window_end=window_end,
                budget_limit=budget, points_limit=0,
                summary=f"{names};時間 {window_start}~{window_end};預算上限 NT${budget:,};30 分鐘內有效",
            )
            session["grantId"] = grant["id"]
            session["awaiting"] = "grant"
            session["messages"].append({
                "role": "assistant",
                "content": (
                    f"執行授權內容:服務商 {names};時間範圍 {window_start}~{window_end};"
                    f"預算上限 NT${budget:,};不折抵點數;30 分鐘內有效。"
                    "核准後我才會實際送出訂單。"
                ),
            })

        def _execute_with_grant(session: dict, owner: dict, principal: Principal) -> None:
            """核准後執行:每個子任務 authorize→ready→(同一個 submit 閉包)→付款。"""
            grant_id = session.get("grantId")
            executed: list[str] = []
            for subtask in _ready_subtasks(session):
                option = subtask["selected"]
                amount = int(subtask.get("quote", {}).get("payable", 0))
                starts_at = option.get("slot", {}).get("startsAt") if option.get("slot") else None
                agent_grants.authorize_spend(
                    grant_id, **owner, provider_id=option["providerId"],
                    starts_at=starts_at, amount=amount, points=0,
                )
                draft = drafts.require_owned(subtask["draftId"], **owner)
                if draft["status"] == "drafting":
                    draft = drafts.transition(
                        subtask["draftId"], **owner,
                        expected_version=draft["version"], status="ready",
                    )
                result = submit_draft(
                    subtask["draftId"],
                    DraftSubmitReq(expected_version=draft["version"]),
                    idempotency_key=f"agent-{session['id']}-{subtask['id']}-submit",
                    principal=principal,
                )["data"]
                subtask["subjectType"] = result["subjectType"]
                subtask["subjectId"] = result["subjectId"]
                subtask["status"] = "submitted"
                # 產品規則(2026-07-31):預約類服務不預收款,最多做到預約;
                # 只有商品下單(commerce)才走 Demo 付款。
                if amount > 0 and result["subjectType"] == "commerce_order":
                    create_payment(
                        PaymentCreateReq(
                            subject_type=result["subjectType"], subject_id=result["subjectId"],
                            amount=amount, points_redeemed=0, outcome="success",
                        ),
                        idempotency_key=f"agent-{session['id']}-{subtask['id']}-pay",
                        principal=principal,
                    )
                executed.append(
                    f"{option['providerName']}・{option['offeringName']}(編號 {result['subjectId']})"
                )
            session["awaiting"] = None
            session["grantId"] = None  # 授權已消耗;下一個目標要重新提案與核准
            session["messages"].append({
                "role": "assistant",
                "content": "已完成:" + ";".join(executed) +
                "。進度、通知與行事曆都會同步更新,可到「我的訂單」追蹤。",
            })

        def _run_turn(req: AgentMessageReq, principal: Principal, on_stage=None) -> dict:
            owner = _agent_owner(principal)
            try:
                session = _load_session(req.session_id, owner)
            except AgentSessionError as exc:
                raise HTTPException(404, str(exc)) from exc

            action = req.action or {}
            kind = action.get("type")
            stages: list[str] = []

            def record_stage(name: str) -> None:
                stages.append(name)
                if on_stage:
                    on_stage(name)

            try:
                if kind == "approve_grant":
                    record_stage("核准授權")
                    agent_grants.approve(session["grantId"], **owner)
                    record_stage("建立訂單")
                    _execute_with_grant(session, owner, principal)
                elif kind == "revoke_grant":
                    if session.get("grantId"):
                        agent_grants.revoke(session["grantId"], **owner)
                    session["grantId"] = None
                    session["awaiting"] = "option"
                    session["messages"].append({
                        "role": "assistant",
                        "content": "已撤回授權,不會送出任何訂單。可以改方案或直接切到手動填寫。",
                    })
                else:
                    turn = agent_orchestrator.handle(
                        session, owner=owner,
                        message=req.message, action=req.action, on_stage=record_stage,
                    )
                    session = turn.session
                    _propose_grant_if_needed(session, owner, principal)
            except GrantError as exc:
                # 守門擋下:誠實告知,停在等待確認,不送單
                session["awaiting"] = "grant" if session.get("grantId") else session.get("awaiting")
                session["messages"].append({"role": "assistant", "content": str(exc)})
            except (DraftError, DraftConflict, DomainError) as exc:
                session["messages"].append({
                    "role": "assistant",
                    "content": f"這一步沒有完成:{exc}。表單內容可點「切到手動填寫」直接修改。",
                })
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "送單未完成,可稍後重試"
                session["messages"].append({
                    "role": "assistant",
                    "content": f"送出時被平台擋下:{detail}。沒有建立任何你未核准的交易。",
                })

            agent_sessions.save(session, **owner)
            return {"session": agent_sessions.to_public(session), "stages": stages}

        @router.post("/agent/messages")
        def agent_message(
            req: AgentMessageReq,
            principal: Principal = Depends(current_principal),
        ) -> dict:
            return {"data": _run_turn(req, principal)}

        @router.post("/agent/messages/stream")
        def agent_message_stream(
            req: AgentMessageReq,
            principal: Principal = Depends(current_principal),
        ) -> StreamingResponse:
            """NDJSON:先逐行送出可驗證階段,最後送完整結果(不含模型思考鏈)。"""

            def generate():
                staged: list[str] = []

                def on_stage(name: str) -> None:
                    staged.append(name)

                result = _run_turn(req, principal, on_stage=on_stage)
                for name in result["stages"] or staged:
                    yield json.dumps({"stage": name}, ensure_ascii=False) + "\n"
                yield json.dumps({"result": result}, ensure_ascii=False) + "\n"

            return StreamingResponse(generate(), media_type="application/x-ndjson")

        @router.get("/agent/sessions/latest")
        def agent_latest_session(principal: Principal = Depends(current_principal)) -> dict:
            owner = _agent_owner(principal)
            session = agent_sessions.latest(**owner)
            return {"data": agent_sessions.to_public(session) if session else None}

        @router.get("/agent/sessions/{session_id}")
        def agent_get_session(
            session_id: str, principal: Principal = Depends(current_principal),
        ) -> dict:
            owner = _agent_owner(principal)
            try:
                return {"data": agent_sessions.to_public(agent_sessions.get(session_id, **owner))}
            except AgentSessionError as exc:
                raise HTTPException(404, str(exc)) from exc

        @router.get("/agent/grants/{grant_id}")
        def agent_get_grant(
            grant_id: str, principal: Principal = Depends(current_principal),
        ) -> dict:
            owner = _agent_owner(principal)
            try:
                return {"data": agent_grants.get(grant_id, **owner)}
            except GrantError as exc:
                raise HTTPException(404, str(exc)) from exc

    return router
