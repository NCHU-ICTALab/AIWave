"""外部服務用戶端（介面隔離，見 ADR-0004）：LLM、（未來）語音、事件、物件儲存。"""

from .llm import LlmClient, get_llm

__all__ = ["LlmClient", "get_llm"]
