"""Bedrock 版 `LlmClient`（[ADR-0004] 的雲端實作）。

官方競賽環境兩個硬約束（見 docs/specs/09 第 3 節）：

1. **全帳號 ≤1 RPS**——所以所有呼叫經過行程內的序列化佇列：一個 lock 保證
   同時只有一個請求在飛，並且兩次請求起點至少間隔 `_MIN_INTERVAL` 秒。
   多執行緒（FastAPI threadpool）下自然排隊，UI 呈現為「等待中」而非逾時。
2. **允許的 action 只有 `InvokeModel`／`InvokeModelWithResponseStream`，
   沒有 `Converse`**——所以這裡用 anthropic messages 原生格式打 `invoke_model`，
   不用 boto3 的 `converse()`（在競賽帳號會 AccessDenied）。

模型 ID 必須用 inference profile（`us.anthropic.…`）；直接用 foundation model ID
會回 ValidationException（on-demand 不支援）。
"""

from __future__ import annotations

import json
import threading
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from core.clients.llm import Message, _extract_json

#: 官方限制 1 RPS；留一點餘裕避免邊界抖動。
_MIN_INTERVAL = 1.1

_RETRYABLE = {"ThrottlingException", "ModelNotReadyException", "ServiceUnavailableException"}


class BedrockLlm:
    """以 `bedrock-runtime.invoke_model` 實作 `LlmClient`。"""

    def __init__(self, model_id: str, region: str | None = None) -> None:
        self.model = model_id
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            # 我們自己做退避重試（要配合 1 RPS 佇列），關掉 SDK 內建的
            config=Config(retries={"max_attempts": 1}, read_timeout=120),
        )
        self._lock = threading.Lock()
        self._last_call = 0.0

    def chat(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> str:
        system, converted = _to_anthropic(messages)
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": converted,
        }
        if system:
            body["system"] = system
        payload = json.dumps(body)

        attempts = 4
        for attempt in range(attempts):
            with self._lock:  # 序列化：同時最多一個請求在飛
                wait = self._last_call + _MIN_INTERVAL - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                try:
                    response = self._client.invoke_model(modelId=self.model, body=payload)
                except ClientError as error:
                    self._last_call = time.monotonic()
                    code = error.response.get("Error", {}).get("Code", "")
                    if code in _RETRYABLE and attempt < attempts - 1:
                        time.sleep(2**attempt)  # 1s, 2s, 4s 退避
                        continue
                    raise
                self._last_call = time.monotonic()
            data = json.loads(response["body"].read())
            return "".join(block.get("text", "") for block in data.get("content", []))
        raise RuntimeError("unreachable")  # pragma: no cover

    def json(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        return _extract_json(self.chat(messages, temperature=temperature, max_tokens=max_tokens))

    def grounded_json(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        return self.json(messages, temperature=temperature, max_tokens=max_tokens)


def _to_anthropic(messages: list[Message]) -> tuple[str, list[dict]]:
    """OpenAI 風格訊息 → anthropic messages 格式。

    system 訊息抽出成獨立參數；連續同角色訊息合併（anthropic 要求嚴格交替）。
    """
    system_parts: list[str] = []
    converted: list[dict] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(content)
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        if converted and converted[-1]["role"] == role:
            converted[-1]["content"] += "\n" + content
        else:
            converted.append({"role": role, "content": content})
    if not converted or converted[0]["role"] != "user":
        converted.insert(0, {"role": "user", "content": "（無輸入）"})
    return "\n".join(system_parts), converted
