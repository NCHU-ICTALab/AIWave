"""AI 對話閉環：口語 → 規則驗證 → 使用者確認 → 後端建立諮詢單。

對話與網頁表單讀**同一份**服務目錄題組定義，因此這裡用 `service_id` 而非舊的 form_id。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from core.config import get_settings
from core.inquiries import SqliteInquiryRepository
from core.orders import SqliteOrderRepository
from tests.auth import MEMBER_HEADERS, MEMBER_ID, SECOND_MEMBER_ID

# core/forms/service_catalog.py 的水電修繕選項
REPAIR_LIGHTING = 1071   # 燈具／開關
URGENCY_NORMAL = 1080    # 一般，可安排時段


class ScriptedLlm:
    """只在外部 LLM 邊界做測試替身。

    **依題目回答，而不是依呼叫順序。** 服務是無狀態的（見 `core.sessions`），
    每次請求都會建立新的 LLM 客戶端；照順序播放的腳本會在每次請求重頭開始，
    測到的其實是「同一行程內連續呼叫」這個不該依賴的假設。
    真實的 LLM 也是看到什麼題目就答什麼，與是第幾次呼叫無關。
    """

    ANSWERS = {
        "修繕項目": {"action": "answer", "value": {"option_id": REPAIR_LIGHTING, "quantity": None}, "note": "辨識為燈具問題"},
        "緊急程度": {"action": "answer", "value": {"option_id": URGENCY_NORMAL, "quantity": None}, "note": "可安排時段"},
        "服務地區": {"action": "answer", "value": {"county_name": "臺北市", "district_name": "大同區"}, "note": "臺北市大同區"},
        "希望日期": {"action": "answer", "value": "2026-07-28", "note": "7 月 28 日"},
        "希望時段": {"action": "answer", "value": {"option_id": 1090, "quantity": None}, "note": "上午"},
        "聯絡資料與到府地址": {"action": "answer", "value": {"name": "林小圓", "mobile": "0912345678", "address": "臺北市大同區承德路一段 1 號"}, "note": "已整理聯絡資料"},
    }

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> str:
        raise AssertionError("FormAgent should request structured JSON")

    def json(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        prompt = " ".join(message.get("content", "") for message in messages)
        for title, answer in self.ANSWERS.items():
            if f"題目：{title}" in prompt:
                return answer
        return {"action": "unclear", "value": None, "note": f"沒有為這題準備答案：{prompt[:60]}"}


class ShoppingLlm(ScriptedLlm):
    ANSWERS = {
        "補貨組合": {"action": "answer", "value": {"option_id": 1150, "quantity": None}, "note": "補貨組"},
        "優惠券": {"action": "answer", "value": {"option_id": 1160, "quantity": None}, "note": "套用"},
        "OPENPOINT 折抵": {"action": "answer", "value": {"option_id": 1170, "quantity": None}, "note": "折 50"},
        "取貨方式": {"action": "answer", "value": {"option_id": 1180, "quantity": None}, "note": "門市"},
        "支付方式": {"action": "answer", "value": {"option_id": 1190, "quantity": None}, "note": "icash Pay"},
    }


class RelativeDateLlm(ScriptedLlm):
    """依 API 注入提示中的『今天』換算明天，模擬真實模型的相對日期行為。"""

    def json(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        prompt = " ".join(message.get("content", "") for message in messages)
        if "題目：冷氣類型" in prompt:
            return {"action": "answer", "value": {"option_id": 1020, "quantity": None}, "note": "分離式"}
        if "題目：清洗台數" in prompt:
            return {"action": "answer", "value": "2", "note": "兩台"}
        if "題目：希望日期" in prompt:
            marker = "今天是 "
            start = prompt.index(marker) + len(marker)
            current = date.fromisoformat(prompt[start:start + 10])
            return {"action": "answer", "value": (current + timedelta(days=1)).isoformat(), "note": "明天"}
        if "題目：希望時段" in prompt:
            return {"action": "answer", "value": {"option_id": 9100, "quantity": None}, "note": "上午"}
        return super().json(messages, temperature=temperature, max_tokens=max_tokens)


def test_real_ai_flow_requires_confirmation_then_persists_inquiry(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3",
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm, today=date(2026, 7, 25)))

    started = client.post("/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-repair"})
    assert started.status_code == 200
    payload = started.json()
    assert payload["service_name"] == "水電修繕"
    assert payload["progress"]["answered"] == 0
    assert payload["trace"][0]["tool"] == "get_service_form"
    session_id = payload["session_id"]

    # 首題就附可點選的選項，使用者不必打字
    assert [option["label"] for option in payload["question"]["options"]] == [
        "水管／馬桶", "燈具／開關", "插座", "其他",
    ]

    for message in ["浴室的燈不亮了", "不急，可以安排時間", "臺北市大同區", "7 月 28 日", "上午", "林小圓 0912345678，臺北市大同區承德路一段 1 號"]:
        response = client.post(
            "/api/chat/message",
            headers=MEMBER_HEADERS,
            json={"session_id": session_id, "message": message, "account_id": SECOND_MEMBER_ID},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["trace"]

    assert payload["awaiting_confirmation"] is True, payload
    assert payload["progress"]["answered"] == payload["progress"]["total"]
    assert repository.list_all() == []   # 確認前不寫入

    confirmed = client.post(
        "/api/chat/message", headers=MEMBER_HEADERS,
        json={"session_id": session_id, "message": "確認送出", "account_id": SECOND_MEMBER_ID},
    )
    assert confirmed.status_code == 200
    completed = confirmed.json()
    assert completed["done"] is True
    assert completed["operation"] == {
        "type": "inquiry.created",
        "id": "INQ-20260725-001",
        "status": "pending_quote",
    }

    stored = client.get(
        "/api/v1/inquiries/INQ-20260725-001", headers=MEMBER_HEADERS,
    ).json()["data"]
    assert {line["label"] for line in stored["summary"]} >= {
        "修繕項目", "緊急程度", "服務地區", "希望日期", "希望時段", "聯絡資料與到府地址",
    }
    assert stored["status"] == "pending_quote"
    assert stored["events"][0]["type"] == "inquiry.created"


def test_relative_date_uses_configured_current_day_across_prompt_and_validation(
    tmp_path: Path, monkeypatch,
) -> None:
    """部署環境指定 7/29 時，使用者說『明天』必須得到 7/30，而不是舊展示日的 7/26。"""
    monkeypatch.setenv("DEMO_TODAY", "2026-07-29")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app(
            repository=SqliteInquiryRepository(tmp_path / "relative-date.sqlite3"),
            llm_factory=RelativeDateLlm,
        ))
        session_id = client.post(
            "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-aircon"},
        ).json()["session_id"]

        payload = {}
        for answer in ("分離式", "兩台", "明天", "上午"):
            response = client.post(
                "/api/chat/message", headers=MEMBER_HEADERS,
                json={"session_id": session_id, "message": answer},
            )
            assert response.status_code == 200
            payload = response.json()

        assert payload["awaiting_confirmation"] is True
        assert "2026-07-30" in payload["reply"]
        assert "2026-07-26" not in payload["reply"]
    finally:
        get_settings.cache_clear()


def test_shopping_conversation_confirms_into_a_persistent_order(tmp_path: Path) -> None:
    now = lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)  # noqa: E731
    db = tmp_path / "shopping.sqlite3"
    orders = SqliteOrderRepository(db, now=now)
    client = TestClient(create_app(
        repository=SqliteInquiryRepository(db, now=now),
        order_repository=orders,
        llm_factory=ShoppingLlm,
    ))
    session_id = client.post(
        "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-shopping"},
    ).json()["session_id"]
    payload = {}
    for answer in ("補貨組", "套用", "50 點", "門市", "icash Pay"):
        payload = client.post(
            "/api/chat/message",
            headers=MEMBER_HEADERS,
            json={"session_id": session_id, "message": answer, "account_id": SECOND_MEMBER_ID},
        ).json()
    assert payload["awaiting_confirmation"] is True

    confirmed = client.post(
        "/api/chat/message",
        headers=MEMBER_HEADERS,
        json={"session_id": session_id, "message": "確認送出", "account_id": SECOND_MEMBER_ID},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["operation"]["type"] == "order.created"
    order = orders.list_for_account(MEMBER_ID)[0]
    assert order["amount"] == 579
    assert client.get(
        f"/api/v1/orders/{order['id']}", headers=MEMBER_HEADERS,
        params={"account_id": MEMBER_ID},
    ).status_code == 200
    assert client.get(
        f"/api/v1/orders/{order['id']}", headers=MEMBER_HEADERS,
        params={"account_id": SECOND_MEMBER_ID},
    ).status_code == 404


def test_conversation_uses_the_same_catalog_as_the_web_form(tmp_path: Path) -> None:
    """任何目錄服務都能開對話——不再只有寫死的三份題組。"""
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))

    for service_id in ("service-aircon", "service-restaurant", "service-shopping"):
        started = client.post("/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": service_id})
        assert started.status_code == 200, service_id
        assert started.json()["question"] is not None


def test_unknown_service_is_rejected(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))
    assert client.post(
        "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-nope"},
    ).status_code == 404


def test_unknown_session_never_reports_success(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))
    response = client.post(
        "/api/chat/message", headers=MEMBER_HEADERS,
        json={"session_id": "missing", "message": "確認"},
    )
    assert response.status_code == 404
    assert repository.list_all() == []


def test_message_stream_reports_progress_then_text_then_complete(tmp_path: Path) -> None:
    """串流先回安全的處理階段，再逐段回文字，最後才附完整狀態。"""
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))
    session_id = client.post(
        "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-repair"},
    ).json()["session_id"]

    with client.stream(
        "POST",
        "/api/chat/message/stream",
        headers=MEMBER_HEADERS,
        json={"session_id": session_id, "message": "浴室的燈不亮了"},
    ) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert events[0] == {"type": "status", "label": "正在理解你的回答"}
    assert "".join(event["text"] for event in events if event["type"] == "delta").startswith("請問緊急程度")
    assert events[-1]["type"] == "complete"
    assert events[-1]["data"]["progress"]["answered"] == 1
