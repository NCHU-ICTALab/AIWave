"""客服 application service：訂單所有權、問題診斷與工單規則的單一來源。"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from core.inquiries import InquiryRepository
from core.orders import SqliteOrderRepository

from .repository import SupportError, SupportRepository


_CATEGORIES = {
    "delay": {
        "label": "服務延遲／未到場",
        "terms": ("延遲", "晚", "沒來", "未到", "沒有出現", "等很久", "沒到"),
        "priority": "high",
        "sla": 4,
        "route": "service_coordination",
    },
    "payment": {
        "label": "付款／金額問題",
        "terms": ("付款", "扣款", "重複扣", "金額", "發票", "退款"),
        "priority": "high",
        "sla": 4,
        "route": "billing_review",
    },
    "service_quality": {
        "label": "服務品質問題",
        "terms": ("做不好", "品質", "損壞", "弄壞", "不滿意", "沒清乾淨", "態度"),
        "priority": "high",
        "sla": 4,
        "route": "quality_review",
    },
    "change_request": {
        "label": "取消／改期需求",
        "terms": ("取消", "改期", "改時間", "延期", "更改預約"),
        "priority": "medium",
        "sla": 8,
        "route": "schedule_change",
    },
    "other": {
        "label": "其他訂單問題",
        "terms": (),
        "priority": "normal",
        "sla": 24,
        "route": "manual_triage",
    },
}


class SupportService:
    def __init__(
        self,
        repository: SupportRepository,
        *,
        inquiries: InquiryRepository,
        orders: SqliteOrderRepository | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.repository = repository
        self.inquiries = inquiries
        self.orders = orders
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._diagnosis_previews: dict[str, tuple[str, str, str, float]] = {}

    def _subject(self, account_id: str, subject_id: str) -> dict:
        if subject_id.startswith("INQ-"):
            record = self.inquiries.get(subject_id)
            if record is None or record.get("account_id") != account_id:
                raise SupportError(f"查無可處理的訂單 {subject_id}")
            latest = record.get("events", [])[-1] if record.get("events") else None
            return {
                "type": "inquiry",
                "id": subject_id,
                "serviceId": record.get("service_id"),
                "status": record["status"],
                "statusLabel": record["status_label"],
                "latestEvent": latest,
            }
        if subject_id.startswith("ORD-") and self.orders is not None:
            record = self.orders.get(subject_id)
            if record is None or record.get("accountId") != account_id:
                raise SupportError(f"查無可處理的訂單 {subject_id}")
            latest = record.get("events", [])[-1] if record.get("events") else None
            return {
                "type": "order",
                "id": subject_id,
                "serviceId": record.get("serviceId"),
                "status": record["status"],
                "statusLabel": record["statusLabel"],
                "latestEvent": latest,
            }
        raise SupportError(f"查無可處理的訂單 {subject_id}")

    def _diagnosis(self, *, account_id: str, subject_id: str, issue_text: str) -> dict:
        issue = issue_text.strip()
        if len(issue) < 4:
            raise SupportError("請至少用一句話描述發生什麼事")
        if len(issue) > 500:
            raise SupportError("問題描述請控制在 500 字以內")
        subject = self._subject(account_id, subject_id)
        category = next(
            (name for name, config in _CATEGORIES.items() if config["terms"] and any(term in issue for term in config["terms"])),
            "other",
        )
        config = _CATEGORIES[category]
        moment = self._now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        evidence = [f"訂單目前狀態：{subject['statusLabel']}"]
        if subject.get("latestEvent"):
            evidence.append(f"最近事件：{subject['latestEvent']['type']}（{subject['latestEvent']['occurred_at']}）")
        return {
            "subject": subject,
            "issueText": issue,
            "category": category,
            "categoryLabel": config["label"],
            "priority": config["priority"],
            "slaHours": config["sla"],
            "dueAt": (moment + timedelta(hours=config["sla"])).isoformat(),
            "recommendedRoute": config["route"],
            "evidence": evidence,
            "computedBy": "deterministic_rules",
        }

    def diagnose(self, *, account_id: str, subject_id: str, issue_text: str) -> dict:
        diagnosis = self._diagnosis(account_id=account_id, subject_id=subject_id, issue_text=issue_text)
        now = self._monotonic()
        self._diagnosis_previews = {
            key: preview for key, preview in self._diagnosis_previews.items() if preview[3] >= now
        }
        token = secrets.token_urlsafe(24)
        self._diagnosis_previews[token] = (
            account_id,
            subject_id,
            diagnosis["issueText"],
            now + 300,
        )
        return {**diagnosis, "diagnosisToken": token, "previewExpiresInSeconds": 300}

    def create_ticket(
        self,
        *,
        account_id: str,
        subject_id: str,
        issue_text: str,
        diagnosis_token: str,
    ) -> dict:
        pending = self._diagnosis_previews.pop(diagnosis_token, None)
        normalized_issue = issue_text.strip()
        if (
            pending is None
            or pending[3] < self._monotonic()
            or pending[:3] != (account_id, subject_id, normalized_issue)
        ):
            raise SupportError("診斷預覽已失效，請重新整理問題與處理方式")
        diagnosis = self._diagnosis(account_id=account_id, subject_id=subject_id, issue_text=normalized_issue)
        return self.repository.create(
            account_id=account_id,
            subject_type=diagnosis["subject"]["type"],
            subject_id=subject_id,
            category=diagnosis["category"],
            category_label=diagnosis["categoryLabel"],
            issue_text=diagnosis["issueText"],
            priority=diagnosis["priority"],
            recommended_route=diagnosis["recommendedRoute"],
            sla_hours=diagnosis["slaHours"],
            due_at=diagnosis["dueAt"],
            subject_snapshot=diagnosis["subject"],
        )

    def list_for_account(self, account_id: str) -> list[dict]:
        return self.repository.list_for_account(account_id)

    def list_queue(self) -> list[dict]:
        return self.repository.list_queue()

    def start_ticket(self, ticket_id: str, *, actor: str) -> dict:
        return self.repository.transition(ticket_id, target="in_progress", actor=actor)

    def resolve_ticket(self, ticket_id: str, *, actor: str, note: str) -> dict:
        return self.repository.transition(ticket_id, target="resolved", actor=actor, note=note)
