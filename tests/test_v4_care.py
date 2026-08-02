from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.proactive_care import CareError, ProactiveCareService
from fastapi.testclient import TestClient

from api.app import create_app


OWNER = {
    "demo_workspace_id": "demo-default",
    "workspace_id": "workspace-personal-demo-member",
    "account_id": "demo-member",
}


def test_care_separates_candidate_delivery_and_keeps_demo_event_explicit(tmp_path) -> None:
    service = ProactiveCareService(
        tmp_path / "care.sqlite3",
        now=lambda: datetime(2026, 8, 1, tzinfo=timezone.utc),
    )

    candidates = service.generate_candidates(**OWNER)
    assert candidates[0]["status"] == "candidate"
    assert candidates[0]["evidence"]["isDemo"] is True
    assert candidates[0]["evidence"]["noBackgroundTracking"] is True
    assert service.list_messages(**OWNER) == []  # read does not implicitly deliver
    service.deliver(**OWNER)
    message = service.list_messages(**OWNER)[0]
    assert message["state"] == "delivered"
    assert message["candidate"]["evidence"]["guideStatus"] == "published_internal_demo"


def test_care_actions_are_allowlisted_idempotent_and_owner_scoped(tmp_path) -> None:
    service = ProactiveCareService(tmp_path / "care.sqlite3")
    message = service.deliver(**OWNER)[0]

    snoozed = service.act(message["id"], **OWNER, action="snooze")
    assert snoozed["state"] == "snoozed"
    replay = service.act(message["id"], **OWNER, action="snooze")
    assert replay["idempotentReplay"] is False  # a repeated snooze is a safe state write

    with pytest.raises(CareError, match="照護訊息"):
        service.act(message["id"], **{**OWNER, "account_id": "demo-member-chen"}, action="close")

    opened = service.act(message["id"], **OWNER, action="open_guide")
    assert opened["guide"]["status"] == "published"
    assert opened["guide"]["preparationItems"][0]["necessity"] == "common-required"
    assert opened["guide"]["pointsEstimate"]["min"] == 20


def test_care_rejects_unknown_actions(tmp_path) -> None:
    service = ProactiveCareService(tmp_path / "care.sqlite3")
    message = service.deliver(**OWNER)[0]
    with pytest.raises(CareError, match="允許清單"):
        service.act(message["id"], **OWNER, action="send_push")  # type: ignore[arg-type]


def test_care_api_is_member_scoped_and_returns_the_internal_demo_guide(tmp_path) -> None:
    client = TestClient(create_app(demo_db_path=tmp_path / "api.sqlite3"))
    headers = {"Authorization": "Bearer aiwave"}
    response = client.get("/api/v1/platform/care/messages", headers=headers)
    assert response.status_code == 200
    message = response.json()["data"][0]
    assert message["candidate"]["evidence"]["isDemo"] is True

    opened = client.post(
        f"/api/v1/platform/care/messages/{message['id']}/actions",
        headers=headers,
        json={"action": "open_guide"},
    )
    assert opened.status_code == 200
    assert opened.json()["data"]["guide"]["status"] == "published"
    assert opened.json()["data"]["guide"]["commercialBoundary"].startswith("只整理類別")

    other = client.get(
        "/api/v1/platform/care/messages",
        headers={"Authorization": "Bearer aiwave-chen"},
    )
    assert other.status_code == 200
    assert other.json()["data"][0]["id"] != message["id"]
