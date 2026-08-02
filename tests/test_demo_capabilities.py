from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from core.access import Role, SqliteAccessRepository
from core.agent_core.orchestrator import AgentOrchestrator
from core.agent_core.registry import ServiceRegistry
from core.agent_core.time_resolver import TAIPEI, TimeResolver
from core.agent_core.turns import capability_descriptions
from core.wiki import WikiService


def test_wang_demo_credential_is_seeded_as_a_member(tmp_path):
    access = SqliteAccessRepository(tmp_path / "demo.sqlite3")

    resident = access.resolve_bearer("aiwave-demo-resident")
    manager = access.resolve_bearer("aiwave-demo-manager")

    assert resident.account_id == "household-wang-xiaoming"
    assert resident.display_name == "王小明"
    assert resident.role is Role.MEMBER
    assert manager.role is Role.COMMUNITY_MANAGER

    client = TestClient(create_app(demo_db_path=tmp_path / "api.sqlite3"))
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer aiwave-demo-resident"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["accountId"] == "household-wang-xiaoming"

    opened = client.post(
        "/api/v1/community/campaigns",
        headers={"Authorization": "Bearer aiwave-demo-resident"},
        json={"title": "王小明發起的茶飲團", "item_name": "茶裏王", "unit_price": 828},
    )
    assert opened.status_code == 200


def test_occasion_only_sentences_resolve_to_real_services():
    """「父親節那個交給你安排」沒有服務名詞,仍必須落到真的做得到的服務上。"""

    registry = ServiceRegistry()

    for sentence, expected in (
        ("父親節那個結果我交給 AI 安排", ["清潔", "餐廳"]),
        ("爸媽要來,幫我處理一下", ["清潔", "餐廳"]),
        ("過年前想先把家裡弄好", ["大掃除", "餐廳"]),
        ("下個月要搬家", ["清潔", "宅配"]),
    ):
        suggestions = registry.suggest_for_occasion(sentence)
        assert [item.service_hint for item in suggestions] == expected
        # 每個建議都必須是登錄表解得開的真服務,不能只是好聽的字串。
        assert all(registry.resolve(item.service_hint).matched for item in suggestions)


def test_occasion_table_never_overrides_an_explicit_service_word():
    registry = ServiceRegistry()

    # 句中已經有服務名詞時,orchestrator 不會走場合表;登錄表自己也解得開。
    assert registry.resolve("父親節想找人修水電").matched == "home_repair"


def test_capability_registry_exposes_the_demo_capabilities():
    assert {item["id"] for item in capability_descriptions()} >= {
        "service.recommend", "community.wiki", "life_circle.search", "calendar.organize",
    }


class _UnhelpfulLlm:
    """A model that understands the sentence but names a service we do not have."""

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.systems: list[str] = []

    def json(self, messages, **kwargs):  # noqa: ANN001 - tiny test double
        self.systems.append(messages[0]["content"])
        return self.payload

    def chat(self, messages, **kwargs):  # noqa: ANN001 - tiny test double
        raise RuntimeError("grounding model unavailable")


class _EmptyCatalog:
    """目錄查詢不是這幾個測試的主題;重點是需求有沒有落到真的 domain 上。"""

    def list_providers(self, **kwargs):  # noqa: ANN003 - tiny test double
        return []


def _occasion_orchestrator(llm) -> AgentOrchestrator:
    return AgentOrchestrator(
        llm_factory=lambda: llm,
        registry=ServiceRegistry(),
        time_resolver=TimeResolver(now=lambda: datetime(2026, 8, 2, 10, 0, tzinfo=TAIPEI)),
        catalog=_EmptyCatalog(), drafts=object(), points=object(), wiki=None,
    )


def test_occasion_turn_never_dead_ends_on_an_unresolvable_service_hint():
    """使用者說「父親節那個交給你安排」時,不可以停在「不確定對應哪一類服務」。"""

    llm = _UnhelpfulLlm({"subtasks": [
        {"goal": "父親節的安排", "serviceHint": "父親節活動規劃", "datePhrase": ""},
    ]})
    session = {"id": "s1", "messages": [], "subtasks": [], "grantId": None}

    _occasion_orchestrator(llm).handle(
        session,
        owner={"demo_workspace_id": "d", "workspace_id": "w", "account_id": "household-wang-xiaoming"},
        message="父親節那個結果我交給 AI 安排",
    )

    domains = [item["domain"] for item in session["subtasks"]]
    assert domains == ["home_cleaning", "dining_reservation"]
    # 場合表只挑服務類別,日期一律留給使用者。
    assert all(item["time"] is None for item in session["subtasks"])
    # 需求理解器拿得到登錄表字彙,才有機會自己抽對 serviceHint。
    assert "serviceVocabulary" in llm.systems[0]


def test_unknown_goal_answers_with_what_the_platform_can_do():
    """真的對應不到時,也要說出平台會什麼,而不是只說不懂。"""

    llm = _UnhelpfulLlm({"subtasks": [
        {"goal": "幫我養一隻貓", "serviceHint": "寵物代養", "datePhrase": ""},
    ]})
    session = {"id": "s2", "messages": [], "subtasks": [], "grantId": None}

    _occasion_orchestrator(llm).handle(
        session,
        owner={"demo_workspace_id": "d", "workspace_id": "w", "account_id": "household-wang-xiaoming"},
        message="幫我養一隻貓",
    )

    reply = session["messages"][-1]["content"]
    assert "水電修繕" in reply and "居家清潔" in reply and "餐廳訂位" in reply


def test_service_vocabulary_is_offered_to_the_understander():
    """需求理解器拿得到登錄表字彙,才不會抽出無法解析的 serviceHint。"""

    vocabulary = ServiceRegistry().vocabulary()

    assert "home_cleaning" in vocabulary and "dining_reservation" in vocabulary
    assert "清潔" in vocabulary["home_cleaning"]
    assert all(isinstance(terms, list) and terms for terms in vocabulary.values())


def test_capability_wiki_answers_father_day_service_query():
    answer = WikiService(Path("docs/knowledge")).answer("product-help", "父親節")

    assert answer["citations"]
    assert "清潔" in answer["answer"]
    assert "團購" in answer["answer"]
