"""Google Calendar mirror. PRD §3.5.

Phase 2 contract (locked 2026-05-15):
- Use ``gcsa`` (google-calendar-simple-api) as the API client.
- OAuth credentials path comes from ``config.calendar.google_oauth_secret_path``;
  the refresh token is persisted via ``keyring`` (macOS Keychain) under
  service "jarvis-google-calendar".
- ``sync_calendar(since, until)`` upserts events into the ``events`` table
  using ``google_event_id`` as the natural key. Returns the number of
  upserted rows (insert + update). Idempotent: re-running yields the same
  row count, no duplicates.
- For each event, also upsert ``event_attendees`` rows. If an attendee email
  matches an existing ``people.email``, link the row; otherwise leave
  person_id NULL — the speaker_resolver can fill it in later.
- ``find_event_for_recording`` joins by ≥50% time-range overlap of the
  recording with the event; ties broken by smallest start-time delta.
  Returns None if no event exceeds the 50% threshold.

The recorder calls find_event_for_recording at the end of the post-stop
pipeline and writes the event_id back onto the recording row. That happens
inside the persister's transaction in Phase 2.
"""

from __future__ import annotations

from datetime import datetime

from .types import CalendarEvent

CALENDAR_KEYRING_SERVICE = "jarvis-google-calendar"
EVENT_OVERLAP_THRESHOLD = 0.5  # ≥50% of recording duration must fall inside event.


def sync_calendar(since: datetime, until: datetime) -> int:
    """Upsert calendar events in [since, until]. Returns # rows touched."""
    raise NotImplementedError("sync_calendar: implemented in Phase 2")


def find_event_for_recording(started_at: datetime, ended_at: datetime) -> CalendarEvent | None:
    """Return the best matching event for a recording window, or None."""
    raise NotImplementedError("find_event_for_recording: implemented in Phase 2")


def authorize() -> None:
    """One-time OAuth flow: open browser, capture refresh token in keyring.

    Re-runnable; rotates the stored token on each call. The CLI command
    ``jarvis calendar authorize`` is a thin wrapper.
    """
    raise NotImplementedError("authorize: implemented in Phase 2")
