from __future__ import annotations

import pytest

from core.task_packages import TaskPackageConflict, SqliteTaskPackageService


OWNER = {
    "demo_workspace_id": "demo-default",
    "workspace_id": "workspace-personal-demo-member",
    "account_id": "demo-member",
}


def _subtasks() -> list[dict]:
    option_a = {
        "id": "option-a", "providerId": "provider-a", "providerName": "A 家",
        "offeringId": "offering-clean", "offeringName": "到府清潔", "basePrice": 1200,
        "quote": {"payable": 1200, "points": 0},
        "slot": {"id": "slot-a", "startsAt": "2026-08-08T13:00:00+08:00", "endsAt": "2026-08-08T15:00:00+08:00"},
    }
    option_b = {
        "id": "option-b", "providerId": "provider-b", "providerName": "B 家",
        "offeringId": "offering-clean", "offeringName": "到府清潔", "basePrice": 1400,
        "quote": {"payable": 1400, "points": 0},
        "slot": {"id": "slot-b", "startsAt": "2026-08-09T13:00:00+08:00", "endsAt": "2026-08-09T15:00:00+08:00"},
    }
    return [{
        "id": "subtask-1", "status": "ready", "draftId": "draft-1", "domain": "home_cleaning",
        "goal": "安排清潔", "selected": option_a, "quote": option_a["quote"],
        "proposals": [option_a, option_b],
    }]


def test_package_has_stable_refs_and_authoritative_totals(tmp_path) -> None:
    service = SqliteTaskPackageService(tmp_path / "package.sqlite3")
    package = service.create_from_subtasks(
        owner=OWNER, source_type="agent_session", source_id="session-1", subtasks=_subtasks(),
        beneficiary={"label": "爸媽"}, service_location={"locationId": "home"}, grant_id="grant-1",
    )

    assert package["status"] == "awaiting_confirmation"
    assert package["taskDraftRefs"] == ["draft-1"]
    assert package["totalAmount"] == 1200
    assert package["items"][0]["details"]["proposalOptions"][1]["providerId"] == "provider-b"
    replay = service.create_from_subtasks(
        owner=OWNER, source_type="agent_session", source_id="session-1", subtasks=_subtasks(),
    )
    assert replay["id"] == package["id"]


def test_package_patch_uses_occ_and_only_selects_catalog_options(tmp_path) -> None:
    service = SqliteTaskPackageService(tmp_path / "package.sqlite3")
    package = service.create_from_subtasks(
        owner=OWNER, source_type="agent_session", source_id="session-1", subtasks=_subtasks(),
    )
    item_id = package["items"][0]["id"]

    replaced = service.patch_item(
        package["id"], item_id, owner=OWNER, expected_version=package["version"],
        operation="replace_provider", changes={"providerId": "provider-b"},
    )
    assert replaced["totalAmount"] == 1400
    assert replaced["items"][0]["providerId"] == "provider-b"

    with pytest.raises(TaskPackageConflict, match="版本"):
        service.patch_item(
            package["id"], item_id, owner=OWNER, expected_version=package["version"],
            operation="pause",
        )
    with pytest.raises(ValueError, match="Catalog"):
        service.patch_item(
            package["id"], item_id, owner=OWNER, expected_version=replaced["version"],
            operation="replace_provider", changes={"providerId": "untrusted-provider"},
        )


def test_package_preserves_success_on_cross_provider_partial_failure_and_is_idempotent(tmp_path) -> None:
    service = SqliteTaskPackageService(tmp_path / "package.sqlite3")
    subtasks = _subtasks() + [{
        **_subtasks()[0], "id": "subtask-2", "draftId": "draft-2", "selected": {
            **_subtasks()[0]["selected"], "id": "option-c", "providerId": "provider-c", "providerName": "C 家",
        },
    }]
    package = service.create_from_subtasks(
        owner=OWNER, source_type="agent_session", source_id="session-1", subtasks=subtasks,
    )
    first, second = [item["id"] for item in package["items"]]
    service.mark_item_executing(package["id"], first, owner=OWNER)
    service.record_item_result(
        package["id"], first, owner=OWNER, status="succeeded", event_key="event-1",
    )
    failed = service.record_item_result(
        package["id"], second, owner=OWNER, status="failed", event_key="event-2", error="provider timeout",
    )
    assert failed["status"] == "partial_failure"
    assert failed["items"][0]["status"] == "succeeded"
    assert failed["items"][1]["lastError"] == "provider timeout"
    replay = service.record_item_result(
        package["id"], second, owner=OWNER, status="failed", event_key="event-2", error="different text",
    )
    assert replay["idempotentReplay"] is True
    assert replay["items"][1]["lastError"] == "provider timeout"
