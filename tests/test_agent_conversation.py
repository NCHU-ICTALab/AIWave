"""Natural conversation stays contextual without gaining transaction powers."""

from __future__ import annotations

from core.agent_core.orchestrator import AgentOrchestrator


class ConversationalLlm:
    def __init__(self, reply: str | None = None, *, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.messages: list[list[dict[str, str]]] = []

    def chat(self, messages, **kwargs):  # noqa: ANN001 - tiny test double
        self.messages.append(messages)
        if self.error:
            raise self.error
        return self.reply or ""


def make_orchestrator(llm: ConversationalLlm) -> AgentOrchestrator:
    return AgentOrchestrator(
        llm_factory=lambda: llm,
        registry=object(),
        time_resolver=object(),
        catalog=object(),
        drafts=object(),
        points=object(),
        wiki=None,
    )


def test_conversation_uses_recent_context_and_is_not_the_old_script() -> None:
    llm = ConversationalLlm("今天想出門走走嗎？如果你告訴我城市和時間，我可以幫你一起整理安排。")
    session = {"messages": [{"role": "assistant", "content": "昨天你提到週末要陪家人。"}]}

    turn = make_orchestrator(llm).handle(
        session,
        owner={"account_id": "household-wang-xiaoming"},
        message="今天天氣如何？",
    )

    assert session["messages"][-1]["content"] == "今天想出門走走嗎？如果你告訴我城市和時間，我可以幫你一起整理安排。"
    assert turn.grounded_response["source"] == "llm-conversation"
    assert llm.messages[-1][-2]["content"] == "昨天你提到週末要陪家人。"
    assert llm.messages[-1][-1]["content"] == "今天天氣如何？"


def test_conversation_fallback_is_honest_when_model_is_unavailable() -> None:
    llm = ConversationalLlm(error=RuntimeError("model unavailable"))
    session = {"messages": []}

    turn = make_orchestrator(llm).handle(
        session,
        owner={"account_id": "household-wang-xiaoming"},
        message="今天天氣如何？",
    )

    reply = session["messages"][-1]["content"]
    assert "沒有接上即時天氣資料" in reply
    assert turn.grounded_response["source"] == "safe-fallback"
    assert len(llm.messages) == 2


def test_conversation_rejects_a_model_claim_of_transaction_side_effect() -> None:
    llm = ConversationalLlm("已下單完成，明天會送到。")
    session = {"messages": []}

    turn = make_orchestrator(llm).handle(
        session,
        owner={"account_id": "household-wang-xiaoming"},
        message="嗨",
    )

    assert "不用先想服務名稱" in session["messages"][-1]["content"]
    assert turn.grounded_response["source"] == "safe-fallback"
