"""目標導向的跨服務 LifeTask 編排。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from core.vendors import VendorClientError, VendorService

from .repository import LifeTaskRepositoryError, SqliteLifeTaskRepository


class LifeTaskError(RuntimeError):
    pass


class LifeTaskNotApplicable(LifeTaskError):
    pass


class LifeTaskUpstreamError(LifeTaskError):
    pass


DEMO_HOME = {
    "choice": "home", "label": "會員中心住家（競賽展示資料）",
    "countyCode": "01", "countyName": "臺北市", "districtCode": "002", "districtName": "大同區",
    "postalCode": "103", "address": "103臺北市大同區承德路一段 1 號",
    "dataSource": "competition_seed_profile",
}
DEMO_CONTACT = {
    "phone": "0912-000-168", "email": "xiaoyuan.demo@example.com",
    "dataSource": "competition_seed_profile",
}
SCOPES = {
    "personal": "只處理我的住家",
    "family": "分享給家庭群組",
    "community": "詢問社區是否有共同需求",
}


def _next_weekday(today: date, weekday: int) -> date:
    days = (weekday - today.weekday()) % 7
    return today + timedelta(days=days or 7)


class LifeTaskService:
    def __init__(
        self, repository: SqliteLifeTaskRepository, *, vendors: VendorService,
        today: date, openpoint_balance: int = 180,
    ) -> None:
        self.repository = repository
        self.vendors = vendors
        self.today = today
        self.openpoint_balance = openpoint_balance

    @staticmethod
    def _recognized_items(message: str) -> list[dict[str, str]]:
        text = message.strip().lower()
        items: list[dict[str, str]] = []
        if any(term in text for term in ("浴室燈", "燈壞", "燈不亮", "水電", "插座", "漏水")):
            items.append({
                "serviceId": "service-repair", "title": "浴室燈修繕",
                "needSummary": "檢查浴室燈具、開關與線路並完成必要修繕",
            })
        if "冷氣" in text and any(term in text for term in ("洗", "清", "很久", "髒")):
            items.append({
                "serviceId": "service-aircon", "title": "冷氣清洗",
                "needSummary": "清洗家用分離式冷氣並進行基礎運轉檢查",
            })
        return items

    def create_draft(self, *, message: str, account_id: str, display_name: str) -> dict[str, Any]:
        items = self._recognized_items(message)
        if len(items) < 2:
            raise LifeTaskNotApplicable("這不是跨服務生活任務，交由一般 AI 能力處理")
        existing = self.repository.find_open(account_id=account_id, utterance=message)
        if existing is not None:
            return self._decorate(existing)
        scheduled = _next_weekday(self.today, 5) if "週六" in message else None
        task = self.repository.create_draft(
            account_id=account_id, display_name=display_name, utterance=message,
            scheduled_date=scheduled.isoformat() if scheduled else None, items=items,
        )
        return self._decorate(task)

    def _decorate(self, task: dict[str, Any]) -> dict[str, Any]:
        task = {**task}
        task["statusLabel"] = {
            "needs_details": "需要補齊條件", "ready": "等待一次確認", "submitting": "正在建立廠商案件",
            "partial_failure": "部分案件待重試", "submitted": "已送交廠商", "quoted": "廠商已報價",
            "ordered": "已確認報價", "in_progress": "服務進行中", "completed": "全部完成",
        }.get(task["status"], task["status"])
        task["requirements"] = [
            {
                "id": "scheduledDate", "label": "服務日期", "required": True,
                "value": task.get("scheduledDate"),
                "options": ([{"value": task["scheduledDate"], "label": f"週六 {task['scheduledDate']}"}]
                            if task.get("scheduledDate") else []),
            },
            {
                "id": "address", "label": "服務地址", "required": True,
                "value": task.get("address", {}).get("choice") if task.get("address") else None,
                "options": [
                    {"value": "home", "label": "使用會員中心住家地址", "description": "臺北市大同區（競賽展示資料）"},
                    {"value": "custom", "label": "輸入其他地址", "description": "需填縣市、行政區與完整地址"},
                ],
            },
            {
                "id": "scope", "label": "分享範圍", "required": True, "value": task.get("scope"),
                "options": [{"value": key, "label": label} for key, label in SCOPES.items()],
            },
        ]
        task["missingFields"] = [item["id"] for item in task["requirements"] if not item.get("value")]
        task["readyForConfirmation"] = task["status"] == "ready" and not task["missingFields"]
        if task.get("points"):
            task["estimate"] = {
                "baseAmount": task["points"]["baseAmount"],
                "pointsApplied": task["points"]["pointsApplied"],
                "finalAmount": task["points"]["finalAmount"],
                "savedAmount": task["points"]["pointsApplied"],
                "source": "deterministic_rules+competition_seed_wallet",
            }
        task["dataUse"] = [
            "會員帳號：建立並追蹤你的生活任務",
            "展示住址與聯絡方式：提供所選廠商聯繫與履約",
            "OPENPOINT 展示帳本：只用於本次節省試算，非即時帳戶",
        ]
        return task

    def get(self, task_id: str, *, account_id: str, synchronize: bool = True) -> dict[str, Any]:
        task = self.repository.get(task_id)
        if task is None or task["accountId"] != account_id:
            raise LifeTaskError("查無這筆生活任務")
        if synchronize and any(item["externalInquiryId"] for item in task["items"]):
            task = self._synchronize(task)
        return self._decorate(task)

    def list_for_account(self, account_id: str) -> list[dict[str, Any]]:
        return [self.get(item["id"], account_id=account_id) for item in self.repository.list_for_account(account_id)]

    def configure(
        self, task_id: str, *, account_id: str, expected_version: int, scheduled_date: str,
        address_choice: str, scope: str, selected_vendors: dict[str, str] | None = None,
        custom_address: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.get(task_id, account_id=account_id, synchronize=False)
        if scope not in SCOPES:
            raise LifeTaskError("分享範圍只接受 personal、family 或 community")
        try:
            service_date = date.fromisoformat(scheduled_date)
        except ValueError as exc:
            raise LifeTaskError("服務日期格式不正確") from exc
        if service_date < self.today:
            raise LifeTaskError("服務日期不可早於今天")
        if address_choice == "home":
            address = dict(DEMO_HOME)
        elif address_choice == "custom":
            address = dict(custom_address or {})
            required = {"countyCode", "countyName", "districtCode", "districtName", "postalCode", "address"}
            if not required <= address.keys() or not all(str(address[key]).strip() for key in required):
                raise LifeTaskError("其他地址需提供完整縣市、行政區、郵遞區號與地址")
            address.update({"choice": "custom", "label": "其他服務地址", "dataSource": "member_input"})
        else:
            raise LifeTaskError("服務地址只接受 home 或 custom")

        slot = "weekend" if service_date.weekday() >= 5 else "weekday_afternoon"
        selected_vendors = selected_vendors or {}
        configured_items: list[dict[str, Any]] = []
        total = 0
        for item in task["items"]:
            result = self.vendors.match(
                item["serviceId"], county_code=address["countyCode"], district_code=address["districtCode"],
                slot=slot, urgent=False, limit=3,
            )
            candidates = result["vendors"]
            if not candidates:
                raise LifeTaskError(f"{item['title']}目前找不到可服務廠商")
            chosen_id = selected_vendors.get(item["id"])
            chosen = next((candidate for candidate in candidates if candidate["vendorId"] == chosen_id), candidates[0])
            total += int(chosen["basePrice"])
            configured_items.append({
                "id": item["id"], "vendorId": chosen["vendorId"], "vendorName": chosen["vendorName"],
                "basePrice": int(chosen["basePrice"]), "slot": slot, "candidates": candidates,
            })
        points_cap = total // 10
        points_applied = min(self.openpoint_balance, points_cap)
        points = {
            "balance": self.openpoint_balance, "baseAmount": total, "pointsApplied": points_applied,
            "finalAmount": total - points_applied, "rule": "競賽情境：1 點折 NT$1，本次服務最高折參考總額 10%",
            "dataSource": "competition_seed_wallet", "computedBy": "deterministic_rules",
        }
        try:
            updated = self.repository.configure(
                task_id, expected_version=expected_version, scheduled_date=scheduled_date,
                address=address, scope=scope, points=points, items=configured_items,
            )
        except LifeTaskRepositoryError as exc:
            raise LifeTaskError(str(exc)) from exc
        return self._decorate(updated)

    def confirm(self, task_id: str, *, account_id: str, expected_version: int) -> dict[str, Any]:
        task = self.get(task_id, account_id=account_id, synchronize=False)
        if task["status"] not in {"ready", "partial_failure"}:
            raise LifeTaskError("這筆生活任務目前不能送出")
        if task["status"] == "ready" and task["version"] != expected_version:
            raise LifeTaskError("生活任務已被更新，請重新檢查預覽")
        if not task.get("address") or not task.get("scheduledDate") or not task.get("scope"):
            raise LifeTaskError("請先補齊日期、地址與分享範圍")
        try:
            task = self.repository.set_task_status(
                task_id, "submitting", expected_version=task["version"] if task["status"] == "ready" else None,
            )
            for item in task["items"]:
                if item["externalInquiryId"]:
                    continue
                payload = {
                    "accountId": account_id, "serviceId": item["serviceId"], "vendorId": item["vendorId"],
                    "consumer": {"name": task["displayName"], "phone": DEMO_CONTACT["phone"], "email": DEMO_CONTACT["email"]},
                    "location": {key: task["address"][key] for key in (
                        "countyCode", "countyName", "districtCode", "districtName", "postalCode", "address"
                    )},
                    "preferredSlots": [item["slot"]], "budget": item["basePrice"] + 500,
                    "urgency": "normal", "summary": f"{task['scheduledDate']}・{item['title']}",
                    "answers": {
                        "taskId": task_id, "description": item["needSummary"],
                        "scheduledDate": task["scheduledDate"], "scope": task["scope"],
                    },
                    "externalReference": f"{task_id}:{item['id']}",
                }
                created = self.vendors.create_inquiry(
                    payload, idempotency_key=f"{task_id}:{item['id']}:inquiry",
                )["data"]
                self.repository.set_external_inquiry(item["id"], created["id"])
            self.repository.set_task_status(task_id, "submitted")
        except (VendorClientError, LifeTaskRepositoryError, KeyError, TypeError) as exc:
            self.repository.set_task_status(task_id, "partial_failure", error=str(exc))
            raise LifeTaskUpstreamError(f"廠商案件建立未完整完成，可安全重試：{exc}") from exc
        return self.get(task_id, account_id=account_id)

    def accept_quotes(
        self, task_id: str, *, account_id: str, expected_version: int,
        selected_quotes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        task = self.get(task_id, account_id=account_id)
        if task["version"] != expected_version:
            raise LifeTaskError("生活任務已被更新，請重新檢查報價")
        selected_quotes = selected_quotes or {}
        for item in task["items"]:
            if item["externalOrderId"]:
                continue
            quotes = item.get("quotes") or []
            quote_id = selected_quotes.get(item["id"])
            quote = next((row for row in quotes if row["id"] == quote_id), quotes[0] if quotes else None)
            if quote is None:
                raise LifeTaskError(f"{item['title']}尚未收到廠商報價")
            created = self.vendors.create_order({
                "inquiryId": item["externalInquiryId"], "quoteId": quote["id"],
                "accountId": account_id, "externalReference": f"{task_id}:{item['id']}",
            }, idempotency_key=f"{task_id}:{item['id']}:order")["data"]
            self.repository.set_external_order(item["id"], created["id"])
        self.repository.set_task_status(task_id, "ordered")
        return self.get(task_id, account_id=account_id)

    def _synchronize(self, task: dict[str, Any]) -> dict[str, Any]:
        synced_items: list[dict[str, Any]] = []
        statuses: list[str] = []
        for item in task["items"]:
            row = {**item, "quotes": [], "vendorInquiry": None, "vendorOrder": None}
            if item["externalInquiryId"]:
                try:
                    row["vendorInquiry"] = self.vendors.get_inquiry(item["externalInquiryId"])["data"]
                    row["quotes"] = self.vendors.list_quotes(item["externalInquiryId"])["data"]
                    remote_status = "quoted" if row["quotes"] else row["vendorInquiry"]["status"]
                    if item["externalOrderId"]:
                        row["vendorOrder"] = self.vendors.get_order(item["externalOrderId"])["data"]
                        remote_status = row["vendorOrder"]["status"]
                    row["status"] = remote_status
                except VendorClientError as exc:
                    row["syncError"] = str(exc)
            statuses.append(row["status"])
            synced_items.append(row)
        task = {**task, "items": synced_items}
        if statuses and all(status == "completed" for status in statuses):
            task["status"] = "completed"
        elif any(status in {"in_service", "in_progress"} for status in statuses):
            task["status"] = "in_progress"
        elif any(item.get("vendorOrder") for item in synced_items):
            task["status"] = "ordered"
        elif statuses and all(status == "quoted" for status in statuses):
            task["status"] = "quoted"
        return task
