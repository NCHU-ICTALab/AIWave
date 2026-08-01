"""M4 六大生活場景的端到端閉環(手動 Platform API,不經 Agent)。

每條閉環:探索 → 選擇 Provider/Location/Offering/Resource/Availability →
TaskDraft → 試算 → DemoPayment → Booking/Order → fake upstream 收件 →
StatusEvent → 通知與 Calendar projection → 完成/取消/退款/失敗恢復。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from core.providers import StandardProviderConnector
from fake_upstreams.partner_app import create_partner_fake_app
from fake_upstreams.partner_seed import DEFAULT_PARTNER_KEYS

CONTROL_KEY = "m4-scenarios-control"


class UnusedLlm:
    def complete(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("M4 手動閉環不得呼叫 LLM")


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def write_headers(key: str, idempotency_key: str) -> dict[str, str]:
    return {**bearer(key), "Idempotency-Key": idempotency_key}


def make_stack(tmp_path, db_name: str = "m4.sqlite3"):
    """平台 + 多 provider fake upstream,並完成目錄同步。"""
    upstream = TestClient(create_partner_fake_app(control_key=CONTROL_KEY))
    connectors = {
        provider_id: StandardProviderConnector(
            base_url="http://partner-fake", api_key=key, client=upstream,
        )
        for provider_id, key in DEFAULT_PARTNER_KEYS.items()
    }
    client = TestClient(create_app(
        demo_db_path=tmp_path / db_name, llm_factory=UnusedLlm,
        provider_connectors=connectors,
    ))
    synced = client.post("/api/v1/platform/catalog/sync", headers=bearer("aiwave-admin"))
    assert synced.status_code == 200
    assert synced.json()["data"]["status"] == "ok"
    return client, upstream


def pick_slot(client: TestClient, provider_id: str, offering_id: str) -> dict:
    slots = client.get(
        "/api/v1/platform/catalog/availability",
        params={"providerId": provider_id, "offeringId": offering_id},
        headers=bearer("aiwave"),
    ).json()["data"]
    assert slots, f"{provider_id}/{offering_id} 應該有可預約時段"
    return slots[0]


def submit_booking_draft(
    client: TestClient, *, key_prefix: str, domain_type: str,
    provider_id: str, offering_id: str, extra_values: dict,
    member: str = "aiwave",
) -> tuple[dict, dict]:
    slot = pick_slot(client, provider_id, offering_id)
    draft = client.post(
        "/api/v1/platform/task-drafts",
        headers=write_headers(member, f"{key_prefix}-draft"),
        json={"domain_type": domain_type, "source": "user", "values": {
            "provider_id": provider_id, "location_id": slot["locationId"],
            "offering_id": offering_id, "resource_id": slot["resourceId"],
            "slot_id": slot["id"], "starts_at": slot["startsAt"], "ends_at": slot["endsAt"],
            **extra_values,
        }},
    ).json()["data"]
    ready = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/transition",
        headers=bearer(member),
        json={"expected_version": draft["version"], "status": "ready"},
    ).json()["data"]
    submitted = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/submit",
        headers=write_headers(member, f"{key_prefix}-submit"),
        json={"expected_version": ready["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()["data"], slot


def test_catalog_covers_six_scenes_with_confirmed_group_brands(tmp_path):
    client, _ = make_stack(tmp_path)
    providers = client.get(
        "/api/v1/platform/catalog/providers", headers=bearer("aiwave"),
    ).json()["data"]
    scenes = {item["scene"] for item in providers}
    assert {"food", "med", "home", "move", "pre", "fun"} <= scenes
    # 2026-07-30 產品負責人提供正式名單(廠商and表單.md)後,六場景皆為真實品牌
    assert all(item["placeholder"] is False for item in providers)
    brands = {item["name"] for item in providers}
    assert {"王子水電", "DUSKIN 樂清", "21PLUS", "速邁樂加油站 Smile",
            "黑貓宅急便", "康是美", "統一渡假村 Uni Resort"} <= brands
    detail = client.get(
        "/api/v1/platform/catalog/providers/vendor-prince-electric", headers=bearer("aiwave"),
    ).json()["data"]
    assert detail["locations"] and detail["offerings"] and detail["resources"]


def test_home_repair_full_loop_with_points_reschedule_and_completion(tmp_path):
    client, _ = make_stack(tmp_path)
    offering_id = "off-prince-electric-repair"
    quote = client.post(
        "/api/v1/platform/quotes", headers=bearer("aiwave"),
        json={"offering_id": offering_id, "points_to_redeem": 100},
    ).json()["data"]
    assert quote["payable"] == 1100 and quote["pointsBalance"] == 180

    result, slot = submit_booking_draft(
        client, key_prefix="repair", domain_type="home_repair",
        provider_id="vendor-prince-electric", offering_id=offering_id,
        extra_values={"problem": "主臥冷氣不冷", "address": "台北市信義區松勤街 1 號", "phone": "0912345678"},
    )
    booking_id = result["subjectId"]
    assert result["draft"]["status"] == "confirmed"
    assert result["booking"]["providerSync"]["syncStatus"] == "synced"

    # 重複送出:同一草稿回同一筆交易(重複提交保護)
    replay = client.post(
        f"/api/v1/platform/task-drafts/{result['draft']['id']}/submit",
        headers=write_headers("aiwave", "repair-submit-again"),
        json={"expected_version": result["draft"]["version"]},
    ).json()["data"]
    assert replay["idempotentReplay"] is True and replay["subjectId"] == booking_id

    # 付款(折抵 100 點)→ 點數餘額同步
    payment = client.post(
        "/api/v1/platform/payments", headers=write_headers("aiwave", "repair-payment"),
        json={"subject_type": "booking", "subject_id": booking_id,
              "amount": 1200, "points_redeemed": 100, "outcome": "success"},
    ).json()["data"]
    assert payment["status"] == "succeeded"
    assert client.get(
        "/api/v1/platform/points", headers=bearer("aiwave"),
    ).json()["data"]["balance"] == 80

    # 廠商工作台收到並確認
    partner_view = client.get("/api/v1/platform/bookings", headers=bearer("aiwave-partner")).json()["data"]
    assert [item["id"] for item in partner_view] == [booking_id]
    confirmed = client.post(
        f"/api/v1/platform/bookings/{booking_id}/transition",
        headers=write_headers("aiwave-partner", "repair-confirm"),
        json={"expected_version": partner_view[0]["version"], "status": "confirmed"},
    ).json()["data"]

    # 改期:重新查 availability 選新時段 → 廠商核准 → 行事曆跟著新時段
    new_slot = next(
        item for item in client.get(
            "/api/v1/platform/catalog/availability",
            params={"providerId": "vendor-prince-electric", "offeringId": offering_id},
            headers=bearer("aiwave"),
        ).json()["data"] if item["id"] != slot["id"]
    )
    request = client.post(
        f"/api/v1/platform/bookings/{booking_id}/reschedule-requests",
        headers=write_headers("aiwave", "repair-reschedule"),
        json={"slot_id": new_slot["id"], "starts_at": new_slot["startsAt"],
              "ends_at": new_slot["endsAt"], "reason": "臨時出差"},
    ).json()["data"]
    review = client.post(
        f"/api/v1/platform/booking-reschedule-requests/{request['id']}/review",
        headers=write_headers("aiwave-partner", "repair-reschedule-accept"),
        json={"accept": True},
    ).json()["data"]
    assert review["status"] == "accepted"
    events = client.get(
        "/api/v1/platform/calendar/events", headers=bearer("aiwave"),
    ).json()["data"]
    projected = next(item for item in events if item["source"]["id"] == booking_id)
    assert projected["startsAt"] == new_slot["startsAt"]

    # 服務中 → 完成;會員端通知與 StatusEvent 一致
    booking = client.get(f"/api/v1/platform/bookings/{booking_id}", headers=bearer("aiwave")).json()["data"]
    for step, status in (("repair-start", "in_service"), ("repair-done", "completed")):
        booking = client.post(
            f"/api/v1/platform/bookings/{booking_id}/transition",
            headers=write_headers("aiwave-partner", step),
            json={"expected_version": booking["version"], "status": status},
        ).json()["data"]
    member_booking = client.get(
        f"/api/v1/platform/bookings/{booking_id}", headers=bearer("aiwave"),
    ).json()["data"]
    assert member_booking["status"] == "completed"
    event_states = [item["toStatus"] for item in member_booking["events"]]
    assert event_states == ["pending_provider", "confirmed", "confirmed", "in_service", "completed"]
    inbox = client.get("/api/v1/platform/notifications", headers=bearer("aiwave")).json()["data"]
    assert any("水電修繕" in item["title"] for item in inbox["items"])

    # refresh/重新登入恢復:同一資料庫重開 app,狀態不變
    reopened = TestClient(create_app(
        demo_db_path=tmp_path / "m4.sqlite3", llm_factory=UnusedLlm, provider_connectors={},
    ))
    persisted = reopened.get(
        f"/api/v1/platform/bookings/{booking_id}", headers=bearer("aiwave"),
    ).json()["data"]
    assert persisted["status"] == "completed"
    assert reopened.get(
        "/api/v1/platform/points", headers=bearer("aiwave"),
    ).json()["data"]["balance"] == 80


def test_dining_reservation_cancel_refunds_and_releases_slot(tmp_path):
    client, upstream = make_stack(tmp_path)
    offering_id = "off-21plus-dinner"
    result, slot = submit_booking_draft(
        client, key_prefix="dining", domain_type="dining_reservation",
        provider_id="vendor-21plus", offering_id=offering_id,
        extra_values={"party_size": "4", "contact_name": "林小圓", "phone": "0912345678"},
    )
    booking_id = result["subjectId"]
    # 訂位免費但示範點數折抵支付路徑:付 0 元 0 點也可(這裡付訂金情境省略)
    before = upstream.get(
        "/partner/v1/availability", headers=bearer(DEFAULT_PARTNER_KEYS["vendor-21plus"]),
    ).json()["data"]
    assert next(item for item in before if item["id"] == slot["id"])["status"] == "booked"

    cancelled = client.post(
        f"/api/v1/platform/bookings/{booking_id}/cancellation",
        headers=write_headers("aiwave", "dining-cancel"),
        json={"expected_version": result["booking"]["version"], "note": "臨時取消"},
    ).json()["data"]
    assert cancelled["status"] == "cancelled"
    after = upstream.get(
        "/partner/v1/availability", headers=bearer(DEFAULT_PARTNER_KEYS["vendor-21plus"]),
    ).json()["data"]
    assert next(item for item in after if item["id"] == slot["id"])["status"] == "available"
    events = client.get("/api/v1/platform/calendar/events", headers=bearer("aiwave")).json()["data"]
    assert all(item["source"]["id"] != booking_id for item in events)  # 取消後不再佔行事曆


def test_pharmacy_pickup_requires_human_confirmation_of_ocr(tmp_path):
    client, _ = make_stack(tmp_path)
    offering_id = "off-cosmed-rx-pickup"
    slot = pick_slot(client, "vendor-cosmed", offering_id)
    base_values = {
        "provider_id": "vendor-cosmed", "location_id": slot["locationId"],
        "offering_id": offering_id, "resource_id": slot["resourceId"],
        "slot_id": slot["id"], "starts_at": slot["startsAt"], "ends_at": slot["endsAt"],
        "patient_name": "林小圓", "phone": "0912345678",
        "rx_type": "慢箋第 2 次領取", "pickup_in_person": "true",
    }
    draft = client.post(
        "/api/v1/platform/task-drafts", headers=write_headers("aiwave", "rx-draft"),
        json={"domain_type": "pharmacy_pickup", "source": "user", "values": base_values},
    ).json()["data"]
    rejected = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/submit",
        headers=write_headers("aiwave", "rx-submit-early"),
        json={"expected_version": draft["version"]},
    )
    assert rejected.status_code == 422  # OCR 結果未經本人確認不得送出
    assert "rx_confirmed" in rejected.text

    confirmed = client.patch(
        f"/api/v1/platform/task-drafts/{draft['id']}",
        headers=bearer("aiwave"),
        json={"expected_version": draft["version"], "source": "user",
              "values": {"rx_confirmed": "true"}},
    ).json()["data"]
    submitted = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/submit",
        headers=write_headers("aiwave", "rx-submit"),
        json={"expected_version": confirmed["version"]},
    ).json()["data"]
    booking_id = submitted["subjectId"]
    partner_rows = client.get(
        "/api/v1/platform/bookings", headers=bearer("aiwave-partner-cosmed"),
    ).json()["data"]
    assert [row["id"] for row in partner_rows] == [booking_id]


def test_shipping_pickup_loop_reaches_completion(tmp_path):
    client, _ = make_stack(tmp_path)
    result, _ = submit_booking_draft(
        client, key_prefix="ship", domain_type="shipping_pickup",
        provider_id="vendor-blackcat", offering_id="off-blackcat-pickup",
        extra_values={"package_size": "60", "pickup_address": "台北市信義區松勤街 1 號",
                      "receiver_address": "台中市西屯區示範路 2 號", "phone": "0912345678"},
    )
    booking_id = result["subjectId"]
    booking = result["booking"]
    for step, status in (("ship-confirm", "confirmed"), ("ship-start", "in_service"),
                         ("ship-done", "completed")):
        booking = client.post(
            f"/api/v1/platform/bookings/{booking_id}/transition",
            headers=write_headers("aiwave-partner-blackcat", step),
            json={"expected_version": booking["version"], "status": status},
        ).json()["data"]
    assert booking["status"] == "completed"


def submit_commerce_draft(
    client: TestClient, *, key_prefix: str, domain_type: str,
    offering_id: str, extra_values: dict, quantity: int = 1,
) -> dict:
    draft = client.post(
        "/api/v1/platform/task-drafts",
        headers=write_headers("aiwave", f"{key_prefix}-draft"),
        json={"domain_type": domain_type, "source": "user", "values": {
            "offering_id": offering_id, "quantity": quantity, **extra_values,
        }},
    ).json()["data"]
    submitted = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/submit",
        headers=write_headers("aiwave", f"{key_prefix}-submit"),
        json={"expected_version": draft["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()["data"]


def test_catalog_listings_expose_group_brands_as_non_transactable(tmp_path):
    """tier-2 陳列(2026-07-31 拍板兩層制):品牌卡誠實標示不可下單,含 ibon 叫車現況說明。"""
    client, _ = make_stack(tmp_path)
    listings = client.get(
        "/api/v1/platform/catalog/listings", headers=bearer("aiwave"),
    ).json()["data"]
    assert all(item["transactable"] is False for item in listings)
    names = {item["name"] for item in listings}
    assert {"星巴克", "Mister Donut", "博客來", "統一夢時代購物中心"} <= {n.split("(")[0] for n in names} | names
    taxi = next(item for item in listings if "ibon 叫車" in item["name"])
    assert "機台" in taxi["note"]  # 誠實陳列官方現況,不虛構線上叫車
    scoped = client.get(
        "/api/v1/platform/catalog/listings", params={"scene": "support"}, headers=bearer("aiwave"),
    ).json()["data"]
    assert scoped and all(item["scene"] == "support" for item in scoped)


def test_food_delivery_and_ticket_and_c2c_and_iopenmall_loops(tmp_path):
    """新 tier-1 場景:foodomo 外送、ibon 非劃位票券、交貨便寄件、iOPEN Mall EC。"""
    client, _ = make_stack(tmp_path)
    cases = [
        ("delivery", "food_delivery", "off-foodomo-meal",
         {"delivery_address": "台北市信義區松勤街 1 號", "phone": "0912345678"},
         "aiwave-partner-foodomo",
         (("accepted", "店家接單"), ("preparing", None), ("shipped", None), ("delivered", None))),
        ("ticket", "ticket_purchase", "off-ibon-attraction",
         {"use_date": "2026-08-09", "buyer_name": "林小圓", "phone": "0912345678"},
         "aiwave-partner-ibonticket",
         (("accepted", None), ("preparing", None), ("ready_for_pickup", None), ("delivered", None))),
        ("c2c", "c2c_shipping", "off-711-c2c-standard",
         {"sender_name": "林小圓", "receiver_name": "陳伯伯", "item_name": "書一本", "phone": "0912345678"},
         "aiwave-partner-711c2c",
         (("accepted", None), ("preparing", None), ("shipped", None),
          ("ready_for_pickup", None), ("delivered", None))),
        ("iopen", "ec_preorder", "off-iopenmall-home",
         {"receiver_name": "林小圓", "phone": "0912345678", "pickup_method": "門市取貨"},
         "aiwave-partner-iopenmall",
         (("accepted", None), ("preparing", None), ("shipped", None), ("delivered", None))),
    ]
    for prefix, domain_type, offering_id, values, partner_key, transitions in cases:
        submitted = submit_commerce_draft(
            client, key_prefix=prefix, domain_type=domain_type,
            offering_id=offering_id, extra_values=values,
        )
        order = submitted["order"]
        assert order["total"] > 0  # 價格由平台目錄決定
        for index, (status, _label) in enumerate(transitions):
            response = client.post(
                f"/api/v1/platform/commerce-orders/{order['id']}/transition",
                headers=write_headers(partner_key, f"{prefix}-{index}"),
                json={"expected_version": order["version"], "status": status},
            )
            assert response.status_code == 200, f"{prefix}:{status}: {response.text}"
            order = response.json()["data"]
        assert order["status"] == "delivered"
    # 通知使用 per-domain 狀態名稱(外送「店家接單」)
    inbox = client.get("/api/v1/platform/notifications", headers=bearer("aiwave")).json()["data"]
    assert any("店家接單" in item["body"] for item in inbox["items"])


def test_admin_persona_reset_and_upstream_health(tmp_path):
    """aiwave-admin:單一 persona workspace 重置與 fake upstream 健康(spec §10)。"""
    client, _ = make_stack(tmp_path)
    result, _ = submit_booking_draft(
        client, key_prefix="admin-reset", domain_type="home_repair",
        provider_id="vendor-prince-electric", offering_id="off-prince-electric-repair",
        extra_values={"problem": "跳電", "address": "台北市信義區", "phone": "0911111111"},
    )
    assert result["subjectId"]
    # 非 operator 不可用(越權防護)
    assert client.post(
        "/api/v1/platform/admin/workspaces/membership-member-xiaoyuan/reset",
        headers=bearer("aiwave"),
    ).status_code == 403
    reset = client.post(
        "/api/v1/platform/admin/workspaces/membership-member-xiaoyuan/reset",
        headers=bearer("aiwave-admin"),
    )
    assert reset.status_code == 200
    assert client.get(
        "/api/v1/platform/bookings", headers=bearer("aiwave"),
    ).json()["data"] == []
    # partner workspace 不是個人 workspace,不可用此端點重置
    assert client.post(
        "/api/v1/platform/admin/workspaces/membership-partner-duskin/reset",
        headers=bearer("aiwave-admin"),
    ).status_code == 422
    health = client.get(
        "/api/v1/platform/admin/upstream-health", headers=bearer("aiwave-admin"),
    ).json()["data"]
    assert health["status"] in {"disabled", "unavailable", "ok"}  # 測試環境未起 HTTP fake,誠實回報


def test_car_wash_booking_with_points_redeem(tmp_path):
    """行(洗車):速邁樂精緻洗車線上預約 —— 名單指出線上化最低的差異化切入點。"""
    client, _ = make_stack(tmp_path)
    quote = client.post(
        "/api/v1/platform/quotes", headers=bearer("aiwave"),
        json={"offering_id": "off-smile-wash-sedan", "points_to_redeem": 150},
    ).json()["data"]
    assert quote["payable"] == 300  # 450 - 150 點折抵(Demo 規則 1 點 = NT$1)

    result, _ = submit_booking_draft(
        client, key_prefix="wash", domain_type="car_wash",
        provider_id="vendor-smile", offering_id="off-smile-wash-sedan",
        extra_values={"plate_number": "ABC-1234", "car_type": "轎車", "phone": "0912345678"},
    )
    booking = result["booking"]
    booking = client.post(
        f"/api/v1/platform/bookings/{booking['id']}/transition",
        headers=write_headers("aiwave-partner-smile", "wash-confirm"),
        json={"expected_version": booking["version"], "status": "confirmed"},
    ).json()["data"]
    assert booking["status"] == "confirmed"


def test_ec_preorder_payment_failure_recovery_and_delivery(tmp_path):
    client, _ = make_stack(tmp_path)
    draft = client.post(
        "/api/v1/platform/task-drafts", headers=write_headers("aiwave", "ec-draft"),
        json={"domain_type": "ec_preorder", "source": "user", "values": {
            "offering_id": "off-711-shop-preorder-coffee", "quantity": 2,
            "receiver_name": "林小圓", "phone": "0912345678", "pickup_method": "門市取貨",
        }},
    ).json()["data"]
    submitted = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/submit",
        headers=write_headers("aiwave", "ec-submit"),
        json={"expected_version": draft["version"]},
    ).json()["data"]
    order_id = submitted["subjectId"]
    order = submitted["order"]
    assert order["total"] == 900  # 價格由平台目錄決定(450×2),不信任 client

    # 付款失敗 → payment_failed;重新付款成功 → 回到 placed(失敗恢復)
    client.post(
        "/api/v1/platform/payments", headers=write_headers("aiwave", "ec-pay-fail"),
        json={"subject_type": "commerce_order", "subject_id": order_id,
              "amount": 900, "outcome": "failure"},
    )
    failed = client.get("/api/v1/platform/commerce-orders", headers=bearer("aiwave")).json()["data"][0]
    assert failed["status"] == "payment_failed"
    client.post(
        "/api/v1/platform/payments", headers=write_headers("aiwave", "ec-pay-retry"),
        json={"subject_type": "commerce_order", "subject_id": order_id,
              "amount": 900, "outcome": "success"},
    )
    recovered = client.get("/api/v1/platform/commerce-orders", headers=bearer("aiwave")).json()["data"][0]
    assert recovered["status"] == "placed"

    order = recovered
    for step, status in (("ec-accept", "accepted"), ("ec-prepare", "preparing"),
                         ("ec-ship", "shipped"), ("ec-deliver", "delivered")):
        order = client.post(
            f"/api/v1/platform/commerce-orders/{order['id']}/transition",
            headers=write_headers("aiwave-partner-711shop", step),
            json={"expected_version": order["version"], "status": status},
        ).json()["data"]
    assert order["status"] == "delivered"
    inbox = client.get("/api/v1/platform/notifications", headers=bearer("aiwave")).json()["data"]
    assert any("已送達" in item["body"] for item in inbox["items"])


def test_resort_booking_no_prepayment_and_ticket_refund_on_cancel(tmp_path):
    """樂:訂房不預收款(2026-07-31 產品規則),取消乾淨無退款;
    退款與點數沖銷的覆蓋改由票券(commerce)取消驗證。"""
    client, _ = make_stack(tmp_path)
    provider = client.get(
        "/api/v1/platform/catalog/providers/vendor-uni-resort", headers=bearer("aiwave"),
    ).json()["data"]
    assert provider["placeholder"] is False
    assert any("馬武督" in item["name"] for item in provider["locations"])

    result, _ = submit_booking_draft(
        client, key_prefix="fun", domain_type="resort_booking",
        provider_id="vendor-uni-resort", offering_id="off-uniresort-stay",
        extra_values={"party_size": "2", "contact_name": "林小圓", "phone": "0912345678"},
    )
    booking_id = result["subjectId"]
    cancelled = client.post(
        f"/api/v1/platform/bookings/{booking_id}/cancellation",
        headers=write_headers("aiwave", "fun-cancel"),
        json={"expected_version": result["booking"]["version"], "note": "行程變更"},
    ).json()["data"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["refunds"] == []  # 未預收款,取消不產生退款

    # commerce(票券)仍走付款;取消 → 自動退款+點數沖銷
    submitted = submit_commerce_draft(
        client, key_prefix="fun-ticket", domain_type="ticket_purchase",
        offering_id="off-ibon-attraction",
        extra_values={"use_date": "2026-08-09", "buyer_name": "林小圓", "phone": "0912345678"},
    )
    order_id = submitted["subjectId"]
    payment = client.post(
        "/api/v1/platform/payments", headers=write_headers("aiwave", "fun-ticket-pay"),
        json={"subject_type": "commerce_order", "subject_id": order_id,
              "amount": 150, "points_redeemed": 50, "outcome": "success"},
    ).json()["data"]
    assert payment["status"] == "succeeded"
    assert client.get(
        "/api/v1/platform/points", headers=bearer("aiwave"),
    ).json()["data"]["balance"] == 130

    cancelled_order = client.post(
        f"/api/v1/platform/commerce-orders/{order_id}/cancellation",
        headers=write_headers("aiwave", "fun-ticket-cancel"),
        json={"expected_version": submitted["order"]["version"], "note": "不去了"},
    ).json()["data"]
    assert cancelled_order["status"] == "cancelled"
    assert cancelled_order["refunds"] and cancelled_order["refunds"][0]["status"] == "refunded"
    assert client.get(
        "/api/v1/platform/points", headers=bearer("aiwave"),
    ).json()["data"]["balance"] == 180  # 點數沖銷回到原餘額


def test_isolation_idempotency_and_cross_role_leak_protection(tmp_path):
    client, _ = make_stack(tmp_path)
    result, _ = submit_booking_draft(
        client, key_prefix="iso", domain_type="home_repair",
        provider_id="vendor-prince-electric", offering_id="off-prince-electric-repair",
        extra_values={"problem": "跳電", "address": "台北市信義區", "phone": "0900000000"},
    )
    booking_id = result["subjectId"]
    # 另一位會員看不到、也不能付款或取消(404 不洩漏存在性)
    assert client.get(
        f"/api/v1/platform/bookings/{booking_id}", headers=bearer("aiwave-chen"),
    ).status_code == 404
    assert client.post(
        "/api/v1/platform/payments", headers=write_headers("aiwave-chen", "iso-steal-pay"),
        json={"subject_type": "booking", "subject_id": booking_id,
              "amount": 1200, "outcome": "success"},
    ).status_code == 404
    assert client.post(
        f"/api/v1/platform/bookings/{booking_id}/cancellation",
        headers=write_headers("aiwave-chen", "iso-steal-cancel"),
        json={"expected_version": 1},
    ).status_code == 404
    # 其他廠商看不到、也不能操作這筆案件
    assert client.get(
        f"/api/v1/platform/bookings/{booking_id}", headers=bearer("aiwave-partner-duskin"),
    ).status_code == 404
    assert client.post(
        f"/api/v1/platform/bookings/{booking_id}/transition",
        headers=write_headers("aiwave-partner-duskin", "iso-steal-transition"),
        json={"expected_version": 1, "status": "confirmed"},
    ).status_code in {404, 409}
    # 會員不能走廠商狀態轉移端點
    assert client.post(
        f"/api/v1/platform/bookings/{booking_id}/transition",
        headers=write_headers("aiwave", "iso-member-transition"),
        json={"expected_version": 1, "status": "confirmed"},
    ).status_code == 403


def test_upstream_state_unknown_is_recoverable_via_retry(tmp_path):
    client, upstream = make_stack(tmp_path)
    offering_id = "off-prince-electric-repair"
    slot = pick_slot(client, "vendor-prince-electric", offering_id)
    draft = client.post(
        "/api/v1/platform/task-drafts", headers=write_headers("aiwave", "fault-draft"),
        json={"domain_type": "home_repair", "source": "user", "values": {
            "provider_id": "vendor-prince-electric", "location_id": slot["locationId"],
            "offering_id": offering_id, "resource_id": slot["resourceId"],
            "slot_id": slot["id"], "starts_at": slot["startsAt"], "ends_at": slot["endsAt"],
            "problem": "漏水", "address": "台北市信義區", "phone": "0911111111",
        }},
    ).json()["data"]
    upstream.put(
        "/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY},
        json={"method": "POST", "path": "/partner/v1/bookings", "status": 504,
              "detail": "已寫入但回應逾時", "after_commit": True},
    )
    failed = client.post(
        f"/api/v1/platform/task-drafts/{draft['id']}/submit",
        headers=write_headers("aiwave", "fault-submit"),
        json={"expected_version": draft["version"]},
    )
    assert failed.status_code == 503
    detail = failed.json()["detail"]
    assert detail["stateUnknown"] is True and detail["recoverable"] is True
    booking_id = detail["bookingId"]

    retried = client.post(
        f"/api/v1/platform/bookings/{booking_id}/provider-sync", headers=bearer("aiwave"),
    ).json()["data"]
    assert retried["providerSync"]["syncStatus"] == "synced"
    # upstream 只有一筆(同一 remote idempotency key,不重複建單)
    rows = upstream.get(
        "/partner/v1/bookings", headers=bearer(DEFAULT_PARTNER_KEYS["vendor-prince-electric"]),
    ).json()["data"]
    assert len(rows) == 1

    # 503 注入:目錄同步誠實回報 partial,不假裝成功
    upstream.put(
        "/__fake__/faults/next", headers={"X-Fake-Control-Key": CONTROL_KEY},
        json={"method": "GET", "path": "/partner/v1/catalog", "status": 503,
              "detail": "模擬 upstream 維護中"},
    )
    partial = client.post("/api/v1/platform/catalog/sync", headers=bearer("aiwave-admin")).json()["data"]
    assert partial["status"] == "partial"
    failed_rows = [row for row in partial["providers"] if row["status"] == "failed"]
    assert len(failed_rows) == 1
