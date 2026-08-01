"""Bedrock 版 LlmClient 的離線測試：訊息格式轉換與 1 RPS 佇列。

不碰真正的 AWS——`_client` 以假物件替換；重點是守住兩條官方環境約束：
InvokeModel 的 anthropic messages 格式，與呼叫間隔 ≥ 1 秒。
"""

from __future__ import annotations

import io
import json
import time

from core.clients.bedrock import BedrockLlm, _to_anthropic


def test_to_anthropic_extracts_system_and_merges_consecutive_roles():
    system, messages = _to_anthropic(
        [
            {"role": "system", "content": "你是管家"},
            {"role": "system", "content": "只回 JSON"},
            {"role": "user", "content": "修燈"},
            {"role": "user", "content": "還要洗冷氣"},
            {"role": "assistant", "content": "好的"},
        ]
    )
    assert system == "你是管家\n只回 JSON"
    assert messages == [
        {"role": "user", "content": "修燈\n還要洗冷氣"},
        {"role": "assistant", "content": "好的"},
    ]


def test_to_anthropic_inserts_user_message_when_first_is_assistant():
    _, messages = _to_anthropic([{"role": "assistant", "content": "嗨"}])
    assert messages[0]["role"] == "user"


class _FakeBedrockRuntime:
    def __init__(self):
        self.calls: list[float] = []
        self.bodies: list[dict] = []

    def invoke_model(self, *, modelId: str, body: str):
        self.calls.append(time.monotonic())
        self.bodies.append(json.loads(body))
        payload = json.dumps({"content": [{"type": "text", "text": '{"ok": true}'}]}).encode()
        return {"body": io.BytesIO(payload)}


def _client_with_fake() -> tuple[BedrockLlm, _FakeBedrockRuntime]:
    llm = BedrockLlm("us.anthropic.claude-sonnet-4-6", region="us-west-2")
    fake = _FakeBedrockRuntime()
    llm._client = fake  # type: ignore[assignment]
    return llm, fake


def test_chat_sends_invoke_model_native_format():
    llm, fake = _client_with_fake()
    text = llm.chat([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], max_tokens=99)
    assert text == '{"ok": true}'
    body = fake.bodies[0]
    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["system"] == "s"
    assert body["max_tokens"] == 99


def test_json_parses_reply():
    llm, _ = _client_with_fake()
    assert llm.json([{"role": "user", "content": "u"}]) == {"ok": True}


def test_serialized_queue_spaces_calls_at_least_one_second():
    llm, fake = _client_with_fake()
    llm.chat([{"role": "user", "content": "1"}])
    llm.chat([{"role": "user", "content": "2"}])
    assert fake.calls[1] - fake.calls[0] >= 1.0
