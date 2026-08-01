"""填單 Agent：把口語映射成題組引擎的結構化答案，並潤飾問句。

分工（見 03-form-engine.md）：確定性流程/驗證在 `core.forms.FormSession`；本層只做
LLM 口語理解與問句呈現。問句用模板（可靠、可測），抽取用 LLM（難的部分）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from core.clients import LlmClient
from core.data.regions import resolve as resolve_region
from core.forms.models import CONTACT_TYPES, TEXT_TYPES, Topic, TopicType

_EXTRACT_SYS = (
    "你是表單填答助理。根據『題目』與『使用者訊息』抽取結構化答案。"
    "只輸出一個 JSON 物件，不要多餘文字或說明。"
    'schema：{"action":"answer|skip|unclear","value":<依題型>,"note":"<給使用者的話>"}。'
    "使用者表達不清或答非所問時 action=unclear 並在 note 說明要問什麼；"
    "使用者表示沒有/不用/略過時 action=skip。"
)


@dataclass
class Interpretation:
    action: str            # answer | skip | unclear
    value: object = None
    note: str = ""


class FormAgent:
    def __init__(self, llm: LlmClient, today: date | None = None) -> None:
        self.llm = llm
        self.today = today or date.today()

    # ---- 問句（模板） -------------------------------------------------

    def question_text(self, topic: Topic) -> str:
        t = topic.type
        if t in (TopicType.SINGLE, TopicType.MULTI):
            lines = [f"　{i}. {o.option_name}" + ("（可填數量）" if o.is_quantity else "")
                     for i, o in enumerate(topic.options, 1) if o.parent_id is None]
            children = [o for o in topic.options if o.parent_id is not None]
            for c in children:
                parent = topic.option(c.parent_id)  # type: ignore[arg-type]
                lines.append(f"　- {parent.option_name if parent else ''}：{c.option_name}")
            hint = "（可複選）" if t is TopicType.MULTI else ""
            return f"請問{topic.title}？{hint}\n" + "\n".join(lines)
        if t is TopicType.REGION:
            return f"請問{topic.title}？例如「台中市西屯區」。"
        if t is TopicType.PHOTO:
            return f"可以上傳{topic.title}嗎？若沒有，回「沒有」即可。"
        if t is TopicType.DATE:
            return f"請問{topic.title}？（例如 2026-07-28，也可說「下週三」）"
        if t in CONTACT_TYPES:
            extra = "" if t is TopicType.CONTACT_NO_ADDR else "、地址"
            return f"請提供{topic.title}：姓名、電話{extra}。"
        if t in TEXT_TYPES:
            return f"請問{topic.title}？" + ("（請填數字）" if topic.is_number_only else "")
        return f"請問{topic.title}？"

    # ---- 抽取（LLM） --------------------------------------------------

    def interpret(self, topic: Topic, message: str) -> Interpretation:
        prompt = self._extract_prompt(topic, message)
        try:
            raw = self.llm.json([
                {"role": "system", "content": _EXTRACT_SYS},
                {"role": "user", "content": prompt},
            ])
        except Exception:  # noqa: BLE001 — provider/parse 失敗一律轉為安全的 unclear
            return Interpretation("unclear", note="AI 暫時無法解析這段內容，請換個說法再試一次。")
        if not isinstance(raw, dict):
            return Interpretation("unclear", note="我沒聽清楚，麻煩再說一次。")

        action = str(raw.get("action", "unclear"))
        note = str(raw.get("note", "") or "")
        if action == "skip":
            return Interpretation("skip", note=note)
        if action != "answer":
            return Interpretation("unclear", note=note or "麻煩再說明一下。")

        value = raw.get("value")
        # 地區題：LLM 給名稱，我方查官方碼
        if topic.type is TopicType.REGION:
            if not isinstance(value, dict):
                return Interpretation("unclear", note="請提供縣市與行政區。")
            r = resolve_region(str(value.get("district_name", "")), str(value.get("county_name") or "") or None)
            if r is None:
                return Interpretation("unclear", note="這個地區我對不上，能再說一次縣市和行政區嗎？")
            return Interpretation("answer", r, note)
        return Interpretation("answer", value, note)

    def _extract_prompt(self, topic: Topic, message: str) -> str:
        t = topic.type
        desc: list[str] = [f"題目：{topic.title}", f"題型：{t.name}"]
        if topic.options:
            opts = []
            for o in topic.options:
                s = f"{o.id}={o.option_name}"
                if o.parent_id is not None:
                    s += f"(子於{o.parent_id})"
                if o.is_quantity:
                    s += f"[可填數量{o.min_quantity or 1}-{o.max_quantity or '∞'}]"
                opts.append(s)
            desc.append("選項(id=名稱)：" + "、".join(opts))
        schema = self._value_schema(topic)
        desc.append("value 格式：" + schema)
        if t is TopicType.DATE:
            desc.append(f"今天是 {self.today.isoformat()}，相對日期請換算成 YYYY-MM-DD。")
        desc.append(f"使用者訊息：「{message}」")
        return "\n".join(desc)

    @staticmethod
    def _value_schema(topic: Topic) -> str:
        t = topic.type
        if t is TopicType.SINGLE:
            return '{"option_id":<id>,"quantity":<數量或null>}'
        if t is TopicType.MULTI:
            return '[{"option_id":<id>,"quantity":<數量或null>}, ...]'
        if t is TopicType.REGION:
            return '{"county_name":"<縣市>","district_name":"<行政區>"}'
        if t is TopicType.DATE:
            return '"YYYY-MM-DD"'
        if t in CONTACT_TYPES:
            if t is TopicType.CONTACT:
                return '{"name":"<姓名>","mobile":"<電話>","address":"<完整地址>"}'
            return '{"name":"<姓名>","mobile":"<電話>"}'
        if t is TopicType.PHOTO:
            return '[]（純文字無法上傳，通常回 skip）'
        return '"<文字，數字題請填純數字>"'

    # ---- 摘要（模板） -------------------------------------------------

    def summary_text(self, feedback_content: dict) -> str:
        parts = []
        for d in feedback_content.get("data", []):
            answers = []
            for a in d["answerList"]:
                if a.get("answer") is not None:
                    q = f"×{a['quantity']}" if a.get("quantity") else ""
                    answers.append(f"{a['answer']}{q}")
                elif a.get("districtName"):
                    answers.append(f"{a.get('countyName') or ''}{a['districtName']}")
                elif a.get("imgUrl"):
                    answers.append(f"{len(a['imgUrl'])} 張照片")
                elif a.get("name"):
                    contact = f"{a.get('name')} {a.get('mobile', '')}".strip()
                    if a.get("address"):
                        contact += f"・{a['address']}"
                    answers.append(contact)
            if answers:
                parts.append("・" + "、".join(answers))
        body = "\n".join(parts)
        return f"幫您確認以下內容：\n{body}\n沒問題的話我就送出囉，現在不會收費，之後才報價。"
