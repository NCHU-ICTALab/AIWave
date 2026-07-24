from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import SqliteInquiryRepository


class ScriptedLlm:
    """Deterministic test double at the external LLM boundary only."""

    def __init__(self) -> None:
        self._responses = iter([
            {"action": "answer", "value": [{"option_id": 130, "quantity": 2}], "note": "辨識為兩台冷氣"},
            {"action": "answer", "value": {"option_id": 141, "quantity": None}, "note": "辨識為分離式"},
            {"action": "skip", "value": None, "note": "目前沒有照片"},
            {"action": "answer", "value": {"county_name": "台中市", "district_name": "西屯區"}, "note": "已對應官方行政區"},
            {"action": "answer", "value": "2026-07-28", "note": "日期在可預約範圍"},
            {"action": "answer", "value": {"option_id": 161, "quantity": None}, "note": "辨識為上午"},
            {"action": "answer", "value": {"name": "陳小圓", "mobile": "0912345678", "address": "晴川社區"}, "note": "聯絡資料已結構化"},
        ])

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> str:
        raise AssertionError("FormAgent should request structured JSON")

    def json(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        return next(self._responses)


def test_real_ai_flow_requires_confirmation_then_persists_inquiry(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3",
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))

    started = client.post("/api/chat/start", json={"form_id": "repair"})
    assert started.status_code == 200
    payload = started.json()
    assert payload["progress"]["answered"] == 0
    assert payload["trace"][0]["tool"] == "get_service_form"
    session_id = payload["session_id"]

    messages = [
        "我有兩台分離式冷氣要洗",
        "都是分離式",
        "目前沒有照片",
        "台中市西屯區",
        "2026-07-28",
        "上午",
        "陳小圓，0912345678，晴川社區",
    ]
    response_payload = None
    for message in messages:
        response = client.post("/api/chat/message", json={"session_id": session_id, "message": message})
        assert response.status_code == 200
        response_payload = response.json()
        assert response_payload["trace"]

    assert response_payload is not None
    assert response_payload["awaiting_confirmation"] is True, response_payload
    assert response_payload["progress"]["answered"] == response_payload["progress"]["total"]
    assert repository.list_all() == []

    confirmed = client.post("/api/chat/message", json={"session_id": session_id, "message": "確認送出"})
    assert confirmed.status_code == 200
    completed = confirmed.json()
    assert completed["done"] is True
    assert completed["operation"] == {
        "type": "inquiry.created",
        "id": "INQ-20260725-001",
        "status": "pending_quote",
    }

    inquiry = client.get("/api/v1/inquiries/INQ-20260725-001")
    assert inquiry.status_code == 200
    stored = inquiry.json()["data"]
    assert stored["id"] == "INQ-20260725-001"
    assert stored["status"] == "pending_quote"
    assert stored["events"][0]["type"] == "inquiry.created"


def test_unknown_session_never_reports_success(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))
    response = client.post("/api/chat/message", json={"session_id": "missing", "message": "確認"})
    assert response.status_code == 404
    assert repository.list_all() == []
