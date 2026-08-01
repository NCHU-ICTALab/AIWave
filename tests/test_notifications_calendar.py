from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.calendar import CalendarConflict, SqliteCalendarRepository
from core.notifications import NotificationError, SqliteNotificationRepository


OWNER = {"demo_workspace_id": "demo-a", "workspace_id": "workspace-a", "account_id": "a"}


def test_notifications_are_persistent_scoped_readable_and_respect_quiet_hours(tmp_path):
    repository = SqliteNotificationRepository(
        tmp_path / "platform.sqlite3",
        now=lambda: datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc),  # 23:00 Taipei
    )
    notification = repository.publish(
        **OWNER, scope_type="personal", scope_id="a", category="booking_status",
        title="預約已確認", body="王子水電已確認時段", deep_link="/orders/booking-a",
        subject_type="booking", subject_id="booking-a", idempotency_key="notify-once",
    )
    repository.set_quiet_hours("a", start="22:00", end="07:00")
    listed = repository.list_owned(**OWNER)
    assert listed["unreadCount"] == 1
    assert listed["quietHoursActive"] is True
    assert repository.mark_read(notification["id"], **OWNER)["readAt"] is not None
    with pytest.raises(NotificationError, match="查無通知"):
        repository.mark_read(
            notification["id"], demo_workspace_id="demo-b", workspace_id="workspace-b", account_id="b",
        )


def test_calendar_manual_recurrence_modes_and_booking_protection(tmp_path):
    repository = SqliteCalendarRepository(tmp_path / "platform.sqlite3")
    manual = repository.create_manual(
        **OWNER, scope_type="personal", scope_id="a", title="每週採買",
        starts_at="2026-08-01T09:00:00+08:00", ends_at="2026-08-01T10:00:00+08:00",
        all_day=False, note=None, recurrence={"frequency": "weekly", "interval": 1},
        idempotency_key="manual-once",
    )
    this_only = repository.change_manual_series(
        manual["id"], **OWNER, mode="this", occurrence_start="2026-08-08T09:00:00+08:00",
        changes={"title": "本週改為補貨"}, idempotency_key="change-this",
    )
    future = repository.change_manual_series(
        manual["id"], **OWNER, mode="future", occurrence_start="2026-08-15T09:00:00+08:00",
        changes={"title": "未來採買", "starts_at": "2026-08-15T10:00:00+08:00"},
        idempotency_key="change-future",
    )
    assert this_only["exceptions"][0]["payload"]["title"] == "本週改為補貨"
    assert future["seriesParentId"] == manual["id"]

    booking = repository.upsert_projection(
        **OWNER, scope_type="personal", scope_id="a", source_type="booking", source_id="booking-a",
        title="水電預約", starts_at="2026-08-02T09:00:00+08:00",
        ends_at="2026-08-02T10:00:00+08:00", note=None,
    )
    with pytest.raises(CalendarConflict, match="變更流程"):
        repository.change_manual_series(
            booking["id"], **OWNER, mode="all", occurrence_start=None,
            changes={"starts_at": "2026-08-03T09:00:00+08:00"}, idempotency_key="drag-booking",
        )

