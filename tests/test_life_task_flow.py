"""Hero：一句跨服務目標 → 補條件 → 一次確認 → 廠商履約回流。"""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import SqliteInquiryRepository
from core.life_tasks import LifeTaskService, SqliteLifeTaskRepository
from core.vendors import MockVendorClient, VendorService
from fake_upstreams.vendor_app import create_fake_vendor_app
from tests.auth import MEMBER_HEADERS

ACCOUNT = "019a52d3-7f6b-7da3-b48d-9c9e2522d616"
HERO = "爸媽週六要來，浴室燈壞了、冷氣也很久沒洗，幫我安排一下，OPENPOINT 能省就省。"
CONTROL_KEY = "life-task-test"
NOW = lambda: datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc)  # noqa: E731


def _stack(tmp_path):
    upstream = TestClient(create_fake_vendor_app(control_key=CONTROL_KEY))
    adapter = MockVendorClient(base_url="http://vendor-fake", client=upstream)
    tasks = LifeTaskService(
        SqliteLifeTaskRepository(tmp_path / "tasks.sqlite3", now=NOW),
        vendors=VendorService(adapter), today=date(2026, 7, 25),
    )
    return upstream, adapter, tasks


def _configured(tasks: LifeTaskService):
    draft = tasks.create_draft(message=HERO, account_id=ACCOUNT, display_name="小圓")
    return tasks.configure(
        draft["id"], account_id=ACCOUNT, expected_version=draft["version"],
        scheduled_date="2026-08-01", address_choice="home", scope="personal",
    )


def test_hero_is_stably_split_and_only_asks_for_missing_conditions(tmp_path):
    _, _, tasks = _stack(tmp_path)
    draft = tasks.create_draft(message=HERO, account_id=ACCOUNT, display_name="小圓")

    assert [item["serviceId"] for item in draft["items"]] == ["service-repair", "service-aircon"]
    assert draft["scheduledDate"] == "2026-08-01"
    assert draft["missingFields"] == ["address", "scope"]
    assert [item["id"] for item in draft["requirements"]] == ["scheduledDate", "address", "scope"]
    assert draft["readyForConfirmation"] is False


def test_configuration_compares_vendors_and_uses_deterministic_points(tmp_path):
    _, _, tasks = _stack(tmp_path)
    ready = _configured(tasks)

    assert ready["status"] == "ready"
    assert ready["readyForConfirmation"] is True
    assert ready["address"]["dataSource"] == "competition_seed_profile"
    assert ready["items"][0]["vendorName"] == "王子水電"
    assert ready["items"][1]["vendorName"] == "DUSKIN 樂清"
    assert len(ready["items"][0]["candidates"]) == 2
    assert ready["estimate"] == {
        "baseAmount": 3100,
        "pointsApplied": 180,
        "finalAmount": 2920,
        "savedAmount": 180,
        "source": "deterministic_rules+competition_seed_wallet",
    }
    assert ready["points"]["rule"].startswith("競賽情境")


def test_one_confirmation_creates_two_idempotent_vendor_inquiries(tmp_path):
    upstream, _, tasks = _stack(tmp_path)
    ready = _configured(tasks)
    before = upstream.get("/__fake__/state", headers={"X-Fake-Control-Key": CONTROL_KEY}).json()["data"]
    assert before["counts"]["inquiries"] == 120

    submitted = tasks.confirm(ready["id"], account_id=ACCOUNT, expected_version=ready["version"])

    assert submitted["status"] == "submitted"
    assert all(item["externalInquiryId"] for item in submitted["items"])
    after = upstream.get("/__fake__/state", headers={"X-Fake-Control-Key": CONTROL_KEY}).json()["data"]
    assert after["counts"]["inquiries"] == 122
    references = [item["vendorInquiry"]["externalReference"] for item in submitted["items"]]
    assert all(reference.startswith(f"{ready['id']}:") for reference in references)


def test_upstream_failure_is_visible_and_safe_to_retry(tmp_path):
    upstream, _, tasks = _stack(tmp_path)
    ready = _configured(tasks)
    upstream.put("/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY}, json={
        "method": "POST", "path": "/v1/inquiries", "status": 503, "detail": "廠商接案服務維護中",
    })

    with pytest.raises(Exception, match="可安全重試"):
        tasks.confirm(ready["id"], account_id=ACCOUNT, expected_version=ready["version"])

    failed = tasks.get(ready["id"], account_id=ACCOUNT, synchronize=False)
    assert failed["status"] == "partial_failure"
    assert "廠商接案服務維護中" in failed["lastError"]
    recovered = tasks.confirm(failed["id"], account_id=ACCOUNT, expected_version=failed["version"])
    assert recovered["status"] == "submitted"
    assert all(item["externalInquiryId"] for item in recovered["items"])


def test_quotes_orders_and_completion_flow_back_under_the_same_task(tmp_path):
    _, adapter, tasks = _stack(tmp_path)
    ready = _configured(tasks)
    submitted = tasks.confirm(ready["id"], account_id=ACCOUNT, expected_version=ready["version"])

    for index, item in enumerate(submitted["items"]):
        adapter.create_quote(item["externalInquiryId"], {
            "vendorId": item["vendorId"], "validUntil": "2026-08-05",
            "items": [{"name": item["title"], "quantity": 1, "unitPrice": item["basePrice"]}],
        }, idempotency_key=f"vendor-quote-{index}")
    quoted = tasks.get(ready["id"], account_id=ACCOUNT)
    assert quoted["status"] == "quoted"
    assert all(len(item["quotes"]) == 1 for item in quoted["items"])

    ordered = tasks.accept_quotes(
        ready["id"], account_id=ACCOUNT, expected_version=quoted["version"],
    )
    assert ordered["status"] == "ordered"
    assert all(item["externalOrderId"] for item in ordered["items"])

    for index, item in enumerate(ordered["items"]):
        adapter.append_order_event(item["externalOrderId"], {
            "type": "completed", "status": "completed", "note": "服務完成",
        }, idempotency_key=f"vendor-complete-{index}")
    completed = tasks.get(ready["id"], account_id=ACCOUNT)
    assert completed["status"] == "completed"
    assert all(item["vendorOrder"]["status"] == "completed" for item in completed["items"])


class BrokenLlm:
    def json(self, messages):
        raise RuntimeError("not needed")


def test_platform_routes_try_hero_without_stealing_single_service_requests(tmp_path):
    upstream = TestClient(create_fake_vendor_app(control_key=CONTROL_KEY))
    adapter = MockVendorClient(base_url="http://vendor-fake", client=upstream)
    db = tmp_path / "platform.sqlite3"
    platform = TestClient(create_app(
        repository=SqliteInquiryRepository(db, now=NOW),
        life_task_repository=SqliteLifeTaskRepository(db, now=NOW),
        vendor_client=adapter, llm_factory=BrokenLlm,
    ))
    headers = MEMBER_HEADERS

    draft = platform.post("/api/v1/life-tasks/draft", headers=headers, json={"message": HERO})
    assert draft.status_code == 200
    assert draft.json()["data"]["displayName"] == "小圓"
    assert platform.post(
        "/api/v1/life-tasks/draft", headers=headers, json={"message": "想找人來打掃"},
    ).status_code == 422
    assert platform.get("/api/v1/life-tasks", headers=headers).json()["data"][0]["id"] == draft.json()["data"]["id"]
    assert platform.get("/api/v1/life-tasks").status_code == 401
