"""社區聯合服務 Hero：需求聚合 → 方案決策 → 廠商履約。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.community import (
    ASSIGNED,
    COMPLETED,
    IN_PROGRESS,
    PROPOSAL_REVIEW,
    JointServiceError,
    SqliteGroupBuyRepository,
    SqliteJointServiceRepository,
)
from core.inquiries import SqliteInquiryRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext, ToolError

NOW = lambda: datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)  # noqa: E731


@pytest.fixture
def repository(tmp_path: Path) -> SqliteJointServiceRepository:
    return SqliteJointServiceRepository(tmp_path / "joint.sqlite3", now=NOW)


def test_seed_is_evidence_backed_and_comparable(repository: SqliteJointServiceRepository):
    campaign = repository.list_campaigns()[0]

    assert campaign["status"] == PROPOSAL_REVIEW
    assert campaign["demand"]["householdCount"] == 18
    assert campaign["demand"]["unitCount"] == 27
    assert campaign["demand"]["privacy"].startswith("以匿名住戶雜湊")
    assert len(campaign["proposals"]) == 2
    assert all(sum(item["amount"] for item in proposal["items"]) == proposal["total"]
               for proposal in campaign["proposals"])
    assert all(proposal["source"] == "competition_seed" for proposal in campaign["proposals"])
    assert "非品牌即時報價" in campaign["dataNotice"]


def test_assignment_and_fulfilment_share_one_persistent_timeline(repository: SqliteJointServiceRepository):
    campaign = repository.list_campaigns()[0]
    assigned = repository.assign(campaign["id"], proposal_id="proposal-care", actor="社區管理者")
    assert assigned["status"] == ASSIGNED
    assert assigned["selectedProposal"]["vendorId"] == "vendor-duskin"

    started = repository.start(campaign["id"], vendor_id="vendor-duskin", actor="合作廠商")
    assert started["status"] == IN_PROGRESS
    completed = repository.complete(campaign["id"], vendor_id="vendor-duskin", actor="合作廠商", note="27 台已完成，3 台外機另附檢查紀錄")
    assert completed["status"] == COMPLETED
    assert [event["type"] for event in completed["events"]][-3:] == [
        "joint_service.assigned", "joint_service.started", "joint_service.completed",
    ]
    assert repository.get_campaign(campaign["id"])["status"] == COMPLETED


def test_state_machine_rejects_skips_and_second_assignment(repository: SqliteJointServiceRepository):
    campaign = repository.list_campaigns()[0]
    with pytest.raises(JointServiceError):
        repository.start(campaign["id"], vendor_id="vendor-duskin", actor="合作廠商")
    repository.assign(campaign["id"], proposal_id="proposal-care", actor="社區管理者")
    with pytest.raises(JointServiceError):
        repository.assign(campaign["id"], proposal_id="proposal-value", actor="社區管理者")


def test_new_campaign_collects_anonymous_deduplicated_demand_before_proposals(repository: SqliteJointServiceRepository):
    draft = repository.create_draft(title="九月冷氣聯合清洗", service_id="service-aircon")
    repository.publish(draft["id"], actor="社區管理者")
    repository.join(draft["id"], account_id="resident-a", units=2, equipment="分離式冷氣", preferred_slot="週六上午")
    updated = repository.join(draft["id"], account_id="resident-a", units=3, equipment="分離式冷氣", preferred_slot="週六上午")
    assert updated["demand"]["householdCount"] == 1
    assert updated["demand"]["unitCount"] == 3
    ready = repository.prepare_proposals(draft["id"], actor="社區管理者")
    assert ready["status"] == PROPOSAL_REVIEW
    assert ready["proposals"][0]["items"][0]["name"] == "冷氣清洗 3 台"


class UnusedLlm:
    def chat(self, *args, **kwargs):
        raise AssertionError("joint service endpoints must not call LLM")

    def json(self, *args, **kwargs):
        raise AssertionError("joint service endpoints must not call LLM")


@pytest.fixture
def client(tmp_path: Path, repository: SqliteJointServiceRepository) -> TestClient:
    return TestClient(create_app(
        repository=SqliteInquiryRepository(tmp_path / "inquiries.sqlite3"),
        group_buys=SqliteGroupBuyRepository(tmp_path / "groups.sqlite3"),
        joint_services=repository,
        llm_factory=UnusedLlm,
    ))


def test_http_roles_and_cross_role_state(client: TestClient):
    manager = {"X-Role": "manager"}
    partner = {"X-Role": "partner", "X-Account-Id": "vendor-duskin"}
    resident = {"X-Role": "user", "X-Account-Id": "A001"}
    campaign = client.get("/api/v1/community/joint-services", headers=manager).json()["data"][0]

    denied = client.post(
        f"/api/v1/community/joint-services/{campaign['id']}/assign",
        headers=resident, json={"proposal_id": "proposal-care"},
    )
    assert denied.status_code == 403

    assigned = client.post(
        f"/api/v1/community/joint-services/{campaign['id']}/assign",
        headers=manager, json={"proposal_id": "proposal-care"},
    )
    assert assigned.status_code == 200
    workload = client.get("/api/v1/vendor/joint-services", headers=partner).json()["data"]
    assert [item["id"] for item in workload] == [campaign["id"]]

    started = client.post(
        f"/api/v1/vendor/joint-services/{campaign['id']}/start", headers=partner,
    )
    assert started.json()["data"]["status"] == IN_PROGRESS
    manager_view = client.get("/api/v1/community/joint-services", headers=manager).json()["data"][0]
    assert manager_view["status"] == IN_PROGRESS


def test_resident_explicitly_consents_and_only_sees_own_signal(client: TestClient):
    resident = {"X-Role": "user", "X-Account-Id": "A001"}
    campaigns = client.get("/api/v1/groups/joint-services", headers=resident).json()["data"]
    collecting = next(item for item in campaigns if item["status"] == "collecting")
    assert collecting["myParticipation"] is None

    rejected = client.post(
        f"/api/v1/community/joint-services/{collecting['id']}/join", headers=resident,
        json={"units": 2, "equipment": "分離式冷氣", "preferred_slot": "週六上午", "consent": False},
    )
    assert rejected.status_code == 422

    joined = client.post(
        f"/api/v1/community/joint-services/{collecting['id']}/join", headers=resident,
        json={"units": 2, "equipment": "分離式冷氣", "preferred_slot": "週六上午", "consent": True},
    )
    assert joined.status_code == 200
    mine = client.get("/api/v1/groups/joint-services", headers=resident).json()["data"]
    participation = next(item for item in mine if item["id"] == collecting["id"])["myParticipation"]
    assert participation["units"] == 2
    assert participation["consentVersion"] == "joint-demand-v1"
    assert "household_hash" not in str(mine)


def test_tools_enforce_roles_and_expose_same_record(tmp_path: Path, repository: SqliteJointServiceRepository):
    inquiries = SqliteInquiryRepository(tmp_path / "tool-inquiries.sqlite3")
    registry = build_registry(
        services=LifeServicesService(inquiries),
        group_buys=SqliteGroupBuyRepository(tmp_path / "tool-groups.sqlite3"),
        joint_services=repository,
        today=datetime(2026, 7, 28).date(),
    )
    manager = ToolContext(role="manager", display_name="社區管理者")
    partner = ToolContext(account_id="vendor-duskin", role="partner", display_name="合作廠商")
    resident = ToolContext(account_id="A001", role="user", display_name="住戶")
    campaign_id = repository.list_campaigns()[0]["id"]
    campaign = registry.call("get_joint_service_summary", {"campaign_id": campaign_id}, manager)

    with pytest.raises(ToolError):
        registry.call("assign_joint_service_vendor", {"campaign_id": campaign["id"], "proposal_id": "proposal-care"}, resident)
    registry.call("assign_joint_service_vendor", {"campaign_id": campaign["id"], "proposal_id": "proposal-care"}, manager)
    assert registry.call("list_assigned_joint_services", {}, partner)[0]["id"] == campaign["id"]

    for tool in registry.list():
        if tool.name in {"get_joint_service_summary", "assign_joint_service_vendor", "list_assigned_joint_services",
                         "start_joint_service", "complete_joint_service"}:
            assert not set(tool.parameters.get("properties", {})) & {"account_id", "role"}
