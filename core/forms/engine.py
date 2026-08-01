"""題組引擎（確定性核心）。

職責：讀表單定義 → 依序選出下一題（含跳題）→ 驗證答案 → 累積 → 產出官方
`feedback_content`（answerList 格式）。**不含 LLM**：口語解析與問句潤飾由上層
Agent 負責，本層只做確定性的流程與驗證，方便 pytest 測到綠。

見 docs/specs/03-form-engine.md。
"""

from __future__ import annotations

from datetime import date

from .models import (
    CHOICE_TYPES,
    CONTACT_TYPES,
    TEXT_TYPES,
    Form,
    Region,
    Selection,
    Topic,
    TopicType,
)


class FormError(ValueError):
    """答案驗證或流程錯誤。"""


class FormSession:
    """一份表單的填答工作階段。

    參數：
        form:   表單定義。
        known:  已知答案（如聯絡資料由 resident 帶入），{topic_id: value}。
        today:  日期題範圍檢查的基準日；None 則不檢查範圍（保持確定性測試友善）。
    """

    def __init__(
        self,
        form: Form,
        known: dict[int, object] | None = None,
        today: date | None = None,
    ) -> None:
        self.form = form
        self.today = today
        self.answers: dict[int, object] = {}
        self._skipped: set[int] = set()
        if known:
            for topic_id, value in known.items():
                self.submit_answer(topic_id, value)

    # ---- 流程 ----------------------------------------------------------

    def _selected_ids(self, value: object) -> set[int]:
        """從已正規化的答案取出被選 option id（供跳題判斷）。"""
        if isinstance(value, list) and value and isinstance(value[0], Selection):
            return {s.option_id for s in value}
        return set()

    @property
    def skipped_ids(self) -> set[int]:
        """已略過的題目。

        跨請求重建工作階段時要一併還原（見 `core.sessions`）——只還原答案的話，
        使用者略過的題目會被重新問一次。
        """
        return set(self._skipped)

    def mark_skipped(self, topic_id: int) -> None:
        """還原略過紀錄，不重跑 `skip()` 的驗證。

        與 `skip()` 的差別：`skip()` 是使用者當下的動作，必須擋下「略過必填題」；
        這裡處理的是**已經發生過**的略過，重播時題目可見性可能因為後續答案而改變，
        再驗一次只會製造假錯誤。
        """
        self._skipped.add(topic_id)

    def is_visible(self, topic: Topic) -> bool:
        """跳題判斷：無 skip_logic 一律顯示；有則依賴題答案須命中。"""
        sl = topic.skip_logic
        if sl is None:
            return True
        dep = self.answers.get(sl.topic_id)
        if dep is None:
            return False
        return bool(self._selected_ids(dep) & set(sl.answer_in))

    def next_topic(self) -> Topic | None:
        """回傳下一個「可見、未答、未略過」的題目；沒有則 None。"""
        for t in self.form.ordered_topics():
            if self.is_visible(t) and t.id not in self.answers and t.id not in self._skipped:
                return t
        return None

    def progress(self) -> dict[str, int]:
        """Return visible completion progress, counting explicit optional skips."""
        visible = [topic for topic in self.form.ordered_topics() if self.is_visible(topic)]
        completed = sum(topic.id in self.answers or topic.id in self._skipped for topic in visible)
        return {"answered": completed, "total": len(visible)}

    def skip(self, topic_id: int) -> Topic | None:
        """略過一個選填題（必填題不可略過），回傳下一題。"""
        topic = self.form.topic(topic_id)
        if topic is None:
            raise FormError(f"表單無此題目：{topic_id}")
        if topic.is_required:
            raise FormError(f"「{topic.title}」為必填，不可略過")
        if not self.is_visible(topic):
            raise FormError(f"題目 {topic_id} 目前不可見")
        self._skipped.add(topic_id)
        return self.next_topic()

    def is_complete(self) -> bool:
        """所有「可見且必填」的題目都答了即完成。"""
        for t in self.form.ordered_topics():
            if self.is_visible(t) and t.is_required and t.id not in self.answers:
                return False
        return True

    def submit_answer(self, topic_id: int, value: object) -> Topic | None:
        """驗證並記錄一題答案，回傳下一題（或 None）。"""
        topic = self.form.topic(topic_id)
        if topic is None:
            raise FormError(f"表單無此題目：{topic_id}")
        if not self.is_visible(topic):
            raise FormError(f"題目 {topic_id} 目前不該出現（跳題條件未滿足）")
        self.answers[topic_id] = self._validate(topic, value)
        return self.next_topic()

    # ---- 驗證 ----------------------------------------------------------

    def _validate(self, topic: Topic, value: object) -> object:
        t = topic.type
        if t in TEXT_TYPES:
            return self._validate_text(topic, value)
        if t in CHOICE_TYPES:
            return self._validate_choice(topic, value)
        if t is TopicType.REGION:
            return self._validate_region(topic, value)
        if t is TopicType.PHOTO:
            return self._validate_photo(topic, value)
        if t is TopicType.DATE:
            return self._validate_date(topic, value)
        if t in CONTACT_TYPES:
            return self._validate_contact(topic, value)
        raise FormError(f"未支援的題型：{t}")

    def _require(self, topic: Topic, empty: bool) -> None:
        if topic.is_required and empty:
            raise FormError(f"「{topic.title}」為必填")

    def _validate_text(self, topic: Topic, value: object) -> str:
        text = "" if value is None else str(value).strip()
        self._require(topic, text == "")
        if text and topic.is_number_only and not text.isdigit():
            raise FormError(f"「{topic.title}」僅能填數字")
        return text

    def _coerce_selection(self, value: object) -> Selection:
        if isinstance(value, Selection):
            return value
        if isinstance(value, int):
            return Selection(option_id=value)
        if isinstance(value, dict):
            return Selection(**value)
        raise FormError(f"無法解析選項答案：{value!r}")

    def _validate_choice(self, topic: Topic, value: object) -> list[Selection]:
        if value is None:
            items: list[object] = []
        elif topic.type is TopicType.MULTI:
            items = list(value) if isinstance(value, (list, tuple)) else [value]
        else:  # SINGLE
            items = list(value) if isinstance(value, (list, tuple)) else [value]
            if len(items) > 1:
                raise FormError(f"「{topic.title}」為單選")
        self._require(topic, len(items) == 0)

        result: list[Selection] = []
        for raw in items:
            sel = self._coerce_selection(raw)
            opt = topic.option(sel.option_id)
            if opt is None:
                raise FormError(f"「{topic.title}」無此選項：{sel.option_id}")
            if opt.is_quantity:
                lo = opt.min_quantity or 1
                hi = opt.max_quantity
                if sel.quantity is None:
                    raise FormError(f"「{opt.option_name}」需填數量")
                if sel.quantity < lo or (hi is not None and sel.quantity > hi):
                    raise FormError(
                        f"「{opt.option_name}」數量須介於 {lo}–{hi if hi is not None else '∞'}"
                    )
            else:
                sel = Selection(option_id=sel.option_id, quantity=None)
            result.append(sel)
        return result

    def _validate_region(self, topic: Topic, value: object) -> Region:
        if value is None:
            self._require(topic, True)
        region = value if isinstance(value, Region) else Region(**value)  # type: ignore[arg-type]
        if not region.county_code or not region.district_code:
            raise FormError(f"「{topic.title}」需含縣市與行政區")
        return region

    def _validate_photo(self, topic: Topic, value: object) -> list[str]:
        urls = list(value) if isinstance(value, (list, tuple)) else ([] if value is None else [value])
        urls = [str(u) for u in urls]
        self._require(topic, len(urls) == 0)
        if topic.max_media is not None and len(urls) > topic.max_media:
            raise FormError(f"「{topic.title}」最多 {topic.max_media} 張")
        min_media = topic.min_media or (1 if topic.is_required else 0)
        if topic.is_required and len(urls) < min_media:
            raise FormError(f"「{topic.title}」至少 {min_media} 張")
        return urls

    def _validate_date(self, topic: Topic, value: object) -> str:
        raw = "" if value is None else str(value).strip()
        self._require(topic, raw == "")
        if not raw:
            return raw
        try:
            d = date.fromisoformat(raw)
        except ValueError as exc:
            raise FormError(f"「{topic.title}」日期格式須為 YYYY-MM-DD") from exc
        if self.today is not None:
            lo = self.today.toordinal() + (topic.start_date_offset_days or 0)
            if d.toordinal() < lo:
                raise FormError(f"「{topic.title}」日期過早")
            if topic.end_date_offset_days is not None:
                hi = self.today.toordinal() + topic.end_date_offset_days
                if d.toordinal() > hi:
                    raise FormError(f"「{topic.title}」日期超出範圍")
        return d.isoformat()

    def _validate_contact(self, topic: Topic, value: object) -> dict:
        data = dict(value) if isinstance(value, dict) else {}
        self._require(topic, not data)
        if data:
            required = ("name", "mobile", "address") if topic.type is TopicType.CONTACT else ("name", "mobile")
            missing = [key for key in required if not str(data.get(key, "")).strip()]
            if missing:
                labels = {"name": "姓名", "mobile": "電話", "address": "地址"}
                raise FormError(f"「{topic.title}」缺少{'、'.join(labels[key] for key in missing)}")
        return data

    # ---- 輸出 ----------------------------------------------------------

    def to_feedback_content(self) -> dict:
        """產出官方 pms_form_feedback.feedback_content 格式（answerList）。"""
        data: list[dict] = []
        for t in self.form.ordered_topics():
            if not self.is_visible(t) or t.id not in self.answers:
                continue
            data.append(
                {
                    "type": t.type.value,
                    "topicId": t.id,
                    "answerList": self._answer_list(t, self.answers[t.id]),
                }
            )
        return {"data": data}

    def _answer_list(self, topic: Topic, value: object) -> list[dict]:
        t = topic.type
        if t in CHOICE_TYPES:
            out = []
            for i, sel in enumerate(value, start=1):  # type: ignore[arg-type]
                opt = topic.option(sel.option_id)
                assert opt is not None
                if opt.parent_id is not None:
                    parent = topic.option(opt.parent_id)
                    answer = f"{parent.option_name}-{opt.option_name}" if parent else opt.option_name
                else:
                    answer = opt.option_name
                out.append(
                    _entry(
                        sort=i,
                        title=opt.option_name,
                        answer=answer,
                        answerId=opt.id,
                        quantity=sel.quantity,
                    )
                )
            return out
        if t is TopicType.REGION:
            r: Region = value  # type: ignore[assignment]
            return [
                _entry(
                    answer=None,
                    countyCode=r.county_code,
                    countyName=r.county_name,
                    districtCode=r.district_code,
                    districtName=r.district_name,
                )
            ]
        if t is TopicType.PHOTO:
            return [_entry(answer=None, imgUrl=list(value))]  # type: ignore[arg-type]
        if t in CONTACT_TYPES:
            return [_entry(answer=None, **value)]  # type: ignore[arg-type]
        # 文字 / 日期
        return [_entry(answer=value)]


_ENTRY_KEYS = (
    "sort",
    "title",
    "answer",
    "answerId",
    "quantity",
    "imgUrl",
    "countyCode",
    "countyName",
    "districtCode",
    "districtName",
    "remark",
)


def _entry(**kw: object) -> dict:
    """組一筆 answerList 條目，未給的官方欄位補 None，額外欄位（如聯絡資料）保留。"""
    entry = {k: kw.get(k) for k in _ENTRY_KEYS}
    for k, v in kw.items():
        if k not in entry:
            entry[k] = v
    return entry
