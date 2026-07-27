"""規劃器：LLM 拆解、規則執行（ADR-0017）。

這裡用假 LLM 餵出各種「模型會犯的錯」，驗證規則層真的擋得住：
幻覺出的能力、越權的能力、亂填的參數、發散成八個步驟。
擋不住的話，LLM 規劃就從功能變成漏洞。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from agent.planner import MAX_STEPS, Planner
from core.community.group_buy import SqliteGroupBuyRepository
from core.inquiries import SqliteInquiryRepository
from core.services import LifeServicesService
from core.tools.catalog import build_registry
from core.tools.registry import ToolContext

TODAY = date(2026, 7, 27)
FEEDBACK = {"data": [{"type": "3", "topicId": 1, "answerList": [{"answer": "燈具／開關", "answerId": 1071}]}]}


class FakeLlm:
    """回傳預先寫好的規劃結果；也可以設定成拋錯，用來測降級。"""

    def __init__(self, payload=None, *, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.prompts: list[list[dict]] = []

    def json(self, messages):
        self.prompts.append(messages)
        if self.error is not None:
            raise self.error
        return self.payload

    def complete(self, messages):  # pragma: no cover - 規劃器只用 json()
        return json.dumps(self.payload, ensure_ascii=False)


@pytest.fixture
def services(tmp_path: Path) -> LifeServicesService:
    repository = SqliteInquiryRepository(
        tmp_path / "inquiries.sqlite3",
        now=lambda: datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    return LifeServicesService(repository, today=TODAY)


@pytest.fixture
def group_buys(tmp_path: Path) -> SqliteGroupBuyRepository:
    return SqliteGroupBuyRepository(tmp_path / "groupbuys.sqlite3")


@pytest.fixture
def registry(services, group_buys):
    return build_registry(services=services, group_buys=group_buys, today=TODAY)


@pytest.fixture
def resident() -> ToolContext:
    return ToolContext(account_id="A001", role="user", display_name="王小明")


def _planner(registry, payload=None, *, error=None) -> tuple[Planner, FakeLlm]:
    llm = FakeLlm(payload, error=error)
    return Planner(llm, registry), llm


# ---- 多意圖：這是規劃器存在的理由 ---------------------------------------

def test_splits_one_sentence_into_multiple_intents(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "冷氣要清洗，順便看團購",
            "steps": [
                {"tool": "get_service_form", "arguments": {"service_id": "service-aircon"}, "why": "要問清楚冷氣狀況"},
                {"tool": "list_group_buys", "arguments": {"status": "open"}, "why": "看目前有什麼團"},
            ],
        },
    )
    plan = planner.plan("冷氣不冷想找人洗，然後這個月社區有團購嗎", resident)

    assert plan.rejected_reason is None
    assert [step.tool for step in plan.steps] == ["get_service_form", "list_group_buys"]
    assert all(step.status == "ready" for step in plan.steps)


def test_executes_read_only_steps_and_returns_real_results(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "看有什麼服務",
            "steps": [{"tool": "list_services", "arguments": {}, "why": "列出服務"}],
        },
    )
    plan = planner.execute(planner.plan("你們有什麼服務", resident), resident)

    assert plan.steps[0].status == "done"
    assert any(service["id"] == "service-aircon" for service in plan.steps[0].result)


# ---- 規則把關：模型會犯的錯 ---------------------------------------------

def test_rejects_the_whole_plan_when_a_tool_does_not_exist(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "退款",
            "steps": [
                {"tool": "list_services", "arguments": {}, "why": "看服務"},
                {"tool": "refund_everything", "arguments": {}, "why": "幻覺出來的能力"},
            ],
        },
    )
    plan = planner.plan("我要退費", resident)

    assert plan.is_empty, "一步不合法就該整份作廢，不能只做前半段"
    assert "不存在的能力" in (plan.rejected_reason or "")


def test_rejects_a_plan_that_uses_a_tool_the_role_may_not_call(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "開團",
            "steps": [
                {"tool": "open_group_buy", "arguments": {"title": "米", "item_name": "池上米", "unit_price": 350}, "why": "開團"}
            ],
        },
    )
    plan = planner.plan("幫我開一團池上米", resident)

    assert plan.is_empty
    assert "無法使用" in (plan.rejected_reason or "")


def test_rejects_a_plan_with_invalid_arguments(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "跟團",
            "steps": [{"tool": "join_group_buy", "arguments": {"campaign_id": 1}, "why": "少了份數"}],
        },
    )
    plan = planner.plan("我要跟團", resident)

    assert plan.is_empty
    assert "參數不正確" in (plan.rejected_reason or "")


def test_rejects_a_plan_that_tries_to_read_someone_elses_data(registry, resident):
    """身分參數不在 schema 裡，所以這種嘗試會在參數驗證就被擋下。"""
    planner, _ = _planner(
        registry,
        {
            "understanding": "看別人的單",
            "steps": [{"tool": "list_my_inquiries", "arguments": {"account_id": "B002"}, "why": "越權"}],
        },
    )
    plan = planner.plan("看看 B002 的委託", resident)

    assert plan.is_empty
    assert "參數不正確" in (plan.rejected_reason or "")


def test_rejects_a_guessed_service_id(registry, resident):
    """實測 Gemma 會把 service-cleaning 簡寫成 cleaning。

    這種值型別合法、只是不存在，若不在規劃階段擋下，就會變成
    「第一步做完了、第二步才發現服務不存在」的半套狀態。
    """
    planner, _ = _planner(
        registry,
        {
            "understanding": "找清潔",
            "steps": [{"tool": "match_vendors", "arguments": {"service_id": "cleaning"}, "why": "媒合"}],
        },
    )
    plan = planner.plan("幫我找清潔阿姨", resident)

    assert plan.is_empty
    assert "參數不正確" in (plan.rejected_reason or "")


def test_rejects_an_empty_string_where_a_value_is_required(registry, resident):
    """實測 Gemma 會在「知道要填但不知道填什麼」時給空字串。"""
    planner, _ = _planner(
        registry,
        {
            "understanding": "媒合",
            "steps": [{"tool": "match_vendors", "arguments": {"service_id": "", "district": "大同區"}, "why": "媒合"}],
        },
    )
    plan = planner.plan("水管漏水找人修", resident)

    assert plan.is_empty
    assert "參數不正確" in (plan.rejected_reason or "")


def test_the_prompt_gives_the_model_the_service_codes_so_it_need_not_guess(registry, resident):
    """計畫一次產生，第二步看不到第一步的結果——代碼必須事先給。"""
    planner, llm = _planner(registry, {"understanding": "", "steps": []})
    planner.plan("冷氣壞了", resident)

    prompt = llm.prompts[0][1]["content"]
    assert "service-aircon" in prompt
    assert "service-cleaning" in prompt


def test_the_prompt_lists_allowed_values_for_enum_parameters(registry, resident):
    """否則模型會寫 slot="週末"，讓一個合理需求因為列舉值而整份作廢。"""
    planner, llm = _planner(registry, {"understanding": "", "steps": []})
    planner.plan("找人打掃", resident)

    prompt = llm.prompts[0][1]["content"]
    assert "weekend" in prompt
    assert "evening" in prompt


def test_rejects_a_plan_that_sprawls_beyond_the_step_ceiling(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "發散",
            "steps": [{"tool": "list_services", "arguments": {}, "why": f"第 {i} 步"} for i in range(MAX_STEPS + 1)],
        },
    )
    plan = planner.plan("幫我把所有事情都做一做", resident)

    assert plan.is_empty
    assert "步驟過多" in (plan.rejected_reason or "")


def test_deduplicates_repeated_identical_steps_instead_of_failing(registry, resident):
    """模型常把同一件事列兩次；這是冗贅不是錯誤，去重就好。"""
    planner, _ = _planner(
        registry,
        {
            "understanding": "看服務",
            "steps": [
                {"tool": "list_services", "arguments": {}, "why": "列出服務"},
                {"tool": "list_services", "arguments": {}, "why": "再列一次"},
            ],
        },
    )
    plan = planner.plan("有什麼服務", resident)

    assert len(plan.steps) == 1
    assert plan.rejected_reason is None


# ---- 寫入動作一律先問 ---------------------------------------------------

def test_write_steps_wait_for_confirmation_instead_of_running(registry, group_buys, resident):
    campaign = group_buys.create_campaign(title="中秋", item_name="文旦", unit_price=300)
    planner, _ = _planner(
        registry,
        {
            "understanding": "跟團兩份",
            "steps": [
                {"tool": "join_group_buy", "arguments": {"campaign_id": campaign["id"], "quantity": 2}, "why": "跟團"}
            ],
        },
    )
    plan = planner.execute(planner.plan("幫我跟中秋那團，兩份", resident), resident)

    assert plan.steps[0].status == "needs_confirmation"
    assert group_buys.get_campaign(campaign["id"])["totalQuantity"] == 0, "沒點頭就不該真的跟團"


def test_a_confirmed_write_step_actually_runs(registry, group_buys, resident):
    campaign = group_buys.create_campaign(title="中秋", item_name="文旦", unit_price=300)
    planner, _ = _planner(
        registry,
        {
            "understanding": "跟團兩份",
            "steps": [
                {"tool": "join_group_buy", "arguments": {"campaign_id": campaign["id"], "quantity": 2}, "why": "跟團"}
            ],
        },
    )
    plan = planner.plan("幫我跟中秋那團，兩份", resident)
    plan = planner.execute(plan, resident, approved={0})

    assert plan.steps[0].status == "done"
    assert group_buys.get_campaign(campaign["id"])["totalQuantity"] == 2


def test_confirming_one_write_does_not_approve_another(registry, group_buys, resident):
    first = group_buys.create_campaign(title="中秋", item_name="文旦", unit_price=300)
    second = group_buys.create_campaign(title="年節", item_name="烏魚子", unit_price=1200)
    planner, _ = _planner(
        registry,
        {
            "understanding": "兩團都跟",
            "steps": [
                {"tool": "join_group_buy", "arguments": {"campaign_id": first["id"], "quantity": 1}, "why": "文旦"},
                {"tool": "join_group_buy", "arguments": {"campaign_id": second["id"], "quantity": 1}, "why": "烏魚子"},
            ],
        },
    )
    plan = planner.plan("兩團都幫我跟", resident)
    plan = planner.execute(plan, resident, approved={0})

    assert plan.steps[0].status == "done"
    assert plan.steps[1].status == "needs_confirmation"
    assert group_buys.get_campaign(second["id"])["totalQuantity"] == 0


# ---- 降級：失敗要說實話 -------------------------------------------------

def test_degrades_with_a_reason_when_the_llm_fails(registry, resident):
    planner, _ = _planner(registry, error=RuntimeError("connection reset"))
    plan = planner.plan("冷氣壞了", resident)

    assert plan.is_empty
    assert plan.rejected_reason == "規劃暫時無法使用"


def test_degrades_when_the_llm_returns_nonsense(registry, resident):
    planner, _ = _planner(registry, "我不知道")
    plan = planner.plan("冷氣壞了", resident)

    assert plan.is_empty
    assert plan.rejected_reason == "規劃結果格式不正確"


def test_empty_input_is_rejected_without_calling_the_llm(registry, resident):
    planner, llm = _planner(registry, {"understanding": "", "steps": []})
    plan = planner.plan("   ", resident)

    assert plan.is_empty
    assert llm.prompts == [], "空輸入不該浪費一次 LLM 呼叫"


def test_a_failing_step_reports_the_error_rather_than_crashing(registry, resident):
    planner, _ = _planner(
        registry,
        {
            "understanding": "看不存在的團",
            "steps": [{"tool": "list_group_buys", "arguments": {}, "why": "看團"},
                      {"tool": "get_inquiry", "arguments": {"inquiry_id": "INQ-不存在"}, "why": "查單"}],
        },
    )
    plan = planner.execute(planner.plan("看看團購和我的單", resident), resident)

    assert plan.steps[0].status == "done"
    assert plan.steps[1].status == "failed"
    assert "查無諮詢單" in (plan.steps[1].error or "")


# ---- 提示詞只給該身分看得到的能力 ---------------------------------------

def test_the_prompt_only_offers_tools_the_current_role_may_use(registry, resident):
    planner, llm = _planner(registry, {"understanding": "", "steps": []})
    planner.plan("隨便問問", resident)

    prompt = llm.prompts[0][1]["content"]
    assert "list_my_inquiries" in prompt
    assert "open_group_buy" not in prompt, "住戶的提示詞不該出現管委會的能力"
    assert "submit_quote" not in prompt
