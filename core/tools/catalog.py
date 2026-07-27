"""把既有能力包成工具——規劃器與 MCP 共用的那一份（[ADR-0017]）。

這裡**不寫任何新的商業規則**。每個 handler 都只是把 `core/` 既有的服務層包起來，
理由是規則只能有一份：規劃器走這裡、MCP 走這裡、HTTP 也走同一個服務層。
一旦這裡開始出現 if-else 業務判斷，就代表規則漏到能力層了。

工具描述（`description`）是寫給模型看的提示詞的一部分，不是給人看的註解——
它決定 LLM 會不會在對的時機挑對的工具，所以寫得具體、講清楚「什麼時候用」。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from core.community.group_buy import GroupBuyRepository
from core.data.regions import resolve as resolve_region
from core.forms.service_catalog import list_services as list_catalog_services
from core.insights.behavior import build_trail, summarize
from core.insights.recommendations import recommend
from core.matching import match as match_vendors_by_rules
from core.services.life_services import LifeServicesService
from core.tools.registry import Tool, ToolContext, ToolError, ToolRegistry

RESIDENT = frozenset({"user"})
MANAGER = frozenset({"manager"})
PARTNER = frozenset({"partner"})


def _require_account(context: ToolContext) -> str:
    if not context.account_id:
        raise ToolError("這項能力需要先登入")
    return context.account_id


def _empty_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}}


def _service_id_schema(description: str) -> dict[str, Any]:
    """service_id 一律帶 enum。

    提示詞裡寫「只能用這些代碼」擋不住模型——實測它仍會填出 `cleaning` 這種簡寫。
    把合法值放進 schema，幻覺的代碼在參數驗證就被擋掉（整份計畫作廢），
    而不是等到執行時才失敗；外部 Agent 透過 MCP 也會看到同一份限制。
    """
    return {
        "type": "string",
        "enum": [service.id for service in list_catalog_services()],
        "description": description,
    }


def build_registry(
    *,
    services: LifeServicesService,
    group_buys: GroupBuyRepository,
    today: date,
) -> ToolRegistry:
    """組出這個部署可用的全部能力。"""
    registry = ToolRegistry()

    # ---- 服務目錄與題組（唯讀，任何身分都能查） ----------------------

    def list_services(context: ToolContext) -> Any:
        return services.list_services()

    def get_service_form(context: ToolContext, *, service_id: str) -> Any:
        form = services.get_service_form(service_id)
        if form is None:
            raise ToolError(f"沒有這項服務：{service_id}")
        return form

    def estimate_price(context: ToolContext, *, service_id: str) -> Any:
        quote = services.quote(service_id, None)
        return quote.to_dict() if hasattr(quote, "to_dict") else quote

    registry.register(
        Tool(
            name="list_services",
            description="列出平台上所有可申請的生活服務（家電清洗、居家清潔、水電修繕、團購等）。"
            "當使用者問「你們有什麼服務」或需要確認某個需求對應到哪項服務時使用。",
            parameters=_empty_schema(),
            handler=list_services,
        )
    )
    registry.register(
        Tool(
            name="get_service_form",
            description="取得某項服務的諮詢單題組（要問住戶哪些問題）。"
            "確定使用者要申請哪項服務之後，用這個取得後續要引導填答的題目。",
            parameters={
                "type": "object",
                "properties": {"service_id": _service_id_schema("服務代碼")},
                "required": ["service_id"],
            },
            handler=get_service_form,
        )
    )
    registry.register(
        Tool(
            name="estimate_price",
            description="取得某項服務的參考價格與可用折扣（券、點數、支付加碼）。"
            "使用者問「大概多少錢」時使用；這是估價不是正式報價，正式報價由廠商提出。",
            parameters={
                "type": "object",
                "properties": {"service_id": _service_id_schema("服務代碼")},
                "required": ["service_id"],
            },
            handler=estimate_price,
        )
    )

    # ---- 服務媒合（FR-S-04） -----------------------------------------

    def match_vendors(
        context: ToolContext,
        *,
        service_id: str,
        district: str | None = None,
        county: str | None = None,
        budget: int | None = None,
        slot: str | None = None,
        urgent: bool | None = None,
    ) -> Any:
        if services.get_service_form(service_id) is None:
            raise ToolError(f"沒有這項服務：{service_id}")
        region = resolve_region(district, county) if district else None
        if district and region is None:
            raise ToolError(f"無法辨識的地區：{county or ''}{district}")
        matches = match_vendors_by_rules(
            service_id,
            county_code=region["county_code"] if region else None,
            district_code=region["district_code"] if region else None,
            budget=budget,
            slot=slot,
            urgent=bool(urgent),
        )
        return {
            "serviceId": service_id,
            "region": region,
            "criteria": {"budget": budget, "slot": slot, "urgent": bool(urgent)},
            "vendors": [item.to_dict() for item in matches],
        }

    registry.register(
        Tool(
            name="match_vendors",
            description="依服務類型、地區、時段、預算、緊急程度與評分，媒合 2–3 家合適廠商並附上推薦理由。"
            "使用者想知道「找誰做」「哪家比較好」「有沒有便宜一點的」時使用。"
            "地區用口語地名即可，例如 district=大同區、county=台北市。",
            parameters={
                "type": "object",
                "properties": {
                    "service_id": _service_id_schema("服務代碼"),
                    "district": {"type": "string", "description": "行政區口語名稱，例如 大同區"},
                    "county": {"type": "string", "description": "縣市口語名稱，例如 台北市"},
                    "budget": {"type": "integer", "description": "預算上限（新台幣元）"},
                    "slot": {
                        "type": "string",
                        "enum": ["weekday_morning", "weekday_afternoon", "weekend", "evening"],
                        "description": "希望的服務時段",
                    },
                    "urgent": {"type": "boolean", "description": "是否需要加急（當日／隔日到場）"},
                },
                "required": ["service_id"],
            },
            handler=match_vendors,
        )
    )

    # ---- 住戶自己的委託 ----------------------------------------------

    def list_my_inquiries(context: ToolContext) -> Any:
        return services.list_inquiries_for(_require_account(context))

    def get_inquiry(context: ToolContext, *, inquiry_id: str) -> Any:
        record = services.get_inquiry(inquiry_id)
        if record is None:
            raise ToolError(f"查無諮詢單 {inquiry_id}")
        account_id = _require_account(context)
        if record.get("account_id") not in (None, account_id):
            raise ToolError(f"查無諮詢單 {inquiry_id}")
        return record

    def confirm_quote(context: ToolContext, *, inquiry_id: str) -> Any:
        get_inquiry(context, inquiry_id=inquiry_id)   # 先確認是自己的單
        return services.confirm_inquiry_quote(inquiry_id)

    def request_quote_revision(context: ToolContext, *, inquiry_id: str, note: str) -> Any:
        get_inquiry(context, inquiry_id=inquiry_id)
        return services.request_quote_revision(inquiry_id, note=note)

    def cancel_inquiry(context: ToolContext, *, inquiry_id: str, reason: str | None = None) -> Any:
        get_inquiry(context, inquiry_id=inquiry_id)
        return services.cancel_inquiry(inquiry_id, reason=reason)

    registry.register(
        Tool(
            name="list_my_inquiries",
            description="列出目前登入住戶自己的所有委託單及其進度（待報價／已報價待確認／已確認／已完工）。"
            "使用者問「我的案件到哪了」「有什麼待處理」時使用。",
            parameters=_empty_schema(),
            handler=list_my_inquiries,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="get_inquiry",
            description="查看單一委託單的完整內容，包含填答摘要、廠商報價與歷程事件。",
            parameters={
                "type": "object",
                "properties": {"inquiry_id": {"type": "string", "description": "例如 INQ-20260727-001"}},
                "required": ["inquiry_id"],
            },
            handler=get_inquiry,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="confirm_quote",
            description="住戶同意廠商的報價，讓案件進入排程施作。這會改變案件狀態，執行前必須先向使用者確認。",
            parameters={
                "type": "object",
                "properties": {"inquiry_id": {"type": "string"}},
                "required": ["inquiry_id"],
            },
            handler=confirm_quote,
            writes=True,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="request_quote_revision",
            description="住戶覺得報價太貴、想議價，或想換別家廠商出價時使用。"
            "案件會退回待報價並附上住戶的說明，廠商可以重新出價。這會改變案件狀態，執行前必須確認。",
            parameters={
                "type": "object",
                "properties": {
                    "inquiry_id": {"type": "string"},
                    "note": {"type": "string", "description": "希望調整什麼，例如「預算希望壓在 1000 以內」"},
                },
                "required": ["inquiry_id", "note"],
            },
            handler=request_quote_revision,
            writes=True,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="cancel_inquiry",
            description="住戶不需要這項服務了，取消整張委託。只有在施工開始前可以取消。"
            "這是不可逆的動作，執行前必須明確確認。",
            parameters={
                "type": "object",
                "properties": {
                    "inquiry_id": {"type": "string"},
                    "reason": {"type": "string", "description": "取消原因（選填）"},
                },
                "required": ["inquiry_id"],
            },
            handler=cancel_inquiry,
            writes=True,
            roles=RESIDENT,
        )
    )

    # ---- 社區團購 ------------------------------------------------------

    def list_group_buys(context: ToolContext, *, status: str | None = None) -> Any:
        return group_buys.list_campaigns(status=status)

    def join_group_buy(context: ToolContext, *, campaign_id: int, quantity: int) -> Any:
        return group_buys.join(
            campaign_id,
            account_id=_require_account(context),
            display_name=context.display_name,
            quantity=quantity,
        )

    def open_group_buy(
        context: ToolContext,
        *,
        title: str,
        item_name: str,
        unit_price: int,
        unit: str | None = None,
        min_quantity: int | None = None,
        close_time: str | None = None,
        pickup: str | None = None,
    ) -> Any:
        optional = {"unit": unit, "min_quantity": min_quantity, "close_time": close_time, "pickup": pickup}
        return group_buys.create_campaign(
            title=title,
            item_name=item_name,
            unit_price=unit_price,
            created_by=context.account_id,
            **{key: value for key, value in optional.items() if value is not None},
        )

    def close_group_buy(context: ToolContext, *, campaign_id: int) -> Any:
        return group_buys.close_campaign(campaign_id)

    registry.register(
        Tool(
            name="list_group_buys",
            description="列出社區團購活動與目前跟團情形（幾戶、幾份、是否達標）。"
            "使用者問「社區這期有什麼團購」時使用。",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["open", "closed", "fulfilled"], "description": "不填則全部"}
                },
            },
            handler=list_group_buys,
        )
    )
    registry.register(
        Tool(
            name="join_group_buy",
            description="以目前住戶身分跟團，指定要買幾份。重複跟同一團會更新份數而不是新增一筆。"
            "這會寫入資料，執行前必須先向使用者確認份數。",
            parameters={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "integer"},
                    "quantity": {"type": "integer", "description": "要買幾份，至少 1"},
                },
                "required": ["campaign_id", "quantity"],
            },
            handler=join_group_buy,
            writes=True,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="open_group_buy",
            description="管委會開一檔新的社區團購。這會建立活動並對全社區公開，執行前必須先確認內容。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "item_name": {"type": "string"},
                    "unit_price": {"type": "integer", "description": "每份單價（新台幣元）"},
                    "unit": {"type": "string", "description": "計量單位，預設「份」"},
                    "min_quantity": {"type": "integer", "description": "成團門檻份數"},
                    "close_time": {"type": "string", "description": "截止時間 ISO 字串"},
                    "pickup": {"type": "string", "description": "取貨方式說明"},
                },
                "required": ["title", "item_name", "unit_price"],
            },
            handler=open_group_buy,
            writes=True,
            roles=MANAGER,
        )
    )
    registry.register(
        Tool(
            name="close_group_buy",
            description="管委會結單：停止收單並產出給廠商的採購彙總。不可逆，執行前必須確認。",
            parameters={
                "type": "object",
                "properties": {"campaign_id": {"type": "integer"}},
                "required": ["campaign_id"],
            },
            handler=close_group_buy,
            writes=True,
            roles=MANAGER,
        )
    )

    # ---- 個人洞察（皆由官方訂單算出） --------------------------------

    def get_behavior_summary(context: ToolContext) -> Any:
        return summarize(_require_account(context), today=today).to_dict()

    def get_activity_trail(context: ToolContext, *, limit: int | None = None) -> Any:
        trail = [event.to_dict() for event in build_trail(_require_account(context))]
        trail.reverse()   # 新到舊，對話裡先講最近的事
        return trail[: limit or 10]

    def get_recommendations(context: ToolContext, *, limit: int | None = None) -> Any:
        recs = recommend(_require_account(context), today=today, limit=limit or 3)
        return [rec.to_dict() for rec in recs]

    registry.register(
        Tool(
            name="get_behavior_summary",
            description="取得目前住戶的跨服務使用摘要（用過幾次、花了多少、多久沒用某項服務）。"
            "需要根據使用者過去行為給建議時使用。",
            parameters=_empty_schema(),
            handler=get_behavior_summary,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="get_activity_trail",
            description="取得住戶的行為軌跡：依時間排序的跨服務事件（最近的在前）。"
            "使用者問「我上次什麼時候用過」或需要回顧歷史時使用。",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "取幾筆，預設 10"}},
            },
            handler=get_activity_trail,
            roles=RESIDENT,
        )
    )
    registry.register(
        Tool(
            name="get_recommendations",
            description="取得針對目前住戶的可解釋推薦，每則都附有來自真實訂單的證據。"
            "要主動提醒使用者「該做什麼」時使用。",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "取幾則，預設 3"}},
            },
            handler=get_recommendations,
            roles=RESIDENT,
        )
    )

    # ---- 廠商工作台 ----------------------------------------------------

    def list_vendor_workload(context: ToolContext) -> Any:
        return services.list_vendor_workload()

    def submit_quote(context: ToolContext, *, inquiry_id: str, items: list, vendor_name: str) -> Any:
        return services.quote_inquiry(inquiry_id, items=items, vendor_name=vendor_name)

    def complete_inquiry(context: ToolContext, *, inquiry_id: str, note: str | None = None) -> Any:
        return services.complete_inquiry(inquiry_id, note=note)

    registry.register(
        Tool(
            name="list_vendor_workload",
            description="廠商工作台：待報價、已報價待住戶確認、已確認待施作的案件清單。",
            parameters=_empty_schema(),
            handler=list_vendor_workload,
            roles=PARTNER,
        )
    )
    registry.register(
        Tool(
            name="submit_quote",
            description="廠商對一張委託單提出報價。這會通知住戶，執行前必須確認金額與項目。",
            parameters={
                "type": "object",
                "properties": {
                    "inquiry_id": {"type": "string"},
                    "items": {"type": "array", "description": "報價項目，每項含 name 與 amount"},
                    "vendor_name": {"type": "string"},
                },
                "required": ["inquiry_id", "items", "vendor_name"],
            },
            handler=submit_quote,
            writes=True,
            roles=PARTNER,
        )
    )
    registry.register(
        Tool(
            name="complete_inquiry",
            description="廠商回報完工。這會結案，執行前必須確認。",
            parameters={
                "type": "object",
                "properties": {"inquiry_id": {"type": "string"}, "note": {"type": "string"}},
                "required": ["inquiry_id"],
            },
            handler=complete_inquiry,
            writes=True,
            roles=PARTNER,
        )
    )

    return registry
