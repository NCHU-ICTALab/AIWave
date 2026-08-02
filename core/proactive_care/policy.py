"""Versioned delivery policy for the future non-Demo care preferences.

The competition Demo intentionally does not expose a settings screen.  This
module still makes the formal policy executable and testable before a future
preference API is added.  Transaction notifications use a separate counter
and are not throttled by the general-care frequency window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterable, Literal


class CarePolicyError(ValueError):
    pass


CareMode = Literal["quiet", "balanced", "caring"]
Frequency = Literal["off", "low", "normal", "high"]


@dataclass(frozen=True)
class CarePreferences:
    mode: CareMode = "balanced"
    channel: Literal["in_app", "push", "email"] = "in_app"
    quiet_start: time = time(22, 0)
    quiet_end: time = time(8, 0)
    category_overrides: dict[str, Frequency] = field(default_factory=dict)

    def frequency_for(self, category: str) -> Frequency:
        override = self.category_overrides.get(category)
        if override is not None:
            return override
        return {"quiet": "low", "balanced": "normal", "caring": "high"}[self.mode]  # type: ignore[return-value]


@dataclass(frozen=True)
class CareDeliveryDecision:
    allowed: bool
    reason: str
    next_eligible_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "nextEligibleAt": self.next_eligible_at,
        }


_FREQUENCY_WINDOWS: dict[Frequency, tuple[int, int]] = {
    "off": (0, 0),
    "low": (1, 30),
    "normal": (1, 7),
    "high": (3, 1),
}
_ALLOWED_SOURCES = {
    "public_calendar",
    "explicit_calendar",
    "explicit_address",
    "competition_demo_event",
}


def evaluate_delivery(
    candidate: dict[str, Any],
    *,
    preferences: CarePreferences,
    now: datetime,
    recent_deliveries: Iterable[dict[str, Any]] = (),
) -> CareDeliveryDecision:
    """Return a deterministic delivery decision without writing state."""

    if preferences.mode not in {"quiet", "balanced", "caring"}:
        raise CarePolicyError("不支援的關懷模式")
    if preferences.channel not in {"in_app", "push", "email"}:
        raise CarePolicyError("不支援的關懷送達方式")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    category = str(candidate.get("kind") or "general")
    if category == "transaction":
        return CareDeliveryDecision(True, "transaction_counter_is_separate")

    evidence = candidate.get("evidence") or {}
    source = str(evidence.get("source") or "")
    if source not in _ALLOWED_SOURCES:
        return CareDeliveryDecision(False, "source_not_allowlisted")

    frequency = preferences.frequency_for(category)
    count, days = _FREQUENCY_WINDOWS[frequency]
    if count == 0:
        return CareDeliveryDecision(False, "category_disabled")

    if preferences.channel != "in_app" and _in_quiet_hours(now, preferences.quiet_start, preferences.quiet_end):
        next_time = _next_quiet_end(now, preferences.quiet_start, preferences.quiet_end)
        return CareDeliveryDecision(False, "quiet_hours", next_time.isoformat())

    cutoff = now - timedelta(days=days)
    matching = []
    for item in recent_deliveries:
        if str(item.get("kind") or item.get("category") or "general") != category:
            continue
        sent_at = _parse_datetime(item.get("deliveredAt") or item.get("sentAt"))
        if sent_at and sent_at >= cutoff:
            matching.append(sent_at)
    if len(matching) >= count:
        next_eligible = min(matching) + timedelta(days=days)
        return CareDeliveryDecision(False, "frequency_limit", next_eligible.isoformat())
    return CareDeliveryDecision(True, "eligible")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _in_quiet_hours(value: datetime, start: time, end: time) -> bool:
    current = value.timetz().replace(tzinfo=None)
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _next_quiet_end(value: datetime, start: time, end: time) -> datetime:
    if start < end:
        candidate = value.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        return candidate if candidate > value else candidate + timedelta(days=1)
    if value.timetz().replace(tzinfo=None) < end:
        return value.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return (value + timedelta(days=1)).replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
