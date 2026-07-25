"""意圖判讀：口語需求 → 服務目錄中的一項服務。

LLM 只負責判讀，回傳的 service id 一律用目錄驗證；判讀不出時回 None，由介面退回目錄。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.intent_agent import IntentAgent
from api.app import create_app
from core.inquiries import SqliteInquiryRepository


class ScriptedLlm:
    def __init__(self, response: object) -> None:
        self.response = response
        self.prompts: list[str] = []

    def chat(self, *args, **kwargs) -> str:
        raise AssertionError("IntentAgent should request structured JSON")

    def json(self, messages, **kwargs) -> object:
        self.prompts.append(messages[-1]["content"])
        return self.response


class BrokenLlm:
    def chat(self, *args, **kwargs) -> str:
        raise RuntimeError("provider down")

    def json(self, *args, **kwargs) -> object:
        raise RuntimeError("provider down")


def test_matches_a_spoken_need_to_a_catalog_service():
    llm = ScriptedLlm({"serviceId": "service-repair", "confidence": "high", "reason": "燈具故障"})
    match = IntentAgent(llm).match("浴室的燈不亮了")

    assert match is not None
    assert (match.service_id, match.service_name) == ("service-repair", "水電修繕")
    assert match.confidence == "high"
    assert match.reason == "燈具故障"


def test_prompt_includes_the_catalog_so_the_model_cannot_invent_services():
    llm = ScriptedLlm({"serviceId": "service-aircon", "confidence": "high", "reason": "冷氣"})
    IntentAgent(llm).match("冷氣不冷")
    assert "service-aircon" in llm.prompts[0]
    assert "浴室" not in llm.prompts[0]  # 只有目錄與該次需求


def test_hallucinated_service_id_is_rejected():
    """模型回一個不存在的服務時必須當作判讀失敗，而不是照單全收。"""
    llm = ScriptedLlm({"serviceId": "service-pet-sitting", "confidence": "high", "reason": "寵物"})
    assert IntentAgent(llm).match("幫我照顧貓") is None


def test_explicit_null_means_no_match():
    llm = ScriptedLlm({"serviceId": None, "confidence": "low", "reason": "無法對應"})
    assert IntentAgent(llm).match("幫我養一隻貓") is None


def test_provider_failure_degrades_to_no_match():
    assert IntentAgent(BrokenLlm()).match("浴室的燈不亮了") is None


def test_non_dict_response_degrades_to_no_match():
    assert IntentAgent(ScriptedLlm(["unexpected"])).match("浴室的燈不亮了") is None


@pytest.mark.parametrize("need", ["", "   "])
def test_blank_need_never_calls_the_model(need):
    llm = ScriptedLlm({"serviceId": "service-repair", "confidence": "high", "reason": "x"})
    assert IntentAgent(llm).match(need) is None
    assert llm.prompts == []


def test_confidence_defaults_to_low_when_not_high():
    llm = ScriptedLlm({"serviceId": "service-repair", "confidence": "maybe", "reason": ""})
    match = IntentAgent(llm).match("水管漏水")
    assert match is not None and match.confidence == "low"


# ---- API ----------------------------------------------------------------

def _client(tmp_path: Path, response: object) -> TestClient:
    repository = SqliteInquiryRepository(tmp_path / "inquiries.sqlite3")
    return TestClient(create_app(repository=repository, llm_factory=lambda: ScriptedLlm(response)))


def test_intent_endpoint_returns_the_matched_service(tmp_path: Path):
    client = _client(tmp_path, {"serviceId": "service-repair", "confidence": "high", "reason": "燈具故障"})
    payload = client.post("/api/v1/intent/match", json={"need": "浴室的燈不亮了"}).json()["data"]
    assert payload["serviceId"] == "service-repair"
    assert payload["serviceName"] == "水電修繕"


def test_intent_endpoint_returns_null_when_unmatched(tmp_path: Path):
    client = _client(tmp_path, {"serviceId": None, "confidence": "low", "reason": "無法對應"})
    response = client.post("/api/v1/intent/match", json={"need": "幫我養一隻貓"})
    assert response.status_code == 200
    assert response.json()["data"] is None
