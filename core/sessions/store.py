"""對話工作階段的儲存介面（[ADR-0018] 要上 AWS 常駐服務的前提）。

原本的實作把 `FormSession`／`FormAgent` 物件直接放在行程內的 dict 裡。地端單一行程
沒問題，但常駐服務一定不只一個執行單元——請求打到另一台就會「工作階段不存在」，
而且沒有任何錯誤訊息說得清楚為什麼。

解法是把**狀態**（可序列化）與**物件**（不可序列化）分開：

- `ConversationState` 只有純資料：服務代碼、已填答案、略過的題目、是否等待確認。
  `FormSession` 本來就支援用既有答案重建（`known` 參數），所以每次請求重建即可。
- `FormAgent` 是無狀態的（只包一個 LLM 客戶端），本來就不需要保存。

因此換成 ElastiCache／DynamoDB 時，只要多寫一個 `SessionStore` 實作，
`api/app.py` 一行都不用改。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ConversationState:
    """一段引導填答對話的完整狀態——刻意只放可序列化的資料。"""

    session_id: str
    service_id: str
    #: topic_id → 已驗證的答案值
    answers: dict[int, object] = field(default_factory=dict)
    #: 使用者明確略過的選填題
    skipped: list[int] = field(default_factory=list)
    awaiting_confirm: bool = False
    submitted_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "sessionId": self.session_id,
            "serviceId": self.service_id,
            # JSON 的物件鍵一律是字串，先轉好，避免不同實作各自處理而不一致
            "answers": {str(key): value for key, value in self.answers.items()},
            "skipped": list(self.skipped),
            "awaitingConfirm": self.awaiting_confirm,
            "submittedId": self.submitted_id,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> ConversationState:
        return cls(
            session_id=str(payload["sessionId"]),
            service_id=str(payload["serviceId"]),
            answers={int(key): value for key, value in (payload.get("answers") or {}).items()},
            skipped=[int(value) for value in (payload.get("skipped") or [])],
            awaiting_confirm=bool(payload.get("awaitingConfirm")),
            submitted_id=payload.get("submittedId"),
        )


class SessionStore(Protocol):
    def get(self, session_id: str) -> ConversationState | None: ...
    def save(self, state: ConversationState) -> None: ...
    def delete(self, session_id: str) -> None: ...


class InMemorySessionStore:
    """地端與測試用。雲端換成 ElastiCache／DynamoDB 實作即可。"""

    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = {}

    def get(self, session_id: str) -> ConversationState | None:
        return self._states.get(session_id)

    def save(self, state: ConversationState) -> None:
        self._states[state.session_id] = state

    def delete(self, session_id: str) -> None:
        self._states.pop(session_id, None)
