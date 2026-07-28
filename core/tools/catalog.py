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
from core.community.joint_service import JointServiceRepository
from core.data.regions import resolve as resolve_region
from core.forms.service_catalog import list_services as list_catalog_services
from core.insights.behavior import build_trail, summarize
from core.insights.recommendations import recommend
from core.matching import match as match_vendors_by_rules
from core.personalization import PersonalizationService
from core.retail import RetailService
from core.support import SupportService
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
    joint_services: JointServiceRepository | None = None,
    personalization: PersonalizationService | None = None,
    retail: RetailService | None = None,
    support: SupportService | None = None,
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

    def search_services(context: ToolContext, *, query: str, limit: int | None = None) -> Any:
        return services.search_services(query, limit=limit or 3)

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
            name="search_services",
            description="依使用者的自然語言需求搜尋最相關的生活服務，只回傳有匹配證據的前幾項。"
            "例如『想找人打掃』應回清潔與計時家事，不應列出寄件或外送。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "使用者原始需求"},
                    "limit": {"type": "integer", "description": "候選數，預設 3、最多 5"},
                },
                "required": ["query"],
            },
            handler=search_services,
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

    def submit_inquiry(
        context: ToolContext, *, service_id: str, answers: dict
    ) -> Any:
        return services.submit_structured_inquiry(
            service_id=service_id,
            answers=answers,
            account_id=_require_account(context),
        )

    def list_my_inquiries(context: ToolContext) -> Any:
        return services.list_inquiries_for(_require_account(context))

    registry.register(
        Tool(
            name="submit_inquiry",
            description="依 get_service_form 回傳的欄位代碼建立正式諮詢單。答案會再次通過題組引擎驗證，"
            "建立後回傳可追蹤編號；這會寫入資料，必須先讓住戶預覽並確認。",
            parameters={
                "type": "object",
                "properties": {
                    "service_id": _service_id_schema("服務代碼"),
                    "answers": {"type": "object", "description": "以題組 field id 為 key 的答案"},
                },
                "required": ["service_id", "answers"],
            },
            handler=submit_inquiry,
            writes=True,
            roles=RESIDENT,
        )
    )
    if services.orders is not None:
        registry.register(
            Tool(
                name="create_order",
                description="依服務題組答案建立可追蹤訂單，金額只採後端確定性規則計算。"
                "這會真的建立訂單，執行前必須讓住戶預覽品項、折抵與應付金額。",
                parameters={
                    "type": "object",
                    "properties": {
                        "service_id": _service_id_schema("可直接下單的服務代碼"),
                        "answers": {"type": "object", "description": "以題組 field id 為 key 的答案"},
                    },
                    "required": ["service_id", "answers"],
                },
                handler=lambda context, service_id, answers: services.create_order(
                    service_id=service_id, answers=answers, account_id=_require_account(context)
                ),
                writes=True,
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="list_my_orders",
                description="列出目前住戶透過平台建立的訂單、確定性計價明細與履約事件。",
                parameters=_empty_schema(),
                handler=lambda context: services.list_orders_for(_require_account(context)),
                roles=RESIDENT,
            )
        )

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

    # ---- 個人化補貨、回饋與提醒 --------------------------------------

    if personalization is not None:
        registry.register(
            Tool(
                name="get_restock_plan",
                description="依官方歷史訂單與競賽用點數優惠帳本，整理月初補貨建議、可驗證依據與最省付款組合。",
                parameters=_empty_schema(),
                handler=lambda context: personalization.restock_plan(_require_account(context)),
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="record_recommendation_feedback",
                description="只調整指定推薦的軟性偏好，可選不感興趣或復原；不會關閉其他推薦。這會寫入偏好狀態。",
                parameters={
                    "type": "object",
                    "properties": {
                        "recommendation_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["dismiss", "undo"]},
                    },
                    "required": ["recommendation_id", "action"],
                },
                handler=lambda context, recommendation_id, action: personalization.feedback(
                    _require_account(context), recommendation_id, action
                ),
                writes=True,
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="create_restock_reminder",
                description="為單一補貨品項建立週期提醒，保存下次到期日；建立前須讓住戶確認品項與週期。",
                parameters={
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "cadence_days": {"type": "integer"},
                        "next_due_on": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                    "required": ["item_name", "cadence_days", "next_due_on"],
                },
                handler=lambda context, item_name, cadence_days, next_due_on: personalization.create_reminder(
                    _require_account(context),
                    item_name=item_name,
                    cadence_days=cadence_days,
                    next_due_on=next_due_on,
                ),
                writes=True,
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="list_reminders",
                description="列出目前住戶已設定的有效補貨提醒與下次到期日。",
                parameters=_empty_schema(),
                handler=lambda context: personalization.list_reminders(_require_account(context)),
                roles=RESIDENT,
            )
        )

    # ---- 超商能力、庫存、替代門市與候補 ------------------------------

    if retail is not None:
        registry.register(
            Tool(
                name="search_store_inventory",
                description="依商品、行政區與門市能力查詢庫存；指定區域缺貨時同時排序附近可替代門市，並標示資料來源時間。",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "商品名稱或聯名關鍵字"},
                        "district": {"type": "string", "description": "行政區，例如大同區"},
                        "capability": {"type": "string", "description": "需要的能力，例如列印、寄件、ATM"},
                    },
                    "required": ["query"],
                },
                handler=lambda context, query, district=None, capability=None: retail.search(
                    query=query, district=district, capability=capability
                ),
            )
        )
        registry.register(
            Tool(
                name="join_stock_waitlist",
                description="指定門市缺貨時加入到貨候補，後續可由通知通路主動告知。這會寫入資料，必須先確認。",
                parameters={
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "enum": ["limited-cup", "tissue-pack"]},
                        "store_id": {"type": "string", "enum": ["qingchuan", "zhongxing", "minsheng"]},
                    },
                    "required": ["product_id", "store_id"],
                },
                handler=lambda context, product_id, store_id: retail.join_waitlist(
                    _require_account(context), product_id=product_id, store_id=store_id
                ),
                writes=True,
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="list_stock_watches",
                description="列出目前住戶追蹤中的缺貨商品、指定門市與候補狀態。",
                parameters=_empty_schema(),
                handler=lambda context: retail.list_watches(_require_account(context)),
                roles=RESIDENT,
            )
        )

    # ---- 訂單異常診斷與客服閉環 --------------------------------------

    if support is not None:
        registry.register(
            Tool(
                name="diagnose_order_issue",
                description="依目前住戶自己的委託／訂單狀態與問題描述，判斷延遲、付款、品質或改期問題，"
                "回傳證據、優先級、處理路由與 SLA 預覽；不會直接建立工單。",
                parameters={
                    "type": "object",
                    "properties": {
                        "subject_id": {"type": "string", "description": "INQ- 或 ORD- 開頭的追蹤編號"},
                        "issue_text": {"type": "string", "description": "使用者描述發生什麼事"},
                    },
                    "required": ["subject_id", "issue_text"],
                },
                handler=lambda context, subject_id, issue_text: support.diagnose(
                    account_id=_require_account(context), subject_id=subject_id, issue_text=issue_text
                ),
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="create_support_ticket",
                description="針對住戶自己的委託／訂單建立可追蹤客服工單。會重新驗證所有權與分類，"
                "並避免同一訂單重複開啟工單；寫入前必須展示診斷預覽並取得確認。",
                parameters={
                    "type": "object",
                    "properties": {
                        "subject_id": {"type": "string"},
                        "issue_text": {"type": "string"},
                        "diagnosis_token": {"type": "string", "description": "由 diagnose_order_issue 取得的短效預覽 token"},
                    },
                    "required": ["subject_id", "issue_text", "diagnosis_token"],
                },
                handler=lambda context, subject_id, issue_text, diagnosis_token: support.create_ticket(
                    account_id=_require_account(context), subject_id=subject_id, issue_text=issue_text,
                    diagnosis_token=diagnosis_token,
                ),
                writes=True,
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="list_my_support_tickets",
                description="列出目前住戶自己的客服工單、SLA、處理狀態與完整事件。",
                parameters=_empty_schema(),
                handler=lambda context: support.list_for_account(_require_account(context)),
                roles=RESIDENT,
            )
        )
        registry.register(
            Tool(
                name="list_support_queue",
                description="社區客服查看尚未完成的異常工單，依優先級與建立時間排序。",
                parameters=_empty_schema(),
                handler=lambda context: support.list_queue(),
                roles=MANAGER,
            )
        )
        registry.register(
            Tool(
                name="start_support_ticket",
                description="社區客服接手一張待處理工單並留下事件；執行前必須確認。",
                parameters={
                    "type": "object",
                    "properties": {"ticket_id": {"type": "string"}},
                    "required": ["ticket_id"],
                },
                handler=lambda context, ticket_id: support.start_ticket(ticket_id, actor=context.display_name),
                writes=True,
                roles=MANAGER,
            )
        )
        registry.register(
            Tool(
                name="resolve_support_ticket",
                description="社區客服填寫處理結果並完成工單；處理結果不可空白，執行前必須確認。",
                parameters={
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "note": {"type": "string", "description": "已採取的處理方式"},
                    },
                    "required": ["ticket_id", "note"],
                },
                handler=lambda context, ticket_id, note: support.resolve_ticket(
                    ticket_id, actor=context.display_name, note=note
                ),
                writes=True,
                roles=MANAGER,
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

    # ---- 社區聯合服務 --------------------------------------------------

    if joint_services is not None:
        def get_joint_service_summary(context: ToolContext, *, campaign_id: int) -> Any:
            campaign = joint_services.get_campaign(campaign_id)
            if campaign is None:
                raise ToolError(f"查無聯合服務 {campaign_id}")
            return campaign

        def create_joint_service(context: ToolContext, *, title: str, service_id: str) -> Any:
            return joint_services.create_draft(title=title, service_id=service_id, created_by=context.display_name)

        def publish_joint_service(context: ToolContext, *, campaign_id: int) -> Any:
            return joint_services.publish(campaign_id, actor=context.display_name)

        def join_joint_service(
            context: ToolContext, *, campaign_id: int, units: int, equipment: str,
            preferred_slot: str, special_requirement: str | None = None,
        ) -> Any:
            return joint_services.join(
                campaign_id, account_id=_require_account(context), units=units, equipment=equipment,
                preferred_slot=preferred_slot, special_requirement=special_requirement,
            )

        def prepare_joint_service_proposals(context: ToolContext, *, campaign_id: int) -> Any:
            return joint_services.prepare_proposals(campaign_id, actor=context.display_name)

        def assign_joint_service_vendor(context: ToolContext, *, campaign_id: int, proposal_id: str) -> Any:
            return joint_services.assign(campaign_id, proposal_id=proposal_id, actor=context.display_name)

        def list_assigned_joint_services(context: ToolContext) -> Any:
            return joint_services.list_assigned(vendor_id=_require_account(context))

        def start_joint_service(context: ToolContext, *, campaign_id: int) -> Any:
            return joint_services.start(campaign_id, vendor_id=_require_account(context), actor=context.display_name)

        def complete_joint_service(context: ToolContext, *, campaign_id: int, note: str) -> Any:
            return joint_services.complete(
                campaign_id, vendor_id=_require_account(context), actor=context.display_name, note=note,
            )

        registry.register(Tool(
            name="get_joint_service_summary",
            description="管委會查看社區聯合服務的匿名需求統計、AI 草稿、候選方案、決策與履約事件。",
            parameters={"type": "object", "properties": {"campaign_id": {"type": "integer"}},
                        "required": ["campaign_id"]},
            handler=get_joint_service_summary, roles=MANAGER,
        ))
        registry.register(Tool(
            name="create_joint_service",
            description="管委會建立一份聯合服務草稿；只建立草稿，不會直接對住戶發布，執行前必須確認。",
            parameters={"type": "object", "properties": {
                "title": {"type": "string"}, "service_id": _service_id_schema("服務目錄代碼"),
            }, "required": ["title", "service_id"]},
            handler=create_joint_service, writes=True, roles=MANAGER,
        ))
        registry.register(Tool(
            name="publish_joint_service",
            description="管委會確認 AI 草稿後發布聯合服務、開始募集匿名需求；執行前必須確認。",
            parameters={"type": "object", "properties": {"campaign_id": {"type": "integer"}},
                        "required": ["campaign_id"]},
            handler=publish_joint_service, writes=True, roles=MANAGER,
        ))
        registry.register(Tool(
            name="join_joint_service",
            description="住戶以目前登入帳號匿名加入社區聯合服務；重複加入會更新需求，執行前必須確認台數與時段。",
            parameters={"type": "object", "properties": {
                "campaign_id": {"type": "integer"}, "units": {"type": "integer"},
                "equipment": {"type": "string"}, "preferred_slot": {"type": "string"},
                "special_requirement": {"type": "string"},
            }, "required": ["campaign_id", "units", "equipment", "preferred_slot"]},
            handler=join_joint_service, writes=True, roles=RESIDENT,
        ))
        registry.register(Tool(
            name="prepare_joint_service_proposals",
            description="管委會截止匿名需求募集並依聚合台數產生兩份分項方案，執行前必須確認。",
            parameters={"type": "object", "properties": {"campaign_id": {"type": "integer"}},
                        "required": ["campaign_id"]},
            handler=prepare_joint_service_proposals, writes=True, roles=MANAGER,
        ))
        registry.register(Tool(
            name="assign_joint_service_vendor",
            description="管委會看完兩案價格、時段、優點與限制後，確認指派其中一案；指派不可重複，執行前必須確認。",
            parameters={"type": "object", "properties": {
                "campaign_id": {"type": "integer"}, "proposal_id": {"type": "string"},
            }, "required": ["campaign_id", "proposal_id"]},
            handler=assign_joint_service_vendor, writes=True, roles=MANAGER,
        ))
        registry.register(Tool(
            name="list_assigned_joint_services",
            description="合作廠商查看已指派的社區聯合服務標準工單、匿名需求摘要、報價與履約狀態。",
            parameters=_empty_schema(), handler=list_assigned_joint_services, roles=PARTNER,
        ))
        registry.register(Tool(
            name="start_joint_service",
            description="合作廠商回報已開始執行社區聯合服務，狀態與事件會同步回管委會；執行前必須確認。",
            parameters={"type": "object", "properties": {"campaign_id": {"type": "integer"}},
                        "required": ["campaign_id"]},
            handler=start_joint_service, writes=True, roles=PARTNER,
        ))
        registry.register(Tool(
            name="complete_joint_service",
            description="合作廠商填寫完工說明並完成社區聯合服務，結果會同步回管委會；執行前必須確認。",
            parameters={"type": "object", "properties": {
                "campaign_id": {"type": "integer"}, "note": {"type": "string"},
            }, "required": ["campaign_id", "note"]},
            handler=complete_joint_service, writes=True, roles=PARTNER,
        ))

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
