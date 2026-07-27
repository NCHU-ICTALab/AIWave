"""規劃器：LLM 拆解需求成計畫，規則負責執行（[ADR-0017]）。

這是「Agent 一點都不智慧」那項回饋的答案。先前全系統只有兩個 LLM 呼叫點
（意圖分類、欄位抽取），使用者說一句話只會得到一張表單；說兩件事只會處理第一件。

分工不變，只是層級提高了：

- **LLM 負責規劃**——把一句口語拆成「要做哪幾件事、各自該呼叫哪個能力、為什麼」。
  這是模型真正擅長的：處理「冷氣不冷，順便看看這個月團購」這種一句話兩件事。
- **規則負責執行**——工具存不存在、角色能不能用、參數合不合法，全部由
  `ToolRegistry` 判定。模型講錯，計畫就作廢，不會有半套的副作用。

三條刻意的紀律：

1. **整份計畫要嘛全過、要嘛作廢。** 任何一步驗證不過就不執行任何一步——
   免得使用者看到「第一件事做好了，第二件事失敗了」這種收不了尾的中間狀態。
2. **寫入動作一律先問。** `writes=True` 的步驟只會被列出來等使用者確認，
   規劃器自己絕不直接執行（延續 [ADR-0008] 權限受控的 Copilot）。
3. **失敗要說實話。** LLM 掛掉或亂答時回傳空計畫與原因，由呼叫端退回既有的
   單一意圖流程，不假裝理解。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.clients import LlmClient
from core.tools.registry import ToolContext, ToolError, ToolRegistry, validate_arguments

#: 一句話最多拆成幾件事——超過通常是模型在發散，不是使用者真的要做八件事
MAX_STEPS = 4

_SYSTEM = (
    "你是智慧社區生活管家的規劃器。使用者會用日常口語說出需求，"
    "你要判斷「要完成這件事需要依序呼叫哪些能力」，輸出一份計畫。\n"
    "規則：\n"
    "1. 只能使用提供的能力清單裡的名稱，不可自行發明。\n"
    "2. 一句話可能包含多件事，請全部拆出來，各自一個步驟。\n"
    "3. 參數必須符合該能力的 schema；不確定的參數就不要填。\n"
    "4. 使用者只是閒聊或需求不明時，steps 給空陣列。\n"
    "5. 不要在計畫裡重複同一個能力做同一件事。\n"
    "只輸出一個 JSON 物件，不要多餘文字或程式碼區塊。\n"
    'schema：{"understanding":"<20 字內中文，複述你理解的需求>",'
    '"steps":[{"tool":"<能力名稱>","arguments":{},"why":"<15 字內中文，為什麼要做這步>"}]}'
)


@dataclass
class PlanStep:
    """計畫中的一步。"""

    tool: str
    arguments: dict[str, Any]
    why: str
    writes: bool
    #: ready（可執行）｜needs_confirmation（等使用者點頭）｜done｜failed
    status: str = "ready"
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "why": self.why,
            "writes": self.writes,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class Plan:
    """一次規劃的結果。步驟為空時，`rejected_reason` 一定說得出原因。"""

    understanding: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    rejected_reason: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.steps

    @property
    def needs_confirmation(self) -> list[PlanStep]:
        return [step for step in self.steps if step.status == "needs_confirmation"]

    def to_dict(self) -> dict:
        return {
            "understanding": self.understanding,
            "steps": [step.to_dict() for step in self.steps],
            "rejectedReason": self.rejected_reason,
            "needsConfirmation": [step.to_dict() for step in self.needs_confirmation],
        }


class Planner:
    def __init__(self, llm: LlmClient, registry: ToolRegistry) -> None:
        self.llm = llm
        self.registry = registry

    # ---- 規劃 ----------------------------------------------------------

    def plan(self, utterance: str, context: ToolContext) -> Plan:
        """把一句口語拆成計畫。任何一步不合法，整份計畫作廢。"""
        text = (utterance or "").strip()
        if not text:
            return Plan(rejected_reason="沒有收到需求內容")

        try:
            raw = self.llm.json([
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": self._prompt(text, context)},
            ])
        except Exception:  # noqa: BLE001 — 規劃失敗要退回既有流程，不能中斷對話
            return Plan(rejected_reason="規劃暫時無法使用")

        if not isinstance(raw, dict):
            return Plan(rejected_reason="規劃結果格式不正確")

        understanding = str(raw.get("understanding") or "").strip()
        raw_steps = raw.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return Plan(understanding=understanding, rejected_reason="沒有可執行的步驟")

        if len(raw_steps) > MAX_STEPS:
            return Plan(understanding=understanding, rejected_reason="計畫步驟過多，已作廢")

        steps: list[PlanStep] = []
        seen: set[tuple[str, str]] = set()
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                return Plan(understanding=understanding, rejected_reason="計畫格式不正確")

            name = raw_step.get("tool")
            tool = self.registry.get(name) if isinstance(name, str) else None
            if tool is None:
                return Plan(understanding=understanding, rejected_reason=f"計畫用到不存在的能力：{name}")
            if not tool.allows(context.role):
                return Plan(understanding=understanding, rejected_reason=f"目前身分無法使用「{tool.name}」")

            arguments = raw_step.get("arguments") or {}
            try:
                cleaned = validate_arguments(tool.parameters, arguments)
            except ToolError as error:
                return Plan(understanding=understanding, rejected_reason=f"「{tool.name}」的參數不正確：{error}")

            fingerprint = (tool.name, repr(sorted(cleaned.items())))
            if fingerprint in seen:
                continue   # 模型偶爾會把同一件事列兩次；去重即可，不必因此作廢整份計畫
            seen.add(fingerprint)

            steps.append(
                PlanStep(
                    tool=tool.name,
                    arguments=cleaned,
                    why=str(raw_step.get("why") or "").strip(),
                    writes=tool.writes,
                    status="needs_confirmation" if tool.writes else "ready",
                )
            )

        if not steps:
            return Plan(understanding=understanding, rejected_reason="沒有可執行的步驟")
        return Plan(understanding=understanding, steps=steps)

    # ---- 執行 ----------------------------------------------------------

    def execute(self, plan: Plan, context: ToolContext, *, approved: set[int] | None = None) -> Plan:
        """執行計畫中已就緒的步驟。

        `approved` 是使用者已點頭的步驟索引；沒有被點頭的寫入步驟會原地留著等確認，
        不會因為「順便」就被執行掉。
        """
        approved = approved or set()
        for index, step in enumerate(plan.steps):
            if step.status == "done":
                continue
            if step.writes and index not in approved:
                step.status = "needs_confirmation"
                continue
            try:
                step.result = self.registry.call(step.tool, step.arguments, context)
                step.status = "done"
                step.error = None
            except Exception as error:  # noqa: BLE001 — 逐步回報，讓使用者知道哪一步卡住
                step.status = "failed"
                step.error = str(error)
        return plan

    # ---- 提示詞 --------------------------------------------------------

    def _prompt(self, utterance: str, context: ToolContext) -> str:
        lines = []
        for tool in self.registry.list(role=context.role):
            params = ", ".join(
                f"{name}:{spec.get('type')}" for name, spec in tool.parameters.get("properties", {}).items()
            )
            required = tool.parameters.get("required") or []
            signature = f"（參數：{params}；必填：{'、'.join(required) or '無'}）" if params else "（無參數）"
            lines.append(f"- {tool.name}{signature}：{tool.description}")
        catalog = "\n".join(lines)
        who = "已登入" if context.account_id else "尚未登入（需要身分的能力不可用）"
        return f"能力清單：\n{catalog}\n\n使用者身分：{context.role}，{who}\n使用者說：「{utterance}」"
