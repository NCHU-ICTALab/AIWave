"""LlmClient 介面與實作。

本機：OpenAI 相容端點（NCHC Gemma）。最終：Bedrock Claude（另一個實作，不改呼叫端）。
見 [ADR-0004]。
"""

from __future__ import annotations

import json
import re
from typing import Protocol, runtime_checkable

from openai import OpenAI

from core.config import settings

Message = dict[str, str]


@runtime_checkable
class LlmClient(Protocol):
    def chat(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> str: ...

    def json(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> object: ...


class OpenAICompatLlm:
    """OpenAI Chat Completions 相容用戶端。"""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def chat(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def json(self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 512) -> object:
        """要求並解析 JSON 回覆（容忍 ```json 圍欄與前後雜訊）。"""
        text = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return _extract_json(text)


def _extract_json(text: str) -> object:
    """從模型回覆抽出第一段合法 JSON（物件或陣列）。"""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 退而求其次：抓第一個 {...} 或 [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = cleaned.find(opener), cleaned.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(cleaned[i : j + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"無法從回覆解析 JSON：{text[:200]!r}")


_singleton: OpenAICompatLlm | None = None


def get_llm() -> LlmClient:
    """取得預設 LLM 用戶端（依 .env 設定）。"""
    global _singleton
    if _singleton is None:
        s = settings()
        _singleton = OpenAICompatLlm(s.api_url, s.api_key, s.model)
    return _singleton
