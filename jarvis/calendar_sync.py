"""Google Calendar mirror. PRD §3.5."""

from __future__ import annotations

from datetime import datetime

from .types import CalendarEvent


def sync_calendar(since: datetime, until: datetime) -> int:
    raise NotImplementedError("sync_calendar: implemented in Phase 2")


def find_event_for_recording(started_at: datetime, ended_at: datetime) -> CalendarEvent | None:
    raise NotImplementedError("find_event_for_recording: implemented in Phase 2")
