"""訂單異常與客服閉環：診斷 → 人確認 → 工單 → 處理事件。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from agent.planner import Planner
from core.community import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from core.orders import SqliteOrderRepository
from core.personalization import PersonalizationService, SqlitePersonalizationRepository
from core.retail import RetailService, SqliteRetailRepository
from core.services import LifeServicesService
from core.support import SupportError, SupportService, SqliteSupportRepository
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext


NOW = lambda: datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)  # noqa: E731
ACCOUNT = "019e6c8c-a061-7197-be0f-b7d341dbafdd"
OTHER_ACCOUNT = "019c3f5f-794a-7245-a1e1-5a5b86cb3a58"
FEEDBACK = {"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "燈具／開關"}]}]}


def _confirmed_inquiry(db: Path) -> tuple[SqliteInquiryRepository, str]:
    inquiries = SqliteInquiryRepository(db, now=NOW)
    service = LifeServicesService(inquiries, today=date(2026, 7, 28))
    inquiry_id = service.submit_inquiry(
        form_id=105,
        feedback_content=FEEDBACK,
        service_id="service-repair",
        account_id=ACCOUNT,
    )["id"]
    inquiries.add_quote(
        inquiry_id,
        items=[{"name": "材料費", "amount": 300}, {"name": "施工費", "amount": 900}],
        vendor_name="安心修繕",
    )
    inquiries.confirm_quote(inquiry_id)
    return inquiries, inquiry_id


def test_diagnosis_uses_order_state_and_gives_a_recoverable_next_step(tmp_path: Path):
    inquiries, inquiry_id = _confirmed_inquiry(tmp_path / "support.sqlite3")
    service = SupportService(
        SqliteSupportRepository(tmp_path / "support.sqlite3", now=NOW),
        inquiries=inquiries,
        now=NOW,
    )

    diagnosis = service.diagnose(
        account_id=ACCOUNT,
        subject_id=inquiry_id,
        issue_text="師傅已經晚兩個小時還沒來，也沒有通知",
    )

    assert diagnosis["category"] == "delay"
    assert diagnosis["categoryLabel"] == "服務延遲／未到場"
    assert diagnosis["priority"] == "high"
    assert diagnosis["slaHours"] == 4
    assert diagnosis["subject"]["status"] == "confirmed"
    assert diagnosis["recommendedRoute"] == "service_coordination"
    assert diagnosis["computedBy"] == "deterministic_rules"
    assert "已確認，等待服務" in diagnosis["evidence"][0]


def test_ticket_is_owned_deduplicated_and_records_every_transition(tmp_path: Path):
    inquiries, inquiry_id = _confirmed_inquiry(tmp_path / "support.sqlite3")
    service = SupportService(
        SqliteSupportRepository(tmp_path / "support.sqlite3", now=NOW),
        inquiries=inquiries,
        now=NOW,
    )

    with pytest.raises(SupportError, match="查無可處理的訂單"):
        service.diagnose(account_id=OTHER_ACCOUNT, subject_id=inquiry_id, issue_text="師傅沒來")

    preview = service.diagnose(
        account_id=ACCOUNT,
        subject_id=inquiry_id,
        issue_text="師傅已經晚兩個小時還沒來",
    )
    ticket = service.create_ticket(
        account_id=ACCOUNT,
        subject_id=inquiry_id,
        issue_text="師傅已經晚兩個小時還沒來",
        diagnosis_token=preview["diagnosisToken"],
    )
    assert ticket["id"] == "SUP-20260728-001"
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"
    assert ticket["subjectId"] == inquiry_id
    assert ticket["events"][0]["type"] == "support.created"

    with pytest.raises(SupportError, match="已有處理中的客服工單"):
        duplicate_preview = service.diagnose(account_id=ACCOUNT, subject_id=inquiry_id, issue_text="還是沒來")
        service.create_ticket(
            account_id=ACCOUNT, subject_id=inquiry_id, issue_text="還是沒來",
            diagnosis_token=duplicate_preview["diagnosisToken"],
        )

    with pytest.raises(SupportError, match="無法轉為"):
        service.resolve_ticket(ticket["id"], actor="社區客服", note="跳過接手")

    working = service.start_ticket(ticket["id"], actor="社區客服")
    with pytest.raises(SupportError, match="無法轉為"):
        service.start_ticket(ticket["id"], actor="另一位客服")
    resolved = service.resolve_ticket(working["id"], actor="社區客服", note="已重新安排 14:00 到場")
    assert resolved["status"] == "resolved"
    assert [event["type"] for event in resolved["events"]] == [
        "support.created", "support.in_progress", "support.resolved",
    ]
    assert resolved["events"][-1]["detail"] == "已重新安排 14:00 到場"


class UnusedLlm:
    def json(self, *args, **kwargs):
        raise AssertionError("support endpoints do not need an LLM")


class BrokenLlm:
    def json(self, *args, **kwargs):
        raise RuntimeError("offline")


def test_planner_can_route_an_order_problem_to_grounded_diagnosis_when_the_model_is_offline(tmp_path: Path):
    db = tmp_path / "support.sqlite3"
    inquiries, inquiry_id = _confirmed_inquiry(db)
    life = LifeServicesService(inquiries, today=date(2026, 7, 28))
    support = SupportService(SqliteSupportRepository(db, now=NOW), inquiries=inquiries, now=NOW)
    registry = build_registry(
        services=life,
        group_buys=SqliteGroupBuyRepository(db),
        support=support,
        today=date(2026, 7, 28),
    )
    resident = ToolContext(account_id=ACCOUNT, role="user")

    plan = Planner(BrokenLlm(), registry).plan(f"{inquiry_id} 的師傅晚兩個小時還沒來", resident)
    executed = Planner(BrokenLlm(), registry).execute(plan, resident)

    assert [step.tool for step in executed.steps] == ["diagnose_order_issue"]
    assert executed.steps[0].arguments["subject_id"] == inquiry_id
    assert executed.steps[0].result["category"] == "delay"


def test_http_support_flow_returns_the_same_ticket_to_resident_and_queue(tmp_path: Path):
    db = tmp_path / "support.sqlite3"
    inquiries, inquiry_id = _confirmed_inquiry(db)
    client = TestClient(create_app(
        repository=inquiries,
        group_buys=SqliteGroupBuyRepository(db),
        support_repository=SqliteSupportRepository(db, now=NOW),
        llm_factory=UnusedLlm,
    ))

    resident_headers = {"X-Account-Id": ACCOUNT, "X-Role": "user"}
    manager_headers = {"X-Role": "manager"}
    diagnosed = client.post("/api/v1/support/diagnose", headers=resident_headers, json={
        "subject_id": inquiry_id,
        "issue_text": "師傅沒有出現，也沒有通知",
    })
    assert diagnosed.status_code == 200
    assert diagnosed.json()["data"]["category"] == "delay"

    created = client.post("/api/v1/support/tickets", headers=resident_headers, json={
        "subject_id": inquiry_id,
        "issue_text": "師傅沒有出現，也沒有通知",
        "diagnosis_token": diagnosed.json()["data"]["diagnosisToken"],
    })
    assert created.status_code == 200
    ticket_id = created.json()["data"]["id"]

    assert client.get("/api/v1/support/tickets", headers=resident_headers).json()["data"][0]["id"] == ticket_id
    assert client.get("/api/v1/support/queue", headers=resident_headers).status_code == 403
    assert client.get("/api/v1/support/queue", headers=manager_headers).json()["data"][0]["id"] == ticket_id

    started = client.post(f"/api/v1/support/tickets/{ticket_id}/start", headers=manager_headers, json={})
    assert started.json()["data"]["status"] == "in_progress"
    resolved = client.post(f"/api/v1/support/tickets/{ticket_id}/resolve", headers=manager_headers, json={
        "note": "已重新安排 14:00 到場",
    })
    assert resolved.json()["data"]["status"] == "resolved"
    assert resolved.json()["data"]["events"][-1]["actor"] == "社區管理者"


def test_ticket_creation_requires_the_exact_unexpired_diagnosis_preview(tmp_path: Path):
    inquiries, inquiry_id = _confirmed_inquiry(tmp_path / "support.sqlite3")
    service = SupportService(SqliteSupportRepository(tmp_path / "support.sqlite3", now=NOW), inquiries=inquiries, now=NOW)
    preview = service.diagnose(account_id=ACCOUNT, subject_id=inquiry_id, issue_text="師傅還沒來")

    with pytest.raises(SupportError, match="診斷預覽已失效"):
        service.create_ticket(
            account_id=ACCOUNT, subject_id=inquiry_id, issue_text="改過的問題",
            diagnosis_token=preview["diagnosisToken"],
        )


def test_diagnosis_preview_expires_and_cannot_be_replayed(tmp_path: Path):
    inquiries, inquiry_id = _confirmed_inquiry(tmp_path / "support.sqlite3")
    monotonic = [100.0]
    service = SupportService(
        SqliteSupportRepository(tmp_path / "support.sqlite3", now=NOW),
        inquiries=inquiries,
        now=NOW,
        monotonic=lambda: monotonic[0],
    )
    expired = service.diagnose(account_id=ACCOUNT, subject_id=inquiry_id, issue_text="師傅還沒來")
    monotonic[0] = 401.0
    with pytest.raises(SupportError, match="診斷預覽已失效"):
        service.create_ticket(
            account_id=ACCOUNT, subject_id=inquiry_id, issue_text="師傅還沒來",
            diagnosis_token=expired["diagnosisToken"],
        )

    valid = service.diagnose(account_id=ACCOUNT, subject_id=inquiry_id, issue_text="師傅還沒來")
    service.create_ticket(
        account_id=ACCOUNT, subject_id=inquiry_id, issue_text="師傅還沒來",
        diagnosis_token=valid["diagnosisToken"],
    )
    with pytest.raises(SupportError, match="診斷預覽已失效"):
        service.create_ticket(
            account_id=ACCOUNT, subject_id=inquiry_id, issue_text="師傅還沒來",
            diagnosis_token=valid["diagnosisToken"],
        )


def test_complete_registry_has_36_tools_and_role_scopes_support_operations(tmp_path: Path):
    db = tmp_path / "complete.sqlite3"
    inquiries = SqliteInquiryRepository(db, now=NOW)
    registry = build_registry(
        services=LifeServicesService(inquiries, orders=SqliteOrderRepository(db), today=date(2026, 7, 28)),
        group_buys=SqliteGroupBuyRepository(db),
        personalization=PersonalizationService(SqlitePersonalizationRepository(db), today=date(2026, 7, 28)),
        retail=RetailService(SqliteRetailRepository(db)),
        support=SupportService(
            SqliteSupportRepository(db, now=NOW),
            inquiries=inquiries,
            orders=SqliteOrderRepository(db),
            now=NOW,
        ),
        today=date(2026, 7, 28),
    )

    assert len(registry.list()) == 36
    resident_tools = {tool.name for tool in registry.list(role="user")}
    manager_tools = {tool.name for tool in registry.list(role="manager")}
    assert {"diagnose_order_issue", "create_support_ticket", "list_my_support_tickets"} <= resident_tools
    assert not {"list_support_queue", "start_support_ticket", "resolve_support_ticket"} & resident_tools
    assert {"list_support_queue", "start_support_ticket", "resolve_support_ticket"} <= manager_tools
