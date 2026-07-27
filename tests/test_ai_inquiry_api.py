"""AI 對話閉環：口語 → 規則驗證 → 使用者確認 → 後端建立諮詢單。

對話與網頁表單讀**同一份**服務目錄題組定義，因此這裡用 `service_id` 而非舊的 form_id。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from core.inquiries import SqliteInquiryRepository

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
    }

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> str:
        raise AssertionError("FormAgent should request structured JSON")

    def json(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        prompt = " ".join(message.get("content", "") for message in messages)
        for title, answer in self.ANSWERS.items():
            if f"題目：{title}" in prompt:
                return answer
        return {"action": "unclear", "value": None, "note": f"沒有為這題準備答案：{prompt[:60]}"}


def test_real_ai_flow_requires_confirmation_then_persists_inquiry(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3",
        now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))

    started = client.post("/api/chat/start", json={"service_id": "service-repair"})
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

    for message in ["浴室的燈不亮了", "不急，可以安排時間"]:
        response = client.post("/api/chat/message", json={"session_id": session_id, "message": message})
        assert response.status_code == 200
        payload = response.json()
        assert payload["trace"]

    assert payload["awaiting_confirmation"] is True, payload
    assert payload["progress"]["answered"] == payload["progress"]["total"]
    assert repository.list_all() == []   # 確認前不寫入

    confirmed = client.post("/api/chat/message", json={"session_id": session_id, "message": "確認送出"})
    assert confirmed.status_code == 200
    completed = confirmed.json()
    assert completed["done"] is True
    assert completed["operation"] == {
        "type": "inquiry.created",
        "id": "INQ-20260725-001",
        "status": "pending_quote",
    }

    stored = client.get("/api/v1/inquiries/INQ-20260725-001").json()["data"]
    assert stored["status"] == "pending_quote"
    assert stored["events"][0]["type"] == "inquiry.created"


def test_conversation_uses_the_same_catalog_as_the_web_form(tmp_path: Path) -> None:
    """任何目錄服務都能開對話——不再只有寫死的三份題組。"""
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))

    for service_id in ("service-aircon", "service-restaurant", "service-shopping"):
        started = client.post("/api/chat/start", json={"service_id": service_id})
        assert started.status_code == 200, service_id
        assert started.json()["question"] is not None


def test_unknown_service_is_rejected(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))
    assert client.post("/api/chat/start", json={"service_id": "service-nope"}).status_code == 404


def test_unknown_session_never_reports_success(tmp_path: Path) -> None:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    client = TestClient(create_app(repository=repository, llm_factory=ScriptedLlm))
    response = client.post("/api/chat/message", json={"session_id": "missing", "message": "確認"})
    assert response.status_code == 404
    assert repository.list_all() == []
