"""TimeResolver(spec 15 §4.2):以 Asia/Taipei 伺服器目前時間解析相對日期。

「明天」「下週三」由這裡裁決,不由 LLM 猜;結果一律附上可回顯的絕對日期字串,
讓確認畫面能明確顯示「8/1(六)」。完全確定性、可注入 now 供測試。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

TAIPEI = timezone(timedelta(hours=8))

_WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
_WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]


@dataclass(frozen=True)
class TimeResolution:
    """解析結果:date 為裁決出的絕對日期;echo 是給確認畫面的回顯字串。"""

    raw: str
    date: date | None
    echo: str | None
    #: 一段日期範圍(例如「這週末」);有值時 date 為範圍起點
    end_date: date | None = None

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "date": self.date.isoformat() if self.date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "echo": self.echo,
        }


class TimeResolver:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(TAIPEI))

    def today(self) -> date:
        return self._now().astimezone(TAIPEI).date()

    def _echo(self, value: date) -> str:
        return f"{value.month}/{value.day}(週{_WEEKDAY_NAMES[value.weekday()]})"

    def resolve(self, phrase: str) -> TimeResolution:
        text = phrase.strip()
        today = self.today()

        def hit(value: date, end: date | None = None) -> TimeResolution:
            echo = self._echo(value)
            if end is not None:
                echo = f"{echo}–{self._echo(end)}"
            return TimeResolution(raw=phrase, date=value, end_date=end, echo=echo)

        if not text:
            return TimeResolution(raw=phrase, date=None, echo=None)

        # 絕對日期:8/9、8月9日、2026-08-09
        iso = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", text)
        if iso:
            value = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
            return hit(value)
        md = re.search(r"(\d{1,2})\s*[/月]\s*(\d{1,2})\s*日?", text)
        if md:
            month, day = int(md.group(1)), int(md.group(2))
            year = today.year
            candidate = date(year, month, day)
            if candidate < today:  # 已過的日期視為明年同日(生活場景不會約過去)
                candidate = date(year + 1, month, day)
            return hit(candidate)

        # 相對詞
        if "今天" in text or "今晚" in text:
            return hit(today)
        if "明天" in text or "明晚" in text:
            return hit(today + timedelta(days=1))
        if "後天" in text:
            return hit(today + timedelta(days=2))

        weekend = "週末" in text or "周末" in text
        weekday_match = re.search(r"[週周星期禮拜]+([一二三四五六日天])", text)
        next_week = "下" in text

        if weekend:
            saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7 if next_week else (5 - today.weekday()) % 7)
            if not next_week and saturday < today:
                saturday += timedelta(days=7)
            if next_week and saturday <= today + timedelta(days=(6 - today.weekday())):
                saturday += timedelta(days=7)
            return hit(saturday, saturday + timedelta(days=1))

        if weekday_match:
            target = _WEEKDAYS[weekday_match.group(1)]
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7  # 「週三」說的當天已是週三 → 下一個週三
            value = today + timedelta(days=delta)
            if next_week:
                # 「下週三」= 下一個日曆週的週三
                days_to_next_monday = 7 - today.weekday()
                value = today + timedelta(days=days_to_next_monday + target)
            return hit(value)

        return TimeResolution(raw=phrase, date=None, echo=None)
