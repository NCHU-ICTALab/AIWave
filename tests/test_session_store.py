"""對話工作階段的儲存（ADR-0018：要上 AWS 常駐服務的前提）。

守住一件事：**對話狀態不能只活在行程記憶體裡**。常駐服務一定不只一個執行單元，
第二個請求打到另一台時，使用者不該看到「工作階段不存在，請重新開始」。

驗證方式是把 `SessionStore` 換成「只保留可序列化資料」的實作——
如果程式碼偷偷依賴了行程內的物件，這裡就會壞。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.forms import FormSession
from core.forms.seed_forms import OPT_LAMP_OFF, repair_form
from core.forms.service_catalog import get_service_form
from core.inquiries import SqliteInquiryRepository
from core.sessions import ConversationState, InMemorySessionStore
from tests.auth import MEMBER_HEADERS, MEMBER_ID, SECOND_MEMBER_HEADERS

REPAIR_LIGHTING = 1071
URGENCY_NORMAL = 1080
SLOT_MORNING = 1090


class RoundTripSessionStore:
    """每次存取都經過 JSON 往返，模擬 DynamoDB／ElastiCache。

    任何無法序列化的東西（`FormSession`、`FormAgent`、`Selection` 物件）
    一旦被塞進狀態，這裡就會爆——這正是我們要防的退化。
    """

    def __init__(self) -> None:
        self._raw: dict[str, str] = {}

    def get(self, session_id: str) -> ConversationState | None:
        payload = self._raw.get(session_id)
        return None if payload is None else ConversationState.from_dict(json.loads(payload))

    def save(self, state: ConversationState) -> None:
        self._raw[state.session_id] = json.dumps(state.to_dict(), ensure_ascii=False)

    def delete(self, session_id: str) -> None:
        self._raw.pop(session_id, None)


class ScriptedLlm:
    ANSWERS = {
        "修繕項目": {"action": "answer", "value": {"option_id": REPAIR_LIGHTING, "quantity": None}, "note": ""},
        "緊急程度": {"action": "answer", "value": {"option_id": URGENCY_NORMAL, "quantity": None}, "note": ""},
        "服務地區": {"action": "answer", "value": {"county_name": "臺北市", "district_name": "大同區"}, "note": ""},
        "希望日期": {"action": "answer", "value": "2026-07-26", "note": ""},
        "希望時段": {"action": "answer", "value": {"option_id": SLOT_MORNING, "quantity": None}, "note": ""},
        "聯絡資料與到府地址": {"action": "answer", "value": {"name": "王小明", "mobile": "0912345678", "address": "臺北市大同區民生西路 1 號"}, "note": ""},
    }

    def json(self, messages, **kwargs):
        prompt = " ".join(message.get("content", "") for message in messages)
        for title, answer in self.ANSWERS.items():
            if f"題目：{title}" in prompt:
                return answer
        return {"action": "unclear", "value": None, "note": ""}

    def chat(self, messages, **kwargs):  # pragma: no cover
        raise AssertionError("FormAgent 應該要求結構化 JSON")


class TestConversationState:
    def test_survives_a_json_round_trip(self):
        state = ConversationState(
            session_id="s1", service_id="service-repair",
            answers={1: "x"}, skipped=[2], awaiting_confirm=True, submitted_id="INQ-1",
        )
        restored = ConversationState.from_dict(json.loads(json.dumps(state.to_dict())))

        assert restored == state

    def test_keeps_integer_topic_ids_despite_json_string_keys(self):
        """JSON 的物件鍵一律是字串；還原時沒轉回 int 的話，題目就對不上。"""
        state = ConversationState(session_id="s1", service_id="service-repair", answers={7: "x"})
        restored = ConversationState.from_dict(json.loads(json.dumps(state.to_dict())))

        assert list(restored.answers) == [7]


class TestFormSessionRebuild:
    def test_restores_skipped_topics_so_they_are_not_asked_again(self):
        """只還原答案是不夠的——略過的題目會被重新問一次。

        現行服務目錄剛好沒有選填題，所以用 seed 表單（含選填的「現場照片」）
        驗證引擎契約本身；目錄哪天加了選填題，這條保證已經在了。
        """
        form = repair_form()
        photo = next(topic for topic in form.ordered_topics() if not topic.is_required)
        raw_answers = {1: {"option_id": OPT_LAMP_OFF, "quantity": None}}

        original = FormSession(form, known=dict(raw_answers))
        original.skip(photo.id)

        rebuilt = FormSession(form, known=dict(raw_answers))
        for topic_id in original.skipped_ids:
            rebuilt.mark_skipped(topic_id)

        assert rebuilt.next_topic() != photo
        assert rebuilt.progress() == original.progress()

    def test_the_stored_answers_stay_json_serialisable(self):
        """驗證後的 Selection 物件不能序列化，所以狀態只能存原始輸入。"""
        form = get_service_form("service-repair")
        assert form is not None
        raw = {"option_id": REPAIR_LIGHTING, "quantity": None}
        session = FormSession(form, known={1: raw})

        # 驗證後的值不可序列化——這正是不能直接存 session.answers 的理由
        with pytest.raises(TypeError):
            json.dumps(session.answers)
        # 原始值可以，而且重放後結果相同
        assert json.loads(json.dumps({1: raw})) == {"1": raw}


class TestChatWithoutProcessMemory:
    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        return TestClient(
            create_app(
                repository=SqliteInquiryRepository(
                    tmp_path / "inq.sqlite3", now=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc)
                ),
                sessions=RoundTripSessionStore(),
                llm_factory=ScriptedLlm,
                today=date(2026, 7, 25),
            )
        )

    def test_completes_a_whole_conversation_through_a_serialising_store(self, client: TestClient):
        session_id = client.post(
            "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-repair"},
        ).json()["session_id"]

        for message in ["浴室的燈不亮了", "不急，可以安排時間", "臺北市大同區", "明天", "上午", "王小明 0912345678 臺北市大同區民生西路 1 號"]:
            payload = client.post(
                "/api/chat/message", headers=MEMBER_HEADERS,
                json={"session_id": session_id, "message": message},
            ).json()

        assert payload["awaiting_confirmation"] is True

        done = client.post(
            "/api/chat/message",
            headers=MEMBER_HEADERS,
            json={"session_id": session_id, "message": "確認送出", "account_id": "A001"},
        ).json()
        assert done["done"] is True
        assert done["operation"]["id"].startswith("INQ-")

    def test_the_submitted_inquiry_belongs_to_the_signed_in_household(self, client: TestClient):
        session_id = client.post(
            "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-repair"},
        ).json()["session_id"]
        for message in ["浴室的燈不亮了", "不急，可以安排時間", "臺北市大同區", "明天", "上午", "王小明 0912345678 臺北市大同區民生西路 1 號"]:
            client.post(
                "/api/chat/message", headers=MEMBER_HEADERS,
                json={"session_id": session_id, "message": message},
            )
        inquiry_id = client.post(
            "/api/chat/message",
            headers=MEMBER_HEADERS,
            json={"session_id": session_id, "message": "確認送出", "account_id": "A001"},
        ).json()["operation"]["id"]

        record = client.get(
            f"/api/v1/inquiries/{inquiry_id}", headers=MEMBER_HEADERS,
        ).json()["data"]
        assert record["account_id"] == MEMBER_ID

    def test_an_unknown_session_is_reported_rather_than_crashing(self, client: TestClient):
        response = client.post(
            "/api/chat/message", headers=MEMBER_HEADERS,
            json={"session_id": "nope", "message": "hi"},
        )

        assert response.status_code == 404

    def test_another_member_cannot_resume_the_conversation(self, client: TestClient):
        session_id = client.post(
            "/api/chat/start", headers=MEMBER_HEADERS, json={"service_id": "service-repair"},
        ).json()["session_id"]
        response = client.post(
            "/api/chat/message", headers=SECOND_MEMBER_HEADERS,
            json={"session_id": session_id, "message": "浴室的燈不亮了"},
        )
        assert response.status_code == 404


def test_the_in_memory_store_still_satisfies_the_protocol():
    store = InMemorySessionStore()
    state = ConversationState(session_id="s1", service_id="service-repair")

    store.save(state)
    assert store.get("s1") == state
    store.delete("s1")
    assert store.get("s1") is None
