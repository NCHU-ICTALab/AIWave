"""AI-guided form API with deterministic validation and persistent inquiry writes."""

from __future__ import annotations

import json

import httpx
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent.form_agent import FormAgent
from agent.intent_agent import IntentAgent
from agent.planner import Plan, PlanStep, Planner, safety_response_for
from core.clients import LlmClient, get_llm
from core.access import AccessError, Principal, Role, SqliteAccessRepository, WorkspaceKind
from core.communities import SqliteCommunityRepository
from core.forms import Form, FormError, FormSession
from core.forms.dto import topic_to_field
from core.forms.service_catalog import get_service as catalog_service
from core.forms.service_catalog import get_service_form as catalog_service_form
from core.forms.service_catalog import list_services as list_catalog_services
from core.agent_core import ServiceRegistry, SqliteGrantRepository, TimeResolver
from core.agent_core.orchestrator import AgentOrchestrator
from core.agent_core.sessions import SqliteAgentSessionStore
from core.data.personas import PERSONAS, get_persona
from core.demo_reset import DemoResetService
from core.groups import GroupError, GroupPermissionError, GroupRepository, SqliteGroupRepository
from core.community import (
    GroupBuyError,
    GroupBuyRepository,
    JointServiceError,
    JointServiceRepository,
    SqliteGroupBuyRepository,
    SqliteJointServiceRepository,
)
from core.inquiries import InquiryRepository, InquiryTransitionError, SqliteInquiryRepository
from core.personalization import PersonalizationService, SqlitePersonalizationRepository
from core.orders import SqliteOrderRepository
from core.retail import (
    RetailConnector,
    RetailService,
    SqliteRetailRepository,
    build_retail_connector,
)
from core.config import get_settings
from core.support import SupportError, SupportRepository, SupportService, SqliteSupportRepository
from core.insights.today import build_briefing
from core.life_tasks import (
    LifeTaskError,
    LifeTaskNotApplicable,
    LifeTaskService,
    LifeTaskUpstreamError,
    SqliteLifeTaskRepository,
)
from core.services import CommunityService, InsightsService, LifeServicesService
from core.sessions import ConversationState, InMemorySessionStore, SessionStore
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext
from core.vendors import VendorClient, VendorClientError, VendorService, build_vendor_client
from api.platform_access import build_access_router, build_principal_dependency
from api.platform_core import build_platform_core_router
from core.calendar import SqliteCalendarRepository
from core.catalog import CatalogSyncService, SqliteCatalogRepository
from core.fulfillment import SqliteFulfillmentRepository
from core.notifications import SqliteNotificationRepository
from core.payments import SqliteDemoPaymentAdapter
from core.points import SqlitePointsLedger
from core.providers import ProviderBookingService, ProviderConnector, build_provider_connector
from core.task_drafts import SqliteTaskDraftRepository

_CONFIRM_WORDS = {"對", "好", "沒問題", "確認", "確認送出", "送出", "可以", "ok", "yes", "是", "嗯"}


@dataclass
class LiveSession:
    """由 `ConversationState` 重建出來的請求內物件。

    只在單一請求存活；狀態一律回寫 `SessionStore`（[ADR-0018]）。
    `FormAgent` 無狀態、`FormSession` 可由既有答案重建，所以不需要跨請求保存物件。
    """

    state: ConversationState
    form: Form
    session: FormSession
    agent: FormAgent


class UpstreamFaultReq(BaseModel):
    """admin 故障注入代理:preset 動作,control key 不出後端。"""
    action: str = "timeout"            # timeout | http_503 | clear
    method: str = "POST"
    path: str = "/partner/v1/bookings"


class StartReq(BaseModel):
    """以服務目錄的 service_id 開啟對話——與網頁表單讀同一份題組定義。"""

    service_id: str


class MsgReq(BaseModel):
    session_id: str
    message: str
    #: 送出諮詢單時要記錄是誰的委託（住戶只能看到自己的單）
    account_id: str | None = None


class QuoteReq(BaseModel):
    answers: dict[str, Any] = {}


class OrderReq(QuoteReq):
    account_id: str


class ServiceSubmissionReq(QuoteReq):
    pass


class IntentReq(BaseModel):
    need: str


class QuoteItem(BaseModel):
    name: str
    amount: int


class CreateQuoteReq(BaseModel):
    items: list[QuoteItem]
    vendor_name: str = "合作廠商"


class CompleteReq(BaseModel):
    note: str | None = None


class ReviseReq(BaseModel):
    """住戶請廠商重新報價；`note` 必填——沒說要改什麼，廠商只能重猜一次。"""

    note: str


class CancelReq(BaseModel):
    reason: str | None = None


class CreateCampaignReq(BaseModel):
    title: str
    item_name: str
    unit_price: int
    unit: str = "份"
    min_quantity: int = 1
    close_time: str | None = None
    pickup: str | None = None


class JoinCampaignReq(BaseModel):
    account_id: str
    display_name: str = "住戶"
    quantity: int = 1


class JointServiceDraftReq(BaseModel):
    title: str
    service_id: str = "service-aircon"


class JointServiceAssignReq(BaseModel):
    proposal_id: str


class JointServiceCompleteReq(BaseModel):
    note: str


class JointServiceJoinReq(BaseModel):
    units: int
    equipment: str
    preferred_slot: str
    special_requirement: str | None = None
    consent: Literal[True]


class CreateGroupReq(BaseModel):
    name: str
    display_name: str = "會員"


class JoinGroupReq(BaseModel):
    invite_code: str
    display_name: str = "會員"


class RenameGroupReq(BaseModel):
    name: str


class PlanReq(BaseModel):
    """一句口語 ＋ 呼叫者身分。身分由前端的登入狀態帶入，不由 LLM 決定。"""

    message: str
    account_id: str | None = None
    role: str = "user"
    display_name: str = "住戶"


class ExecutePlanReq(PlanReq):
    """執行計畫；`approved` 是使用者已點頭的寫入步驟索引。"""

    steps: list[dict] = []
    approved: list[int] = []


class RecommendationFeedbackReq(BaseModel):
    recommendation_id: str
    action: str


class ReminderReq(BaseModel):
    item_name: str
    cadence_days: int
    next_due_on: str


class LifeTaskDraftReq(BaseModel):
    message: str


class LifeTaskConfigureReq(BaseModel):
    expected_version: int
    scheduled_date: str
    address_choice: str
    scope: str
    selected_vendors: dict[str, str] = Field(default_factory=dict)
    custom_address: dict[str, Any] | None = None


class LifeTaskConfirmReq(BaseModel):
    expected_version: int


class LifeTaskAcceptQuotesReq(LifeTaskConfirmReq):
    selected_quotes: dict[str, str] = Field(default_factory=dict)


class StockWatchReq(BaseModel):
    account_id: str
    product_id: str
    store_id: str


class SupportIssueReq(BaseModel):
    subject_id: str
    issue_text: str


class SupportTicketReq(SupportIssueReq):
    diagnosis_token: str


class SupportActionReq(BaseModel):
    note: str | None = None


