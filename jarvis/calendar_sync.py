"""Google Calendar mirror. PRD §3.5.

Phase 2 contract (locked 2026-05-15):
- Use ``gcsa`` (google-calendar-simple-api) as the API client.
- OAuth credentials path comes from ``config.calendar.google_oauth_secret_path``;
  the refresh token + access token + token_uri / client_id / client_secret are
  persisted via ``keyring`` (macOS Keychain) under service
  "jarvis-google-calendar".
- ``sync_calendar(since, until)`` upserts events into the ``events`` table
  using ``google_event_id`` as the natural key. Returns the number of
  upserted rows (insert + update). Idempotent: re-running yields the same
  row count, no duplicates.
- For each event, also upsert ``event_attendees`` rows. If an attendee email
  matches an existing ``people.email``, link the row; otherwise leave
  person_id NULL — the speaker_resolver can fill it in later.
- ``find_event_for_recording`` joins by >=50% time-range overlap of the
  recording with the event; ties broken by smallest start-time delta.
  Returns None if no event exceeds the 50% threshold.

The recorder calls find_event_for_recording at the end of the post-stop
pipeline and writes the event_id back onto the recording row. That happens
inside the persister's transaction in Phase 2.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

import psycopg

from .types import CalendarEvent

log = logging.getLogger(__name__)

CALENDAR_KEYRING_SERVICE = "jarvis-google-calendar"
CALENDAR_KEYRING_USERNAME = "refresh_token"
EVENT_OVERLAP_THRESHOLD = 0.5  # >=50% of recording duration must fall inside event.

# Scopes required for read-only event listing. We deliberately do NOT request
# write scopes — Jarvis is a mirror, never a calendar editor.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _db_url() -> str:
    url = os.environ.get("JARVIS_DB_URL")
    if not url:
        raise RuntimeError("JARVIS_DB_URL is not set. Configure it before running calendar_sync.")
    return url


def _oauth_secret_path() -> str:
    """Resolve the OAuth client-secret JSON path from config.

    Imported lazily so the module is importable without the full config
    machinery (handy for unit tests that mock everything).
    """
    from . import config as _config

    return _config.load().calendar.google_oauth_secret_path


def _store_token(creds: Any) -> None:
    """Persist credentials to keyring as a JSON blob.

    We store more than just the refresh_token because gcsa's GoogleCalendar
    accepts a `Credentials` object that needs token_uri, client_id, and
    client_secret to refresh. Keyring stores arbitrary strings.
    """
    import keyring

    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }
    keyring.set_password(
        CALENDAR_KEYRING_SERVICE,
        CALENDAR_KEYRING_USERNAME,
        json.dumps(payload),
    )


def _load_credentials() -> Any:
    """Load Credentials from keyring. Raises RuntimeError if unauthorized."""
    import keyring
    from google.oauth2.credentials import Credentials

    raw = keyring.get_password(CALENDAR_KEYRING_SERVICE, CALENDAR_KEYRING_USERNAME)
    if not raw:
        raise RuntimeError("calendar not authorized; run `jarvis calendar authorize`")
    payload = json.loads(raw)
    return Credentials(
        token=payload.get("token"),
        refresh_token=payload.get("refresh_token"),
        token_uri=payload.get("token_uri"),
        client_id=payload.get("client_id"),
        client_secret=payload.get("client_secret"),
        scopes=payload.get("scopes", SCOPES),
    )


def _make_calendar_client() -> Any:
    """Build a gcsa GoogleCalendar client from keyring credentials."""
    from gcsa.google_calendar import GoogleCalendar

    creds = _load_credentials()
    # save_token=False because we own persistence via keyring; gcsa's pickle
    # cache would shadow our store and silently desync.
    return GoogleCalendar(credentials=creds, save_token=False)


def _serialize_event(event: Any) -> dict[str, Any]:
    """Serialize a gcsa Event to a JSON-safe dict for the raw_payload column.

    We don't roundtrip everything; just enough that a future debug session can
    see what the calendar told us. Datetimes become ISO strings.
    """

    def _stringify(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    attendees = []
    for a in event.attendees or []:
        attendees.append(
            {
                "email": getattr(a, "email", None),
                "display_name": getattr(a, "display_name", None),
                "response_status": getattr(a, "response_status", None),
            }
        )
    return {
        "id": event.id,
        "summary": event.summary,
        "description": event.description,
        "start": _stringify(event.start) if event.start else None,
        "end": _stringify(event.end) if event.end else None,
        "attendees": attendees,
        "location": getattr(event, "location", None),
    }


def _coerce_datetime(value: Any) -> datetime:
    """Coerce a gcsa start/end into a datetime.

    gcsa returns datetime for timed events and date for all-day events. We
    promote bare dates to midnight UTC so the SQL TIMESTAMPTZ insert succeeds.
    """
    from datetime import UTC, date

    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    raise TypeError(f"unexpected calendar event time type: {type(value).__name__}")


def sync_calendar(since: datetime, until: datetime) -> int:
    """Upsert calendar events in [since, until]. Returns # rows touched.

    Idempotent: re-running with the same window updates existing rows in
    place; the returned count includes both inserts and updates (so the
    operator can confirm "yes, it found 12 events" on either run).
    """
    cal = _make_calendar_client()
    events = list(cal.get_events(time_min=since, time_max=until, single_events=True))

    url = _db_url()
    touched = 0
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for ev in events:
            if ev.id is None:
                # Defensive: gcsa events should always carry an id, but skip
                # rather than crash on the off chance.
                log.warning("calendar event without id, skipping: summary=%s", ev.summary)
                continue
            started = _coerce_datetime(ev.start)
            ended = _coerce_datetime(ev.end) if ev.end else started
            title = ev.summary or "(no title)"
            description = ev.description
            payload = json.dumps(_serialize_event(ev))

            cur.execute(
                """
                INSERT INTO events
                    (google_event_id, title, started_at, ended_at, description, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (google_event_id) DO UPDATE
                   SET title = EXCLUDED.title,
                       started_at = EXCLUDED.started_at,
                       ended_at = EXCLUDED.ended_at,
                       description = EXCLUDED.description,
                       raw_payload = EXCLUDED.raw_payload
                RETURNING id
                """,
                (ev.id, title, started, ended, description, payload),
            )
            row = cur.fetchone()
            if row is None:  # pragma: no cover - INSERT...RETURNING always yields a row
                raise RuntimeError("INSERT into events did not return an id")
            event_id = row[0]
            touched += 1

            # Replace the attendee set for this event. Calendar attendees are a
            # snapshot — if someone is removed from an event upstream, we want
            # them gone here too. DELETE-then-INSERT inside the same txn keeps
            # the row count honest.
            cur.execute("DELETE FROM event_attendees WHERE event_id = %s", (event_id,))
            for attendee in ev.attendees or []:
                email = getattr(attendee, "email", None)
                if not email:
                    continue
                display_name = getattr(attendee, "display_name", None)
                response_status = getattr(attendee, "response_status", None)

                # Resolve to a known person if we can.
                cur.execute("SELECT id FROM people WHERE email = %s", (email,))
                pr = cur.fetchone()
                person_id = pr[0] if pr else None

                cur.execute(
                    """
                    INSERT INTO event_attendees
                        (event_id, person_id, email, display_name, response_status)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (event_id, email) DO UPDATE
                       SET person_id = EXCLUDED.person_id,
                           display_name = EXCLUDED.display_name,
                           response_status = EXCLUDED.response_status
                    """,
                    (event_id, person_id, email, display_name, response_status),
                )

    log.info("sync_calendar: upserted %d events between %s and %s", touched, since, until)
    return touched


def find_event_for_recording(started_at: datetime, ended_at: datetime) -> CalendarEvent | None:
    """Return the best matching event for a recording window, or None.

    Matching rule (PRD §3.5):
    - candidate events overlap the recording window at all
    - winning event has overlap >= 50% of the recording's duration
    - ties broken by smallest |event.started_at - recording.started_at|
    """
    rec_duration = (ended_at - started_at).total_seconds()
    if rec_duration <= 0:
        return None

    url = _db_url()
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, google_event_id, title, started_at, ended_at, description
              FROM events
             WHERE NOT (ended_at < %s OR started_at > %s)
            """,
            (started_at, ended_at),
        )
        rows = cur.fetchall()

        best: tuple[float, float, tuple[Any, ...]] | None = None
        for row in rows:
            ev_started: datetime = row[3]
            ev_ended: datetime = row[4]
            overlap_start = max(started_at, ev_started)
            overlap_end = min(ended_at, ev_ended)
            overlap = (overlap_end - overlap_start).total_seconds()
            if overlap <= 0:
                continue
            ratio = overlap / rec_duration
            if ratio < EVENT_OVERLAP_THRESHOLD:
                continue
            delta = abs((ev_started - started_at).total_seconds())
            # Sort key: higher ratio wins; on tie, smaller delta wins.
            key = (-ratio, delta)
            if best is None or key < (-best[0], best[1]):
                best = (ratio, delta, row)

        if best is None:
            return None

        winner = best[2]
        event_id = winner[0]

        cur.execute(
            "SELECT person_id FROM event_attendees WHERE event_id = %s AND person_id IS NOT NULL",
            (event_id,),
        )
        attendee_person_ids = [r[0] for r in cur.fetchall()]

    return CalendarEvent(
        id=winner[0],
        google_event_id=winner[1],
        title=winner[2],
        started_at=winner[3],
        ended_at=winner[4],
        description=winner[5],
        attendee_person_ids=attendee_person_ids,
    )


def authorize() -> None:
    """One-time OAuth flow: open browser, capture refresh token in keyring.

    Re-runnable; rotates the stored token on each call. The CLI command
    ``jarvis calendar authorize`` is a thin wrapper.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret_path = _oauth_secret_path()
    if not os.path.exists(secret_path):
        raise RuntimeError(
            f"OAuth client secret not found at {secret_path}. "
            "Download credentials.json from Google Cloud Console and place it there, "
            "or set [calendar].google_oauth_secret_path in config.toml."
        )

    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
    creds = flow.run_local_server(port=0)
    _store_token(creds)

    # Best-effort: report which account authorized so the operator can confirm.
    try:
        from googleapiclient.discovery import build

        service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        info = service.userinfo().get().execute()
        email = info.get("email", "<unknown>")
    except Exception:  # noqa: BLE001 - best-effort label only
        email = "<unknown>"

    print(f"authorized as {email}")
