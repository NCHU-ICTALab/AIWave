"""Agent 協調器(spec 15 §4):理解 → 拆解 → 查真目錄 → 提案 → 預填 TaskDraft。

責任邊界:
- LLM 只做三件事:把使用者語句拆成子任務、抽服務關鍵詞/日期片語、抽表單欄位值。
- 服務是否存在(Registry)、日期(TimeResolver)、方案/時段(目錄投影)、
  價格(pricing.estimate)、授權(Grant)全部由確定性模組裁決。
- 提案理由是模板化文字(評分/價格/時段),不是 LLM 生成,因此永遠可驗證。
- LLM 輸出解析失敗:重試一次,再失敗就誠實降級為追問;絕不假裝理解成功。
- 這裡只讀目錄與寫草稿;送單走 platform_core 與手動完全相同的 submit 閉包。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from core.catalog.domains import get_domain
from core.catalog.pricing import estimate

from .registry import ServiceRegistry
from .time_resolver import TimeResolver

STAGE_UNDERSTAND = "理解需求"
STAGE_CATALOG = "查詢可用方案與時段"
STAGE_PROPOSE = "整理方案"
STAGE_DRAFT = "預填正式表單"
STAGE_WAIT = "等待你確認"


@dataclass
class AgentTurn:
    """一輪處理的結果:新增的助理訊息、經過的階段、更新後 session。"""

    session: dict
    stages: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)


class AgentOrchestrator:
    def __init__(
        self,
        *,
        llm_factory: Callable[[], Any],
        registry: ServiceRegistry,
        time_resolver: TimeResolver,
        catalog: Any,                     # SqliteCatalogRepository
        drafts: Any,                      # SqliteTaskDraftRepository
        points: Any,                      # SqlitePointsLedger(查可用點數供試算)
    ) -> None:
        self._llm_factory = llm_factory
        self.registry = registry
        self.time_resolver = time_resolver
        self.catalog = catalog
        self.drafts = drafts
        self.points = points

    # ── LLM 呼叫(唯一入口,含重試與誠實降級) ─────────────

    def _llm_json(self, system: str, user: str) -> object | None:
        try:
            llm = self._llm_factory()
        except Exception:
            return None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for _ in range(2):  # 一次重試
            try:
                return llm.json(messages, temperature=0.0, max_tokens=700)
            except Exception:
                continue
        return None

    # ── 對外主入口 ───────────────────────────────

    def handle(
        self,
        session: dict,
        *,
        owner: dict,
        message: str | None = None,
        action: dict | None = None,
        on_stage: Callable[[str], None] | None = None,
    ) -> AgentTurn:
        turn = AgentTurn(session=session)

        def stage(name: str) -> None:
            turn.stages.append(name)
            if on_stage:
                on_stage(name)

        if action:
            self._handle_action(turn, owner=owner, action=action, stage=stage)
        elif message and message.strip():
            self._append(session, "user", message.strip())
            self._handle_message(turn, owner=owner, message=message.strip(), stage=stage)
        else:
            self._append(session, "assistant", "想處理什麼生活上的事?可以一句話描述,例如「爸媽週六要來,幫我安排清潔和訂餐廳」。")
        return turn

    # ── 訊息處理 ────────────────────────────────

    def _handle_message(self, turn: AgentTurn, *, owner: dict, message: str, stage) -> None:
        session = turn.session

        # 若正在等表單欄位,先試著從回覆抽欄位值
        if session.get("awaiting") == "fields":
            if self._try_fill_fields(turn, owner=owner, message=message, stage=stage):
                return

        stage(STAGE_UNDERSTAND)
        decomposition = self._understand(message)
        if decomposition is None:
            self._append(
                session, "assistant",
                "我沒有把握正確理解這句話(模型回應無法解析)。可以換個說法,或直接說要哪一類服務,例如「找人修水電」「訂餐廳」?",
            )
            session["awaiting"] = None
            return

        new_subtasks: list[dict] = []
        clarifies: list[str] = []
        for item in decomposition:
            resolution = self.registry.resolve(item["serviceHint"] or item["goal"])
            subtask = {
                "id": f"task-{uuid4().hex[:8]}",
                "goal": item["goal"],
                "domain": resolution.matched,
                "datePhrase": item.get("datePhrase") or "",
                "time": None,
                "status": "resolved" if resolution.matched else "clarify",
                "clarify": resolution.clarify,
                "clarifyOptions": [dict(option) for option in resolution.options],
                "proposals": [],
                "selected": None,
                "draftId": None,
                "missingFields": [],
                "subjectId": None,
                "subjectType": None,
            }
            if subtask["datePhrase"]:
                resolved = self.time_resolver.resolve(subtask["datePhrase"])
                if resolved.date:
                    subtask["time"] = resolved.to_dict()
            if resolution.matched is None and not resolution.clarify:
                subtask["clarify"] = (
                    f"「{item['goal']}」我還不確定對應哪一類服務,可以描述得更具體一點嗎?"
                )
            if subtask["status"] == "clarify":
                clarifies.append(subtask["clarify"])
            new_subtasks.append(subtask)

        session["subtasks"] = new_subtasks

        resolved_tasks = [item for item in new_subtasks if item["status"] == "resolved"]
        if resolved_tasks:
            stage(STAGE_CATALOG)
            for subtask in resolved_tasks:
                self._build_proposals(subtask)
            stage(STAGE_PROPOSE)

        reply_parts: list[str] = []
        if resolved_tasks:
            summary = "、".join(
                f"{self._domain_name(item['domain'])}({item['time']['echo']})" if item["time"]
                else self._domain_name(item["domain"])
                for item in resolved_tasks
            )
            reply_parts.append(f"我把需求拆成:{summary}。以下方案來自平台核准店家的真實資料,請選一個,最後由你決定。")
        for question in clarifies:
            reply_parts.append(question)
        if not reply_parts:
            reply_parts.append("可以再描述具體一點嗎?例如要哪一類服務、什麼時間。")

        self._append(session, "assistant", " ".join(reply_parts))
        session["awaiting"] = "option" if resolved_tasks else "clarify"
        stage(STAGE_WAIT)

    def _understand(self, message: str) -> list[dict] | None:
        system = (
            "你是生活服務平台的需求理解器。把使用者的一句話拆成 1~4 個子任務。"
            "只回覆 JSON,格式:{\"subtasks\":[{\"goal\":\"子任務描述\","
            "\"serviceHint\":\"服務關鍵詞(如 修繕/清潔/訂位/外送/洗車/寄件/領藥/購物/訂房/門票)\","
            "\"datePhrase\":\"時間片語,沒有就空字串\"}]}"
            "不要自己決定日期或價格;不要編造使用者沒說的需求。"
        )
        payload = self._llm_json(system, message)
        if not isinstance(payload, dict):
            return None
        raw = payload.get("subtasks")
        if not isinstance(raw, list) or not raw:
            return None
        items: list[dict] = []
        for entry in raw[:4]:
            if not isinstance(entry, dict):
                return None
            goal = str(entry.get("goal") or "").strip()
            if not goal:
                return None
            items.append({
                "goal": goal,
                "serviceHint": str(entry.get("serviceHint") or "").strip(),
                "datePhrase": str(entry.get("datePhrase") or "").strip(),
            })
        return items

    # ── 提案(完全確定性:真目錄+模板理由) ─────────────

    def _domain_name(self, domain_type: str | None) -> str:
        if not domain_type:
            return "服務"
        try:
            return get_domain(domain_type).display_name
        except Exception:
            return domain_type

    def _build_proposals(self, subtask: dict) -> None:
        domain_type = subtask["domain"]
        spec = get_domain(domain_type)
        providers = self.catalog.list_providers(scene=spec.scene)
        candidates: list[dict] = []
        for provider in providers:
            try:
                detail = self.catalog.get_provider(provider["id"])
            except Exception:
                continue
            for offering in detail["offerings"]:
                if offering.get("domainType") != domain_type:
                    continue
                slot = None
                if offering.get("fulfillmentKind") == "booking":
                    slot = self._first_slot(provider["id"], offering["id"], subtask.get("time"))
                    if slot is None:
                        continue  # 沒有真實空檔就不提案,不讓使用者選到不存在的時間
                reasons = [f"評分 {provider.get('rating', '—')}(展示資料)"]
                if offering.get("basePrice", 0) > 0:
                    reasons.append(f"NT${offering['basePrice']:,}/{offering.get('pricingUnit') or '次'}")
                else:
                    reasons.append("免費預約")
                if slot:
                    reasons.append(f"最早可約 {slot['startsAt'][5:16].replace('T', ' ')}")
                candidates.append({
                    "id": f"option-{uuid4().hex[:8]}",
                    "providerId": provider["id"],
                    "providerName": provider["name"],
                    "offeringId": offering["id"],
                    "offeringName": offering["name"],
                    "fulfillmentKind": offering.get("fulfillmentKind"),
                    "basePrice": offering.get("basePrice", 0),
                    "slot": slot,
                    "reasons": reasons,
                    "rating": provider.get("rating") or 0,
                })
        candidates.sort(key=lambda item: (-(item["rating"] or 0), item["basePrice"]))
        subtask["proposals"] = candidates[:3]
        if not candidates:
            subtask["status"] = "clarify"
            subtask["clarify"] = (
                f"{self._domain_name(domain_type)}目前查不到可用的方案或時段,要換個時間或改其他服務嗎?"
            )

    def _first_slot(self, provider_id: str, offering_id: str, time_info: dict | None) -> dict | None:
        starts_after = None
        starts_before = None
        if time_info and time_info.get("date"):
            starts_after = f"{time_info['date']}T00:00:00"
            end = time_info.get("endDate") or time_info["date"]
            starts_before = f"{end}T23:59:59"
        slots = self.catalog.list_slots(
            provider_id, offering_id=offering_id,
            starts_after=starts_after, starts_before=starts_before,
        )
        for slot in slots:
            if slot.get("status") == "available":
                return slot
        return None

    # ── 結構化動作(前端按鈕;不經 LLM) ─────────────────

    def _handle_action(self, turn: AgentTurn, *, owner: dict, action: dict, stage) -> None:
        session = turn.session
        kind = action.get("type")
        if kind == "clarify_option":
            self._act_clarify(turn, owner=owner, action=action, stage=stage)
        elif kind == "select_option":
            self._act_select(turn, owner=owner, action=action, stage=stage)
        else:
            self._append(session, "assistant", "這個操作我不認識,請重新選擇。")

    def _act_clarify(self, turn: AgentTurn, *, owner: dict, action: dict, stage) -> None:
        session = turn.session
        subtask = self._find_subtask(session, action.get("subtaskId"))
        domain = str(action.get("domain") or "")
        label = str(action.get("label") or domain)
        if subtask is None or not domain:
            self._append(session, "assistant", "找不到要釐清的項目,請重新描述需求。")
            return
        subtask["domain"] = domain
        subtask["goal"] = f"{subtask['goal']}({label})"
        subtask["status"] = "resolved"
        subtask["clarify"] = None
        subtask["clarifyOptions"] = []
        stage(STAGE_CATALOG)
        self._build_proposals(subtask)
        stage(STAGE_PROPOSE)
        if subtask["proposals"]:
            self._append(session, "assistant", f"了解,是{label}。以下是可選方案,請挑一個。")
            session["awaiting"] = "option"
        else:
            self._append(session, "assistant", subtask.get("clarify") or "目前查不到可用方案。")
            session["awaiting"] = "clarify"
        stage(STAGE_WAIT)

    def _act_select(self, turn: AgentTurn, *, owner: dict, action: dict, stage) -> None:
        """使用者選定方案 → 預填 TaskDraft(source=agent),缺欄位就開口問。"""
        session = turn.session
        subtask = self._find_subtask(session, action.get("subtaskId"))
        if subtask is None:
            self._append(session, "assistant", "找不到這個子任務,請重新選擇。")
            return
        option = next((item for item in subtask["proposals"] if item["id"] == action.get("optionId")), None)
        if option is None:
            self._append(session, "assistant", "找不到這個方案,請重新選擇。")
            return

        stage(STAGE_DRAFT)
        values: dict[str, Any] = {
            "provider_id": option["providerId"],
            "offering_id": option["offeringId"],
        }
        slot = option.get("slot")
        if slot:
            values.update({
                "location_id": slot.get("locationId"),
                "resource_id": slot.get("resourceId"),
                "slot_id": slot["id"],
                "starts_at": slot["startsAt"],
                "ends_at": slot["endsAt"],
            })
        else:
            values["quantity"] = 1

        spec = get_domain(subtask["domain"])
        draft = self.drafts.create(
            demo_workspace_id=owner["demo_workspace_id"],
            workspace_id=owner["workspace_id"],
            account_id=owner["account_id"],
            domain_type=subtask["domain"],
            values=values,
            source="agent",
            idempotency_key=f"agent-{session['id']}-{subtask['id']}",
        )
        subtask["selected"] = option
        subtask["draftId"] = draft["id"]
        missing = [name for name in spec.required_fields
                   if not str(draft["values"].get(name) or "").strip()]
        subtask["missingFields"] = missing
        subtask["status"] = "fields" if missing else "ready"

        quote = estimate(
            offering={"basePrice": option["basePrice"], "id": option["offeringId"],
                      "name": option["offeringName"], "currency": "TWD"},
            quantity=1, points_to_redeem=0,
            points_balance=self._points_balance(owner),
        )
        subtask["quote"] = {"payable": quote["payable"], "subtotal": quote["subtotal"]}

        when = f",時間 {slot['startsAt'][5:16].replace('T', ' ')}" if slot else ""
        if missing:
            asks = "、".join(self._field_label(name) for name in missing)
            self._append(
                session, "assistant",
                f"已選{option['providerName']}・{option['offeringName']}{when},並預填好正式表單(草稿)。"
                f"還差:{asks}。可以直接在這裡回覆,或點「切到手動填寫」到表單裡改;兩邊是同一份草稿。",
            )
            session["awaiting"] = "fields"
        else:
            self._append(
                session, "assistant",
                f"已選{option['providerName']}・{option['offeringName']}{when}。",
            )
            self._after_subtask_ready(session, subtask)
        stage(STAGE_WAIT)

    # ── 欄位補齊(LLM 抽值,確定性驗證) ─────────────────

    def _try_fill_fields(self, turn: AgentTurn, *, owner: dict, message: str, stage) -> bool:
        session = turn.session
        subtask = next((item for item in session["subtasks"] if item["status"] == "fields"), None)
        if subtask is None:
            return False

        # 先重讀草稿:使用者可能已切到手動精靈補完(user 來源優先),不必經 LLM
        refreshed = self.drafts.require_owned(
            subtask["draftId"], demo_workspace_id=owner["demo_workspace_id"],
            workspace_id=owner["workspace_id"], account_id=owner["account_id"],
        )
        spec = get_domain(subtask["domain"])
        already_missing = [name for name in spec.required_fields
                           if not str(refreshed["values"].get(name) or "").strip()]
        if not already_missing:
            subtask["missingFields"] = []
            subtask["status"] = "ready"
            self._after_subtask_ready(session, subtask)
            stage(STAGE_WAIT)
            return True
        subtask["missingFields"] = already_missing

        stage(STAGE_UNDERSTAND)
        fields = subtask["missingFields"]
        system = (
            "從使用者回覆中抽出指定欄位的值。只回覆 JSON:{\"values\":{欄位:值}}。"
            "抽不到的欄位不要包含;不要編造。欄位清單:" + ", ".join(fields)
        )
        payload = self._llm_json(system, message)
        extracted: dict[str, str] = {}
        if isinstance(payload, dict) and isinstance(payload.get("values"), dict):
            for name in fields:
                value = payload["values"].get(name)
                if value is not None and str(value).strip():
                    extracted[name] = str(value).strip()
        # LLM 失敗時的確定性退路:電話號碼可直接規則抽取
        if not extracted and "phone" in fields:
            match = re.search(r"09\d{2}[- ]?\d{3}[- ]?\d{3}", message)
            if match:
                extracted["phone"] = match.group(0)
        if not extracted:
            self._append(
                session, "assistant",
                "我沒有從回覆裡抓到需要的欄位(不會替你猜)。也可以點「切到手動填寫」直接在表單輸入。",
            )
            return True

        draft = self.drafts.require_owned(
            subtask["draftId"], demo_workspace_id=owner["demo_workspace_id"],
            workspace_id=owner["workspace_id"], account_id=owner["account_id"],
        )
        updated = self.drafts.update_fields(
            subtask["draftId"], demo_workspace_id=owner["demo_workspace_id"],
            workspace_id=owner["workspace_id"], account_id=owner["account_id"],
            expected_version=draft["version"], values=extracted, source="agent",
        )
        spec = get_domain(subtask["domain"])
        missing = [name for name in spec.required_fields
                   if not str(updated["values"].get(name) or "").strip()]
        subtask["missingFields"] = missing
        if missing:
            asks = "、".join(self._field_label(name) for name in missing)
            self._append(session, "assistant", f"收到。還差:{asks}。")
        else:
            subtask["status"] = "ready"
            self._after_subtask_ready(session, subtask)
        stage(STAGE_WAIT)
        return True

    def _after_subtask_ready(self, session: dict, subtask: dict) -> None:
        """子任務備齊:還有別的子任務待處理就先引導,全部備齊才進授權。"""
        quote = subtask.get("quote") or {}
        pending = [item for item in session["subtasks"]
                   if item["id"] != subtask["id"] and item["status"] in {"resolved", "fields", "clarify"}]
        if pending:
            session["awaiting"] = "option"
            names = "、".join(item["goal"] for item in pending)
            self._append(
                session, "assistant",
                f"這一項備齊了(金額 NT${quote.get('payable', 0):,})。還有:{names},請繼續選擇方案或補資料。",
            )
        else:
            session["awaiting"] = "grant"
            self._append(
                session, "assistant",
                f"表單都備齊了,金額 NT${quote.get('payable', 0):,}。下一步請核准執行授權,我才會真正送出。",
            )

    # ── 小工具 ─────────────────────────────────

    def _points_balance(self, owner: dict) -> int:
        try:
            return int(self.points.balance(
                demo_workspace_id=owner["demo_workspace_id"],
                workspace_id=owner["workspace_id"], account_id=owner["account_id"],
            ))
        except Exception:
            return 0

    @staticmethod
    def _find_subtask(session: dict, subtask_id: Any) -> dict | None:
        return next((item for item in session["subtasks"] if item["id"] == subtask_id), None)

    _FIELD_LABELS = {
        "problem": "問題描述", "address": "服務地址", "phone": "聯絡電話",
        "party_size": "人數", "contact_name": "聯絡人姓名", "plate_number": "車牌號碼",
        "car_type": "車型", "rx_type": "處方箋類型", "patient_name": "領藥人姓名",
        "pickup_in_person": "是否本人領取", "rx_confirmed": "辨識結果確認",
        "package_size": "包裹尺寸", "pickup_address": "取件地址", "receiver_address": "送達地址",
        "receiver_name": "取件人姓名", "pickup_method": "取貨方式", "delivery_address": "外送地址",
        "sender_name": "寄件人姓名", "item_name": "商品名稱", "use_date": "使用日期",
        "buyer_name": "訂購人姓名",
    }

    def _field_label(self, name: str) -> str:
        return self._FIELD_LABELS.get(name, name)

    @staticmethod
    def _append(session: dict, role: str, content: str) -> None:
        session["messages"].append({"role": role, "content": content})