def _support_http_context(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ToolContext:
    """Compatibility ToolContext derived only from the verified Platform principal.

    ``X-Account-Id`` and ``X-Role`` are intentionally ignored.  Legacy application
    services can keep their ToolContext boundary while identity authority moves to
    Account/RoleMembership/Workspace.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            401, "請提供 Bearer 存取憑證", headers={"WWW-Authenticate": "Bearer"},
        )
    access: SqliteAccessRepository = request.app.state.access_repository
    try:
        principal = access.resolve_bearer(authorization[7:].strip())
    except AccessError as exc:
        raise HTTPException(
            401, "存取憑證無效", headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if principal.role is Role.MEMBER:
        return ToolContext(
            account_id=principal.account_id, role="user", display_name=principal.display_name,
        )
    if principal.role is Role.COMMUNITY_MANAGER:
        return ToolContext(
            account_id=principal.account_id, role="manager", display_name=principal.display_name,
        )
    if principal.role is Role.PARTNER_STAFF:
        return ToolContext(
            account_id=principal.provider_id, role="partner", display_name=principal.display_name,
        )
    raise HTTPException(403, "平台營運角色不可代替會員、社區或合作方執行舊流程")


def _require_support_role(context: ToolContext, role: str) -> str:
    if context.role != role:
        raise HTTPException(403, "目前身分無法使用這項客服能力")
    if role == "user" and not context.account_id:
        raise HTTPException(401, "請先登入住戶帳號")
    return context.account_id or ""


def _progress(session: FormSession) -> dict[str, int]:
    return session.progress()


def _is_confirmation(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized.startswith(("不", "不要", "取消", "修改")):
        return False
    return normalized in _CONFIRM_WORDS


def create_app(
    *,
    repository: InquiryRepository | None = None,
    group_buys: GroupBuyRepository | None = None,
    joint_services: JointServiceRepository | None = None,
    groups: GroupRepository | None = None,
    sessions: SessionStore | None = None,
    personalization_repository: SqlitePersonalizationRepository | None = None,
    retail_repository: SqliteRetailRepository | None = None,
    retail_connector: RetailConnector | None = None,
    vendor_client: VendorClient | None = None,
    life_task_repository: SqliteLifeTaskRepository | None = None,
    order_repository: SqliteOrderRepository | None = None,
    support_repository: SupportRepository | None = None,
    access_repository: SqliteAccessRepository | None = None,
    community_repository: SqliteCommunityRepository | None = None,
    task_draft_repository: SqliteTaskDraftRepository | None = None,
    fulfillment_repository: SqliteFulfillmentRepository | None = None,
    points_ledger: SqlitePointsLedger | None = None,
    payment_adapter: SqliteDemoPaymentAdapter | None = None,
    notification_repository: SqliteNotificationRepository | None = None,
    calendar_repository: SqliteCalendarRepository | None = None,
    provider_connector: ProviderConnector | None = None,
    provider_connectors: dict[str, ProviderConnector] | None = None,
    llm_factory: Callable[[], LlmClient] = get_llm,
    today: date | None = None,
    demo_db_path: str | Path | None = None,
) -> FastAPI:
    config = get_settings()
    resolved_today = today or config.demo_today
    demo_db = Path(demo_db_path or config.inquiry_db_path)
    demo_now = lambda: datetime(  # noqa: E731
        resolved_today.year, resolved_today.month, resolved_today.day, tzinfo=timezone.utc
    )
    inquiry_repository = repository or SqliteInquiryRepository(demo_db, now=demo_now)
    access = access_repository or SqliteAccessRepository(demo_db, now=demo_now)
    group_buy_repository = group_buys or SqliteGroupBuyRepository(demo_db, now=demo_now)
    joint_service_repository = joint_services or SqliteJointServiceRepository(demo_db, now=demo_now)
    group_repository = groups or SqliteGroupRepository(demo_db, now=demo_now, access=access)
    communities = community_repository or SqliteCommunityRepository(demo_db, now=demo_now, access=access)
    task_drafts = task_draft_repository or SqliteTaskDraftRepository(demo_db, now=demo_now)
    fulfillment = fulfillment_repository or SqliteFulfillmentRepository(demo_db, now=demo_now)
    demo_points = points_ledger or SqlitePointsLedger(demo_db, now=demo_now)
    demo_payments = payment_adapter or SqliteDemoPaymentAdapter(demo_db, points=demo_points, now=demo_now)
    notifications = notification_repository or SqliteNotificationRepository(demo_db, now=demo_now)
    calendar = calendar_repository or SqliteCalendarRepository(demo_db, now=demo_now)
    # M8 Agent:守門模組與對話持久化;LLM 一律走 llm_factory(正式=.env 的真實模型)
    agent_grants = SqliteGrantRepository(demo_db, now=demo_now)
    agent_sessions_store = SqliteAgentSessionStore(demo_db, now=demo_now)
    for persona in PERSONAS:
        demo_points.post(
            demo_workspace_id="demo-default",
            workspace_id=f"workspace-personal-{persona.id}",
            account_id=persona.id,
            entry_type="earn",
            amount=180,
            description="Demo 初始 OPENPOINT 情境點數",
            reference_type="seed",
            reference_id="platform-demo-v2",
            idempotency_key=f"seed:points:{persona.id}:v2",
        )
    session_store: SessionStore = sessions or InMemorySessionStore()
    life_services = LifeServicesService(
        inquiry_repository,
        orders=order_repository or SqliteOrderRepository(demo_db, now=demo_now),
        today=resolved_today,
    )
    insights = InsightsService(today=resolved_today)
    community = CommunityService(group_buy_repository)
    personalization = PersonalizationService(
        personalization_repository or SqlitePersonalizationRepository(demo_db, now=demo_now),
        today=resolved_today,
    )
    configured_retail_connector = retail_connector or build_retail_connector(
        upstream_url=config.retail_upstream_url,
        timeout_seconds=config.upstream_timeout_seconds,
    )
    retail = RetailService(
        retail_repository or SqliteRetailRepository(demo_db, now=demo_now),
        connector=configured_retail_connector,
    )
    configured_vendor_client = vendor_client or build_vendor_client(
        mode=config.vendor_mode,
        fake_url=config.vendor_fake_url,
        real_url=config.vendor_real_url,
        api_token=config.vendor_api_token,
        timeout_seconds=config.vendor_timeout_seconds,
    )
    if config.partner_mode not in {"fake", "real"}:
        raise ValueError("PARTNER_MODE 只接受 fake 或 real")
    partner_url = config.partner_fake_url if config.partner_mode == "fake" else config.partner_real_url
    configured_provider_connector = provider_connector or build_provider_connector(
        mode=config.provider_mode,
        provider_id=config.provider_id,
        database=demo_db,
        standard_url=partner_url,
        standard_api_key=config.partner_api_key,
        timeout_seconds=config.partner_timeout_seconds,
        vendor_client=configured_vendor_client,
    )
    # M4:每個場景 Provider 各自的 connector(六場景多廠商)。測試可注入
    # provider_connectors 覆蓋;未注入時對同一 Partner API 端點用各廠商的 key。
    configured_provider_connectors = provider_connectors
    if configured_provider_connectors is None:
        configured_provider_connectors = {
            pid: build_provider_connector(
                mode="standard",
                provider_id=pid,
                database=demo_db,
                standard_url=partner_url,
                standard_api_key=key,
                timeout_seconds=config.partner_timeout_seconds,
                vendor_client=configured_vendor_client,
            )
            for pid, key in config.partner_provider_keys.items()
        }
        # 單廠商模式的舊 connector 仍是該 provider 的權威(例如 workbench/adapter 模式)
        configured_provider_connectors[config.provider_id] = configured_provider_connector
    provider_bookings = ProviderBookingService(
        demo_db, fulfillment=fulfillment, connector=configured_provider_connector,
        connectors=configured_provider_connectors, now=demo_now,
    )
    catalog_projection = SqliteCatalogRepository(demo_db, now=demo_now)
    catalog_sync = CatalogSyncService(catalog_projection, connectors=configured_provider_connectors)
    agent_orchestrator = AgentOrchestrator(
        llm_factory=llm_factory,
        registry=ServiceRegistry(),
        time_resolver=TimeResolver(now=lambda: datetime(
            resolved_today.year, resolved_today.month, resolved_today.day,
            9, 0, tzinfo=timezone(timedelta(hours=8)),
        )),
        catalog=catalog_projection,
        drafts=task_drafts,
        points=demo_points,
    )
    vendor_service = VendorService(configured_vendor_client)
    life_tasks = LifeTaskService(
        life_task_repository or SqliteLifeTaskRepository(demo_db, now=demo_now),
        vendors=vendor_service,
        today=resolved_today,
    )
    support = SupportService(
        support_repository or SqliteSupportRepository(demo_db, now=demo_now),
        inquiries=inquiry_repository,
        orders=life_services.orders,
        now=demo_now,
    )
    life_services_catalog = list_catalog_services
    # 能力層：規劃器與 MCP server 共用這一份（ADR-0017）
    tool_registry = build_registry(
        services=life_services,
        group_buys=group_buy_repository,
        joint_services=joint_service_repository,
        personalization=personalization,
        retail=retail,
        support=support,
        vendors=vendor_service,
        life_tasks=life_tasks,
        today=resolved_today,
    )
    application = FastAPI(title="智慧生活管家 AI API")

    if config.catalog_sync_on_startup:
        # 只在真正啟動伺服器(uvicorn lifespan)時同步目錄;TestClient 不觸發,
        # 測試各自決定何時同步。失敗不擋啟動,/catalog/health 誠實回報。
        @application.on_event("startup")
        def _sync_catalog_on_startup() -> None:  # pragma: no cover - 啟動旁路
            try:
                catalog_sync.sync_all()
            except Exception:  # noqa: BLE001
                pass
    application.include_router(build_access_router(access=access, communities=communities))
    application.include_router(build_platform_core_router(
        access=access,
        drafts=task_drafts,
        fulfillment=fulfillment,
        points=demo_points,
        payments=demo_payments,
        notifications=notifications,
        calendar=calendar,
        provider_bookings=provider_bookings,
        catalog_projection=catalog_projection,
        catalog_sync=catalog_sync,
        agent_orchestrator=agent_orchestrator,
        agent_sessions=agent_sessions_store,
        agent_grants=agent_grants,
    ))
    application.state.access_repository = access
    application.state.community_repository = communities
    application.state.task_draft_repository = task_drafts
    application.state.fulfillment_repository = fulfillment
    application.state.points_ledger = demo_points
    application.state.payment_adapter = demo_payments
    application.state.notification_repository = notifications
    application.state.calendar_repository = calendar
    application.state.provider_connector = configured_provider_connector
    application.state.provider_connectors = configured_provider_connectors
    application.state.provider_booking_service = provider_bookings
    application.state.catalog_repository = catalog_projection
    application.state.catalog_sync_service = catalog_sync
    reset_service = DemoResetService(
        demo_db,
        access=access,
        points=demo_points,
        now=demo_now,
        session_store=session_store,
        partner_fake_url=config.partner_fake_url if config.partner_mode == "fake" else "",
        partner_control_key=config.vendor_fake_control_key,
        retail_fake_url=config.retail_upstream_url,
        retail_control_key=config.retail_fake_control_key,
        timeout_seconds=max(config.upstream_timeout_seconds, config.partner_timeout_seconds),
        catalog_sync=catalog_sync,
    )
    current_platform_principal = build_principal_dependency(access)

    def require_member_principal(
        principal: Principal,
        requested_account_id: str | None = None,
    ) -> str:
        if principal.role is not Role.MEMBER:
            raise HTTPException(403, "只有會員能使用這項功能")
        if requested_account_id not in {None, "me", principal.account_id}:
            # Do not reveal whether the requested demo account exists.
            raise HTTPException(404, "查無會員資料")
        return principal.account_id

    def require_manager_principal(principal: Principal) -> str:
        if principal.role is not Role.COMMUNITY_MANAGER or not principal.community_id:
            raise HTTPException(403, "只有目前社區的管理者能使用這項功能")
        return principal.community_id

    @application.post("/api/v1/platform/demo/reset")
    def reset_platform_demo(
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """Reset only the caller's personal workspace, or the full demo as operator."""
        if not config.demo_reset_enabled:
            raise HTTPException(404, "Demo 重設功能未啟用")
        if principal.role is Role.PLATFORM_OPERATOR and "demo:reset" in principal.scopes:
            return {"data": reset_service.reset_demo(
                demo_workspace_id=principal.demo_workspace_id,
            )}
        if principal.role is not Role.MEMBER or principal.workspace_kind is not WorkspaceKind.PERSONAL:
            raise HTTPException(403, "只有個人工作空間或平台營運者可以重設 Demo")
        return {"data": reset_service.reset_member(
            demo_workspace_id=principal.demo_workspace_id,
            workspace_id=principal.workspace_id,
            account_id=principal.account_id,
        )}

    def _require_operator(principal: Principal) -> None:
        if principal.role is not Role.PLATFORM_OPERATOR or "demo:reset" not in principal.scopes:
            raise HTTPException(403, "只有平台營運者能使用這項功能")

    @application.post("/api/v1/platform/admin/workspaces/{membership_id}/reset")
    def reset_persona_workspace(
        membership_id: str,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """重置單一固定 Demo persona 的個人 workspace(aiwave-admin 專用;非無限制越權)。"""
        _require_operator(principal)
        if not config.demo_reset_enabled:
            raise HTTPException(404, "Demo 重設功能未啟用")
        try:
            membership = access.describe_membership(membership_id)
        except Exception as exc:  # noqa: BLE001 - 不洩漏內部細節
            raise HTTPException(404, "查無此 Demo persona") from exc
        workspace = membership.get("workspace") or {}
        if workspace.get("kind") not in {"personal", WorkspaceKind.PERSONAL.value}:
            raise HTTPException(422, "只能重置個人 workspace;整體 Demo 請用 demo/reset")
        return {"data": reset_service.reset_member(
            demo_workspace_id=membership["demoWorkspaceId"],
            workspace_id=workspace["id"],
            account_id=membership["accountId"],
        )}

    @application.get("/api/v1/platform/admin/upstream-health")
    def upstream_health(
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """fake upstream 健康與 seed version 一致性(operator;由平台代理,瀏覽器不持有 control key)。"""
        _require_operator(principal)
        base_url = config.partner_fake_url if config.partner_mode == "fake" else ""
        if not base_url:
            return {"data": {"status": "disabled", "seedVersion": None, "platformSeedVersions": []}}
        try:
            response = httpx.get(f"{base_url}/healthz", timeout=5.0)
            response.raise_for_status()
            payload = response.json()
            upstream = {"status": payload.get("status", "ok"), "seedVersion": payload.get("seedVersion")}
        except (httpx.HTTPError, ValueError):
            upstream = {"status": "unavailable", "seedVersion": None}
        projection_versions = sorted({
            row.get("seedVersion") for row in catalog_projection.health()
        }) if catalog_projection is not None else []
        return {"data": {
            **upstream,
            "platformSeedVersions": projection_versions,
            "consistent": upstream["seedVersion"] is not None
            and projection_versions == [upstream["seedVersion"]],
        }}

    @application.post("/api/v1/platform/admin/upstream-faults")
    def inject_upstream_fault(
        req: UpstreamFaultReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """把一次性故障注入 fake upstream(operator 專用代理;control key 只存在後端)。"""
        _require_operator(principal)
        base_url = config.partner_fake_url if config.partner_mode == "fake" else ""
        control_key = config.vendor_fake_control_key
        if not base_url or not control_key:
            raise HTTPException(503, "fake upstream 未設定,無法注入故障")
        try:
            if req.action == "clear":
                response = httpx.delete(
                    f"{base_url}/__fake__/faults",
                    headers={"X-Fake-Control-Key": control_key}, timeout=5.0,
                )
            else:
                preset = {
                    "timeout": {"status": 504, "detail": "注入:回應逾時", "delay_ms": 1500},
                    "http_503": {"status": 503, "detail": "注入:上游暫時無法服務", "delay_ms": 0},
                }[req.action]
                response = httpx.put(
                    f"{base_url}/__fake__/faults/next",
                    headers={"X-Fake-Control-Key": control_key},
                    json={
                        "method": req.method, "path": req.path,
                        "status": preset["status"], "detail": preset["detail"],
                        "delay_ms": preset["delay_ms"], "after_commit": False,
                    },
                    timeout=5.0,
                )
            response.raise_for_status()
            payload = response.json()
            return {"data": {"action": req.action, "result": payload.get("data", payload)}}
        except httpx.HTTPError as exc:
            raise HTTPException(503, f"fake upstream 無法連線:{exc}") from exc

    # 跨服務生活任務：草稿可補條件；只有 confirm 才向廠商 upstream 寫入。
    @application.post("/api/v1/life-tasks/draft")
    def create_life_task_draft(
        req: LifeTaskDraftReq, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        persona = get_persona(account_id)
        try:
            return {"data": life_tasks.create_draft(
                message=req.message, account_id=account_id,
                display_name=persona.name if persona is not None else context.display_name,
            )}
        except LifeTaskNotApplicable as exc:
            raise HTTPException(422, {"code": "NOT_APPLICABLE", "message": str(exc)}) from exc
        except LifeTaskError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.put("/api/v1/life-tasks/{task_id}/configuration")
    def configure_life_task(
        task_id: str, req: LifeTaskConfigureReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": life_tasks.configure(
                task_id, account_id=account_id, expected_version=req.expected_version,
                scheduled_date=req.scheduled_date, address_choice=req.address_choice,
                scope=req.scope, selected_vendors=req.selected_vendors,
                custom_address=req.custom_address,
            )}
        except LifeTaskError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/life-tasks/{task_id}/confirm")
    def confirm_life_task(
        task_id: str, req: LifeTaskConfirmReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": life_tasks.confirm(
                task_id, account_id=account_id, expected_version=req.expected_version,
            )}
        except LifeTaskUpstreamError as exc:
            raise HTTPException(502, str(exc)) from exc
        except LifeTaskError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/life-tasks/{task_id}/accept-quotes")
    def accept_life_task_quotes(
        task_id: str, req: LifeTaskAcceptQuotesReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": life_tasks.accept_quotes(
                task_id, account_id=account_id, expected_version=req.expected_version,
                selected_quotes=req.selected_quotes,
            )}
        except (LifeTaskError, VendorClientError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.get("/api/v1/life-tasks/{task_id}")
    def get_life_task(task_id: str, context: ToolContext = Depends(_support_http_context)) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": life_tasks.get(task_id, account_id=account_id)}
        except LifeTaskError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.get("/api/v1/life-tasks")
    def list_life_tasks(context: ToolContext = Depends(_support_http_context)) -> dict:
        account_id = _require_support_role(context, "user")
        return {"data": life_tasks.list_for_account(account_id)}

    # 廠商 API 一律由平台轉接。Vue、Agent 與 MCP 都不直接碰 fake/real 上游。
    @application.get("/api/v1/vendor-api/availability")
    def vendor_availability(vendor_id: str, service_id: str, date: str | None = None) -> dict:
        try:
            return vendor_service.get_availability(vendor_id=vendor_id, service_id=service_id, date=date)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.post("/api/v1/vendor-api/inquiries")
    def vendor_create_inquiry(
        payload: dict = Body(...), idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        if payload.get("accountId") != account_id:
            raise HTTPException(403, "不能替其他會員建立廠商諮詢單")
        try:
            return vendor_service.create_inquiry(payload, idempotency_key=idempotency_key)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.get("/api/v1/vendor-api/inquiries")
    def vendor_list_inquiries(
        vendor_id: str | None = None, status: str | None = None, account_id: str | None = None,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        assigned_vendor = _require_support_role(context, "partner")
        if vendor_id and vendor_id != assigned_vendor:
            raise HTTPException(403, "不能查看其他廠商的諮詢單")
        try:
            return vendor_service.list_inquiries(vendorId=assigned_vendor, status=status, accountId=account_id)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.get("/api/v1/vendor-api/inquiries/{inquiry_id}")
    def vendor_get_inquiry(
        inquiry_id: str, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        vendor_id = _require_support_role(context, "partner")
        try:
            result = vendor_service.get_inquiry(inquiry_id)
            if result["data"].get("vendorId") != vendor_id:
                raise HTTPException(404, "查無諮詢單")
            return result
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.get("/api/v1/vendor-api/inquiries/{inquiry_id}/quotes")
    def vendor_list_quotes(
        inquiry_id: str, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        vendor_id = _require_support_role(context, "partner")
        try:
            if vendor_service.get_inquiry(inquiry_id)["data"].get("vendorId") != vendor_id:
                raise HTTPException(404, "查無諮詢單")
            return vendor_service.list_quotes(inquiry_id)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.post("/api/v1/vendor-api/inquiries/{inquiry_id}/quotes")
    def vendor_create_quote(
        inquiry_id: str, payload: dict = Body(...),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        vendor_id = _require_support_role(context, "partner")
        if payload.get("vendorId") != vendor_id:
            raise HTTPException(403, "不能替其他廠商報價")
        try:
            if vendor_service.get_inquiry(inquiry_id)["data"].get("vendorId") != vendor_id:
                raise HTTPException(404, "查無諮詢單")
            return vendor_service.create_quote(inquiry_id, payload, idempotency_key=idempotency_key)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.post("/api/v1/vendor-api/orders")
    def vendor_create_order(
        payload: dict = Body(...), idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        if payload.get("accountId") != account_id:
            raise HTTPException(403, "不能替其他會員建立廠商訂單")
        try:
            return vendor_service.create_order(payload, idempotency_key=idempotency_key)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.get("/api/v1/vendor-api/orders")
    def vendor_list_orders(
        vendor_id: str | None = None, status: str | None = None, account_id: str | None = None,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        assigned_vendor = _require_support_role(context, "partner")
        if vendor_id and vendor_id != assigned_vendor:
            raise HTTPException(403, "不能查看其他廠商的訂單")
        try:
            return vendor_service.list_orders(vendorId=assigned_vendor, status=status, accountId=account_id)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.get("/api/v1/vendor-api/orders/{order_id}")
    def vendor_get_order(order_id: str, context: ToolContext = Depends(_support_http_context)) -> dict:
        vendor_id = _require_support_role(context, "partner")
        try:
            result = vendor_service.get_order(order_id)
            if result["data"].get("vendorId") != vendor_id:
                raise HTTPException(404, "查無訂單")
            return result
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.post("/api/v1/vendor-api/orders/{order_id}/events")
    def vendor_append_order_event(
        order_id: str, payload: dict = Body(...),
        idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        vendor_id = _require_support_role(context, "partner")
        try:
            if vendor_service.get_order(order_id)["data"].get("vendorId") != vendor_id:
                raise HTTPException(404, "查無訂單")
            return vendor_service.append_order_event(order_id, payload, idempotency_key=idempotency_key)
        except VendorClientError as exc:
            raise HTTPException(502, str(exc)) from exc

    @application.get("/api/forms")
    def list_forms() -> list[dict]:
        """沿用舊路徑：回傳可對話的服務（即服務目錄）。"""
        return [{"id": service.id, "name": service.name} for service in life_services_catalog()]

    def _question(live: LiveSession, topic) -> dict | None:
        """把當前題目序列化成可渲染的形式，讓介面能畫成按鈕。"""
        return None if topic is None else topic_to_field(live.form, topic, today=resolved_today)

    def _revive(state: ConversationState) -> LiveSession:
        """由儲存的狀態重建這次請求要用的物件。"""
        form = catalog_service_form(state.service_id)
        if form is None:
            raise HTTPException(404, "查無服務")
        session = FormSession(form, today=resolved_today, known=dict(state.answers))
        for topic_id in state.skipped:
            # 略過紀錄要一併還原，否則重建後又會問一次已經略過的題目
            session.mark_skipped(topic_id)
        return LiveSession(state=state, form=form, session=session, agent=FormAgent(llm_factory(), today=resolved_today))

    def _persist(live: LiveSession) -> None:
        """把狀態寫回儲存層。

        刻意**不**存 `session.answers`——那裡放的是驗證後的 `Selection` 物件，
        序列化不了。狀態保存的是使用者/AI 提供的原始答案，重建時重新走一次
        `submit_answer` 驗證。這樣規則永遠是權威，也不會有「存進去的值繞過了驗證」。
        """
        live.state.skipped = sorted(live.session.skipped_ids)
        session_store.save(live.state)

    @application.post("/api/chat/start")
    def start(
        req: StartReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        if principal.role is not Role.MEMBER:
            raise HTTPException(403, "只有會員能開始服務對話")
        service = catalog_service(req.service_id)
        form = catalog_service_form(req.service_id)
        if service is None or form is None:
            raise HTTPException(404, "查無服務")
        session_id = uuid4().hex
        state = ConversationState(
            session_id=session_id, service_id=req.service_id, account_id=principal.account_id,
        )
        live = _revive(state)
        session, agent = live.session, live.agent
        _persist(live)
        first = session.next_topic()
        reply = (
            f"好的，我幫您安排「{service.name}」。\n{agent.question_text(first)}"
            if first else f"好的，我幫您安排「{service.name}」。"
        )
        return {
            "session_id": session_id,
            "service_id": service.id,
            "service_name": service.name,
            "reply": reply,
            "question": _question(live, first),
            "done": first is None,
            "awaiting_confirmation": False,
            "progress": _progress(session),
            "trace": [{"stage": "tool", "tool": "get_service_form", "status": "completed"}],
        }

    def _message_payload(req: MsgReq, *, account_id: str) -> dict:
        stored = session_store.get(req.session_id)
        if stored is None:
            raise HTTPException(404, "工作階段不存在，請重新開始")
        if stored.account_id != account_id:
            raise HTTPException(404, "工作階段不存在，請重新開始")
        live = _revive(stored)
        state = live.state
        text = req.message.strip()

        if state.submitted_id:
            is_order = state.submitted_id.startswith("ORD-")
            record = life_services.get_order(state.submitted_id) if is_order else life_services.get_inquiry(state.submitted_id)
            assert record is not None
            operation = {"type": "order.created" if is_order else "inquiry.created", "id": record["id"], "status": record["status"]}
            return {"reply": "訂單已建立。" if is_order else "諮詢單已建立。", "done": True, "operation": operation, "progress": _progress(live.session), "trace": []}

        if state.awaiting_confirm:
            if _is_confirmation(text):
                is_order = live.form.action.value == "order"
                if is_order:
                    keyed_answers = {
                        topic.key: state.answers[topic.id]
                        for topic in live.form.ordered_topics()
                        if topic.id in state.answers
                    }
                    record = life_services.create_order(
                        service_id=live.form.service_id,
                        answers=keyed_answers,
                        account_id=account_id,
                        idempotency_key=f"chat:{state.session_id}:submit",
                    )
                else:
                    record = life_services.submit_inquiry(
                        form_id=live.form.id,
                        feedback_content=live.session.to_feedback_content(),
                        service_id=live.form.service_id,
                        account_id=account_id,
                        idempotency_key=f"chat:{state.session_id}:submit",
                    )
                state.submitted_id = record["id"]
                _persist(live)
                operation = {"type": "order.created" if is_order else "inquiry.created", "id": record["id"], "status": record["status"]}
                return {
                    "reply": (
                        f"已建立訂單 {record['id']}，應付 NT${record['amount']:,}，可到訂單頁追蹤。"
                        if is_order else f"已建立諮詢單 {record['id']}，合作夥伴稍後會回覆報價。"
                    ),
                    "done": True,
                    "awaiting_confirmation": False,
                    "operation": operation,
                    "progress": _progress(live.session),
                    "trace": [{"stage": "write", "tool": "create_order" if is_order else "submit_inquiry", "status": "completed", "result_id": record["id"]}],
                }
            return {
                "reply": "還沒送出。內容沒問題的話按「確認送出」，需要修改請告訴我要改哪一項。",
                "done": False,
                "awaiting_confirmation": True,
                "progress": _progress(live.session),
                "trace": [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
            }

        current = live.session.next_topic()
        if current is None:
            state.awaiting_confirm = True
            _persist(live)
            return {
                "reply": live.agent.summary_text(live.session.to_feedback_content()),
                "done": False,
                "awaiting_confirmation": True,
                "progress": _progress(live.session),
                "trace": [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
            }

        interpretation = live.agent.interpret(current, text)
        trace: list[dict[str, Any]] = [{
            "stage": "ai", "tool": "extract_form_answer", "status": "completed" if interpretation.action != "unclear" else "needs_retry",
            "topic_id": current.id,
        }]
        if interpretation.action == "unclear":
            return {
                "reply": f"{interpretation.note}\n{live.agent.question_text(current)}",
                "question": _question(live, current),
                "done": False,
                "awaiting_confirmation": False,
                "progress": _progress(live.session),
                "trace": trace,
            }
        try:
            if interpretation.action == "skip":
                live.session.skip(current.id)
            else:
                live.session.submit_answer(current.id, interpretation.value)
                # 通過驗證才記錄；記的是原始值，重建時會再驗一次
                state.answers[current.id] = jsonable_encoder(interpretation.value)
        except FormError as exc:
            trace.append({"stage": "rule", "tool": "validate_form_answer", "status": "rejected", "topic_id": current.id})
            return {
                "reply": f"{exc}\n{live.agent.question_text(current)}",
                "question": _question(live, current),
                "done": False,
                "awaiting_confirmation": False,
                "progress": _progress(live.session),
                "trace": trace,
            }

        trace.append({"stage": "rule", "tool": "validate_form_answer", "status": "completed", "topic_id": current.id})
        next_topic = live.session.next_topic()
        if next_topic is not None:
            _persist(live)
            return {
                "reply": live.agent.question_text(next_topic),
                "question": _question(live, next_topic),
                "done": False,
                "awaiting_confirmation": False,
                "extracted": {"topic_id": current.id, "action": interpretation.action, "value": jsonable_encoder(interpretation.value), "note": interpretation.note},
                "progress": _progress(live.session),
                "trace": trace,
            }
        state.awaiting_confirm = True
        _persist(live)
        return {
            "reply": live.agent.summary_text(live.session.to_feedback_content()),
            "done": False,
            "awaiting_confirmation": True,
            "extracted": {"topic_id": current.id, "action": interpretation.action, "value": jsonable_encoder(interpretation.value), "note": interpretation.note},
            "progress": _progress(live.session),
            "trace": trace + [{"stage": "guard", "tool": "require_confirmation", "status": "waiting"}],
        }

    @application.post("/api/chat/message")
    def message(
        req: MsgReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """非串流相容端點；LINE／既有 client 仍可一次取得完整結果。"""
        if principal.role is not Role.MEMBER:
            raise HTTPException(403, "只有會員能繼續服務對話")
        return _message_payload(req, account_id=principal.account_id)

    @application.post("/api/chat/message/stream")
    def message_stream(
        req: MsgReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> StreamingResponse:
        """以 NDJSON 回報安全的處理階段、文字增量與最終結構化狀態。"""
        stored = session_store.get(req.session_id)
        if principal.role is not Role.MEMBER:
            raise HTTPException(403, "只有會員能繼續服務對話")
        if stored is None or stored.account_id != principal.account_id:
            raise HTTPException(404, "工作階段不存在，請重新開始")

        def encode(event: dict[str, Any]) -> str:
            return json.dumps(jsonable_encoder(event), ensure_ascii=False) + "\n"

        def events():
            # 第一個 event 在進入同步 LLM 判讀前送出，避免畫面長時間沒有回應。
            yield encode({"type": "status", "label": "正在理解你的回答"})
            payload = _message_payload(req, account_id=principal.account_id)
            yield encode({"type": "status", "label": "正在整理回覆"})
            reply = str(payload.get("reply") or "")
            for offset in range(0, len(reply), 8):
                yield encode({"type": "delta", "text": reply[offset : offset + 8]})
            yield encode({"type": "complete", "data": payload})

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.get("/healthz")
    def healthz() -> dict:
        """負載平衡器的健康檢查端點。

        只回報「這個執行單元活著」，不去戳資料庫或 LLM——健康檢查若依賴外部服務，
        一次下游抖動就會讓 ALB 把好好的實例整批換掉。
        """
        return {"status": "ok"}

    @application.get("/api/v1/services")
    def list_services() -> dict:
        """服務目錄——前端與 MCP 共用的單一來源。"""
        return {"data": life_services.list_services()}

    @application.get("/api/v1/services/search")
    def search_services(q: str, limit: int = 3) -> dict:
        """以規則檢索相關服務；零分項目不進候選，避免整份目錄冒充意圖辨識。"""
        return {"data": life_services.search_services(q, limit=limit)}

    @application.get("/api/v1/services/{service_id}/form")
    def get_service_form(service_id: str) -> dict:
        """該服務的題組定義（已把相對日期換算成絕對日期）。"""
        definition = life_services.get_service_form(service_id)
        if definition is None:
            raise HTTPException(404, "查無服務")
        return {"data": definition}

    @application.post("/api/v1/services/{service_id}/quote")
    def quote_service(service_id: str, req: QuoteReq) -> dict:
        """依填答試算金額與折抵（業務規則在後端，跨通路一致）。"""
        if life_services.get_service_form(service_id) is None:
            raise HTTPException(404, "查無服務")
        return {"data": life_services.quote(service_id, req.answers).to_dict()}

    @application.post("/api/v1/services/{service_id}/orders")
    def create_service_order(
        service_id: str, req: OrderReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        account_id = require_member_principal(principal, req.account_id)
        try:
            return {"data": life_services.create_order(
                service_id=service_id, answers=req.answers, account_id=account_id,
                idempotency_key=idempotency_key,
            )}
        except (FormError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.post("/api/v1/services/{service_id}/submissions")
    def submit_service_form(
        service_id: str,
        req: ServiceSubmissionReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """Persist a manual form; never report a booking/fulfillment that did not happen."""
        account_id = require_member_principal(principal, None)
        try:
            return {"data": life_services.submit_service(
                service_id=service_id, answers=req.answers, account_id=account_id,
                idempotency_key=idempotency_key,
            )}
        except (FormError, InquiryTransitionError, ValueError) as exc:
            raise HTTPException(409 if "Idempotency-Key" in str(exc) else 400, str(exc)) from exc

    @application.get("/api/v1/orders")
    def list_platform_orders(
        account_id: str | None = None,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        owner = require_member_principal(principal, account_id)
        return {"data": life_services.list_orders_for(owner)}

    @application.get("/api/v1/orders/{order_id}")
    def get_platform_order(
        order_id: str, account_id: str | None = None,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        owner = require_member_principal(principal, account_id)
        record = life_services.get_order(order_id)
        if record is None or record["accountId"] != owner:
            raise HTTPException(404, "查無訂單")
        return {"data": record}

    @application.post("/api/v1/intent/match")
    def match_intent(req: IntentReq) -> dict:
        """把口語需求判讀成一項服務；判讀不出時回 null，由介面退回服務目錄。"""
        match = IntentAgent(llm_factory()).match(req.need)
        return {"data": None if match is None else match.to_dict()}

    # --- 規劃器：LLM 規劃、規則執行（ADR-0017） ---

    @application.get("/api/v1/assistant/tools")
    def list_tools(context: ToolContext = Depends(_support_http_context)) -> dict:
        """目前身分可用的能力清單——與 MCP server 對外曝露的是同一份。"""
        return {"data": tool_registry.describe(role=context.role)}

    @application.post("/api/v1/assistant/plan")
    def create_plan(req: PlanReq, context: ToolContext = Depends(_support_http_context)) -> dict:
        """把一句話拆成計畫並執行唯讀步驟；寫入步驟留著等使用者確認。"""
        if safety := safety_response_for(req.message):
            return {"data": Plan(rejected_reason=safety).to_dict()}
        # 多意圖 Hero 先進入持久化 LifeTask；單一服務與其他需求仍走通用 Planner。
        if context.role == "user" and context.account_id:
            persona = get_persona(context.account_id)
            try:
                task = life_tasks.create_draft(
                    message=req.message, account_id=context.account_id,
                    display_name=persona.name if persona is not None else context.display_name,
                )
                return {"data": Plan(
                    understanding="我把目標整理成一份跨服務安排",
                    life_task=task,
                ).to_dict()}
            except LifeTaskNotApplicable:
                pass
        planner = Planner(llm_factory(), tool_registry)
        plan = planner.execute(planner.plan(req.message, context), context)
        return {"data": plan.to_dict()}

    @application.post("/api/v1/assistant/plan/execute")
    def execute_plan(req: ExecutePlanReq, context: ToolContext = Depends(_support_http_context)) -> dict:
        """執行使用者已確認的寫入步驟。

        步驟由前端帶回，但**不信任前端**：每一步都重新過一次註冊表的驗證與角色檢查，
        所以偽造的步驟過不了這一關。
        """
        planner = Planner(llm_factory(), tool_registry)
        plan = Plan(understanding=req.message)
        for raw in req.steps:
            tool = tool_registry.get(raw.get("tool"))
            if tool is None or not tool.allows(context.role):
                raise HTTPException(400, f"無法執行的步驟：{raw.get('tool')}")
            plan.steps.append(
                PlanStep(
                    tool=tool.name,
                    arguments=raw.get("arguments") or {},
                    why=str(raw.get("why") or ""),
                    writes=tool.writes,
                    status="needs_confirmation" if tool.writes else "ready",
                )
            )
        return {"data": planner.execute(plan, context, approved=set(req.approved)).to_dict()}

    @application.get("/api/v1/match/{service_id}")
    def match_vendors(
        service_id: str,
        district: str | None = None,
        county: str | None = None,
        budget: int | None = None,
        slot: str | None = None,
        urgent: bool = False,
    ) -> dict:
        """服務媒合（FR-S-04）：依地區／時段／預算／緊急程度／評分列 2–3 家比較。"""
        try:
            result = tool_registry.call(
                "match_vendors",
                {
                    "service_id": service_id,
                    "district": district,
                    "county": county,
                    "budget": budget,
                    "slot": slot,
                    "urgent": urgent,
                },
                ToolContext(),
            )
        except Exception as error:  # noqa: BLE001
            raise HTTPException(404, str(error)) from error
        return {"data": result}

    # --- 個人洞察：全部由官方 mms_order_record 算出 ---

    @application.get("/api/v1/insights/accounts")
    def list_insight_accounts() -> dict:
        return {"data": insights.accounts()}

    @application.get("/api/v1/insights/{account_id}/summary")
    def insight_summary(
        account_id: str,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """消費與跨服務摘要；`me` 解析為展示 persona。"""
        return {"data": insights.summary(require_member_principal(principal, account_id))}

    @application.get("/api/v1/insights/{account_id}/trail")
    def insight_trail(
        account_id: str,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """行為軌跡：跨服務、跨時間的事件序列。"""
        return {"data": insights.trail(require_member_principal(principal, account_id))}

    @application.get("/api/v1/insights/{account_id}/recommendations")
    def insight_recommendations(
        account_id: str, limit: int = 3,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """可解釋推薦：規則產生，每則附官方訂單證據。"""
        return {"data": insights.recommendations(
            require_member_principal(principal, account_id), limit=limit,
        )}

    @application.get("/api/v1/today/{account_id}")
    def today_briefing(
        account_id: str, limit: int = 5,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """今日摘要：由真實待辦與行為軌跡彙整，規則產生（非 LLM 生成）。"""
        resolved = require_member_principal(principal, account_id)
        items = build_briefing(
            account_id=resolved,
            inquiries=life_services.list_inquiries(),
            campaigns=community.list_open_campaigns(),
            today=resolved_today,
            limit=limit,
        )
        if resolved:
            items = [
                item for item in items
                if item.kind != "suggestion" or not personalization.is_suppressed(resolved, item.source)
            ]
        return {"data": [item.to_dict() for item in items]}

    # --- 個人化補貨：官方行為證據＋競賽 seed 帳本＋可撤回偏好 ---

    @application.get("/api/v1/personalization/{account_id}/restock-plan")
    def restock_plan(
        account_id: str,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        owner = require_member_principal(principal, account_id)
        return {"data": personalization.restock_plan(
            owner,
            openpoint_balance=demo_points.balance(
                demo_workspace_id=principal.demo_workspace_id,
                workspace_id=principal.workspace_id,
                account_id=owner,
            ),
        )}

    @application.post("/api/v1/personalization/{account_id}/feedback")
    def recommendation_feedback(
        account_id: str, req: RecommendationFeedbackReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        owner = require_member_principal(principal, account_id)
        try:
            return {"data": personalization.feedback(owner, req.recommendation_id, req.action)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.get("/api/v1/personalization/{account_id}/reminders")
    def list_personal_reminders(
        account_id: str,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        return {"data": personalization.list_reminders(require_member_principal(principal, account_id))}

    @application.post("/api/v1/personalization/{account_id}/reminders")
    def create_personal_reminder(
        account_id: str, req: ReminderReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        owner = require_member_principal(principal, account_id)
        try:
            return {"data": personalization.create_reminder(
                owner,
                item_name=req.item_name,
                cadence_days=req.cadence_days,
                next_due_on=req.next_due_on,
            )}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    # --- 超商生態：能力／庫存、替代門市與候補 ---

    @application.get("/api/v1/retail/stores/search")
    def retail_search(q: str, district: str | None = None, capability: str | None = None) -> dict:
        try:
            return {"data": retail.search(query=q, district=district, capability=capability)}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.get("/api/v1/retail/stock-watches")
    def list_stock_watches(
        account_id: str | None = None,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        return {"data": retail.list_watches(require_member_principal(principal, account_id))}

    @application.post("/api/v1/retail/stock-watches")
    def join_stock_watch(
        req: StockWatchReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        owner = require_member_principal(principal, req.account_id)
        try:
            return {"data": retail.join_waitlist(
                owner, product_id=req.product_id, store_id=req.store_id,
            )}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    # --- 訂單異常與客服：診斷預覽 → 人確認 → 工單與處理事件 ---

    @application.post("/api/v1/support/diagnose")
    def diagnose_support_issue(
        req: SupportIssueReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": support.diagnose(
                account_id=account_id, subject_id=req.subject_id, issue_text=req.issue_text
            )}
        except SupportError as exc:
            status_code = 404 if "查無" in str(exc) else 400
            raise HTTPException(status_code, str(exc)) from exc

    @application.post("/api/v1/support/tickets")
    def create_support_ticket(
        req: SupportTicketReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": support.create_ticket(
                account_id=account_id, subject_id=req.subject_id, issue_text=req.issue_text,
                diagnosis_token=req.diagnosis_token,
            )}
        except SupportError as exc:
            status_code = 404 if "查無" in str(exc) else 409
            raise HTTPException(status_code, str(exc)) from exc

    @application.get("/api/v1/support/tickets")
    def list_support_tickets(context: ToolContext = Depends(_support_http_context)) -> dict:
        return {"data": support.list_for_account(_require_support_role(context, "user"))}

    @application.get("/api/v1/support/queue")
    def list_support_queue(context: ToolContext = Depends(_support_http_context)) -> dict:
        _require_support_role(context, "manager")
        return {"data": support.list_queue()}

    @application.post("/api/v1/support/tickets/{ticket_id}/start")
    def start_support_ticket(
        ticket_id: str,
        req: SupportActionReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": support.start_ticket(ticket_id, actor=context.display_name)}
        except SupportError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/support/tickets/{ticket_id}/resolve")
    def resolve_support_ticket(
        ticket_id: str,
        req: SupportActionReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": support.resolve_ticket(ticket_id, actor=context.display_name, note=req.note or "")}
        except SupportError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.get("/api/v1/inquiries")
    def list_inquiries(context: ToolContext = Depends(_support_http_context)) -> dict:
        if context.role != "user":
            raise HTTPException(403, "只有會員能查看自己的委託")
        # 新帳號沒有 account id，也就沒有任何既有紀錄。
        return {"data": [] if not context.account_id else life_services.list_inquiries_for(context.account_id)}

    @application.get("/api/v1/inquiries/{inquiry_id}")
    def get_inquiry(inquiry_id: str, context: ToolContext = Depends(_support_http_context)) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            record = life_services.require_resident_inquiry(inquiry_id, account_id)
        except InquiryTransitionError:
            raise HTTPException(404, "查無諮詢單")
        return {"data": record}

    # --- 社區團購：住戶與管委會看同一批資料，可做的動作不同 ---

    @application.get("/api/v1/community/campaigns")
    def list_campaigns(
        only_open: bool = False,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        if principal.role is Role.MEMBER:
            require_member_principal(principal)
        else:
            require_manager_principal(principal)
        return {"data": community.list_open_campaigns() if only_open else community.list_all_campaigns()}

    @application.post("/api/v1/community/campaigns")
    def create_campaign(
        req: CreateCampaignReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """【管委會】開團。"""
        require_manager_principal(principal)
        return {"data": community.create_campaign(**req.model_dump())}

    @application.post("/api/v1/community/campaigns/{campaign_id}/join")
    def join_campaign(
        campaign_id: int, req: JoinCampaignReq,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """【住戶】跟團。"""
        owner = require_member_principal(principal, req.account_id)
        try:
            return {"data": community.join_campaign(
                campaign_id, account_id=owner, display_name=principal.display_name, quantity=req.quantity,
            )}
        except GroupBuyError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/community/campaigns/{campaign_id}/close")
    def close_campaign(
        campaign_id: int,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        """【管委會】結單，並產出給廠商的採購彙總。"""
        require_manager_principal(principal)
        try:
            campaign = community.close_campaign(campaign_id)
        except GroupBuyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"data": {"campaign": campaign, "purchaseOrder": community.purchase_order(campaign_id)}}

    @application.get("/api/v1/community/my-participation")
    def my_participation(
        account_id: str | None = None,
        principal: Principal = Depends(current_platform_principal),
    ) -> dict:
        return {"data": community.my_participation(require_member_principal(principal, account_id))}

    # --- 使用者自行命名的 Group；Community 是獨立模型 ---

    @application.get("/api/v1/groups")
    def list_member_groups(context: ToolContext = Depends(_support_http_context)) -> dict:
        account_id = _require_support_role(context, "user")
        return {"data": group_repository.list_for_member(account_id)}

    @application.post("/api/v1/groups")
    def create_member_group(
        req: CreateGroupReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": group_repository.create(
                name=req.name, account_id=account_id,
                display_name=req.display_name or context.display_name,
                idempotency_key=idempotency_key,
            )}
        except GroupError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.post("/api/v1/groups/join")
    def join_member_group(
        req: JoinGroupReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": group_repository.join(
                invite_code=req.invite_code, account_id=account_id,
                display_name=req.display_name or context.display_name,
                idempotency_key=idempotency_key,
            )}
        except GroupError as exc:
            raise HTTPException(404 if "邀請碼" in str(exc) else 400, str(exc)) from exc

    @application.patch("/api/v1/groups/{group_id}")
    def rename_member_group(
        group_id: str, req: RenameGroupReq,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": group_repository.rename(
                group_id, account_id=account_id, name=req.name,
                idempotency_key=idempotency_key,
            )}
        except GroupPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except GroupError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.delete("/api/v1/groups/{group_id}/members/me")
    def leave_member_group(
        group_id: str,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": group_repository.leave(
                group_id, account_id=account_id, idempotency_key=idempotency_key,
            )}
        except GroupPermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except GroupError as exc:
            raise HTTPException(409, str(exc)) from exc

    # --- 社區聯合服務：匿名需求 → 方案決策 → 廠商履約 ---

    @application.get("/api/v1/community/joint-services")
    def list_joint_services(context: ToolContext = Depends(_support_http_context)) -> dict:
        _require_support_role(context, "manager")
        return {"data": joint_service_repository.list_campaigns()}

    @application.get("/api/v1/groups/joint-services")
    def list_resident_joint_services(context: ToolContext = Depends(_support_http_context)) -> dict:
        account_id = _require_support_role(context, "user")
        return {"data": joint_service_repository.list_for_resident(account_id=account_id)}

    @application.post("/api/v1/community/joint-services")
    def create_joint_service(req: JointServiceDraftReq, context: ToolContext = Depends(_support_http_context)) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": joint_service_repository.create_draft(
                title=req.title, service_id=req.service_id, created_by=context.display_name,
            )}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/community/joint-services/{campaign_id}/publish")
    def publish_joint_service(campaign_id: int, context: ToolContext = Depends(_support_http_context)) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": joint_service_repository.publish(campaign_id, actor=context.display_name)}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/community/joint-services/{campaign_id}/join")
    def join_joint_service(
        campaign_id: int, req: JointServiceJoinReq, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        account_id = _require_support_role(context, "user")
        try:
            return {"data": joint_service_repository.join(
                campaign_id, account_id=account_id, units=req.units, equipment=req.equipment,
                preferred_slot=req.preferred_slot, special_requirement=req.special_requirement,
            )}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/community/joint-services/{campaign_id}/prepare-proposals")
    def prepare_joint_service_proposals(
        campaign_id: int, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": joint_service_repository.prepare_proposals(campaign_id, actor=context.display_name)}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/community/joint-services/{campaign_id}/assign")
    def assign_joint_service(
        campaign_id: int, req: JointServiceAssignReq, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        _require_support_role(context, "manager")
        try:
            return {"data": joint_service_repository.assign(
                campaign_id, proposal_id=req.proposal_id, actor=context.display_name,
            )}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.get("/api/v1/vendor/joint-services")
    def vendor_joint_services(context: ToolContext = Depends(_support_http_context)) -> dict:
        vendor_id = _require_support_role(context, "partner")
        if not vendor_id:
            raise HTTPException(401, "合作廠商工作台需要廠商帳號")
        return {"data": joint_service_repository.list_assigned(vendor_id=vendor_id)}

    @application.post("/api/v1/vendor/joint-services/{campaign_id}/start")
    def start_joint_service(campaign_id: int, context: ToolContext = Depends(_support_http_context)) -> dict:
        vendor_id = _require_support_role(context, "partner")
        if not vendor_id:
            raise HTTPException(401, "合作廠商工作台需要廠商帳號")
        try:
            return {"data": joint_service_repository.start(
                campaign_id, vendor_id=vendor_id, actor=context.display_name,
            )}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/vendor/joint-services/{campaign_id}/complete")
    def complete_joint_service(
        campaign_id: int, req: JointServiceCompleteReq, context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        vendor_id = _require_support_role(context, "partner")
        if not vendor_id:
            raise HTTPException(401, "合作廠商工作台需要廠商帳號")
        try:
            return {"data": joint_service_repository.complete(
                campaign_id, vendor_id=vendor_id, actor=context.display_name, note=req.note,
            )}
        except JointServiceError as exc:
            raise HTTPException(409, str(exc)) from exc

    # --- 諮詢單生命週期：住戶送出 → 廠商報價 → 住戶確認 → 廠商完工 ---

    @application.get("/api/v1/vendor/workload")
    def vendor_workload(context: ToolContext = Depends(_support_http_context)) -> dict:
        """廠商工作台：真的來自住戶送出的諮詢單，而非固定展示資料。"""
        vendor_id = _require_support_role(context, "partner")
        return {"data": life_services.list_vendor_workload(vendor_id)}

    @application.post("/api/v1/inquiries/{inquiry_id}/quote")
    def create_quote(
        inquiry_id: str, req: CreateQuoteReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        """【廠商】開立報價 → 住戶會在訂單頁看到並可確認。"""
        vendor_id = _require_support_role(context, "partner")
        try:
            life_services.require_vendor_inquiry(inquiry_id, vendor_id)
            record = life_services.quote_inquiry(
                inquiry_id,
                items=[item.model_dump() for item in req.items],
                vendor_name=life_services.vendor_name(vendor_id),
            )
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"data": record}

    @application.post("/api/v1/inquiries/{inquiry_id}/confirm")
    def confirm_quote(inquiry_id: str, context: ToolContext = Depends(_support_http_context)) -> dict:
        """【住戶】同意報價。"""
        account_id = _require_support_role(context, "user")
        try:
            life_services.require_resident_inquiry(inquiry_id, account_id)
            return {"data": life_services.confirm_inquiry_quote(inquiry_id)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/inquiries/{inquiry_id}/revise")
    def request_revision(
        inquiry_id: str, req: ReviseReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        """【住戶】請廠商重新報價（議價，或想換一家出價）。"""
        account_id = _require_support_role(context, "user")
        try:
            life_services.require_resident_inquiry(inquiry_id, account_id)
            return {"data": life_services.request_quote_revision(inquiry_id, note=req.note)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/inquiries/{inquiry_id}/cancel")
    def cancel_inquiry(
        inquiry_id: str, req: CancelReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        """【住戶】取消委託。已確認之後不開放——廠商已排程，那需要協調。"""
        account_id = _require_support_role(context, "user")
        try:
            life_services.require_resident_inquiry(inquiry_id, account_id)
            return {"data": life_services.cancel_inquiry(inquiry_id, reason=req.reason)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.post("/api/v1/inquiries/{inquiry_id}/complete")
    def complete_inquiry(
        inquiry_id: str, req: CompleteReq,
        context: ToolContext = Depends(_support_http_context),
    ) -> dict:
        """【廠商】回報完工。"""
        vendor_id = _require_support_role(context, "partner")
        try:
            life_services.require_vendor_inquiry(inquiry_id, vendor_id)
            return {"data": life_services.complete_inquiry(inquiry_id, note=req.note)}
        except InquiryTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @application.get("/", response_class=HTMLResponse)
    def index() -> str:
        """API 根路徑。使用者介面在 Vue 應用（`web/app`），不由此服務。"""
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<title>AI 生活服務平台 API</title>"
            "<h1>AI 生活服務平台 API</h1>"
            "<p>這是後端 API。使用者介面請執行 <code>web/app</code>（<code>npm run dev</code>）。</p>"
            "<p><a href='/docs'>API 文件</a></p>"
        )

    return application


app = create_app()
