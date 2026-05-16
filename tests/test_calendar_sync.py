"""Tests for calendar_sync. PRD §3.5.

Two layers:
- Unit tests with mocked gcsa client + keyring (fast, no Docker).
- Integration tests against a pgvector testcontainer that exercise the real
  upsert SQL and assert idempotency + attendee linking.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from jarvis import calendar_sync, cli

# --------------------------------------------------------------------------- #
# Fakes                                                                       #
# --------------------------------------------------------------------------- #


def _fake_attendee(email: str, *, display_name=None, response_status="accepted"):
    return SimpleNamespace(
        email=email,
        display_name=display_name,
        response_status=response_status,
    )


def _fake_event(
    *,
    eid: str,
    summary: str,
    start: datetime,
    end: datetime,
    attendees=None,
    description=None,
):
    return SimpleNamespace(
        id=eid,
        summary=summary,
        description=description,
        start=start,
        end=end,
        attendees=attendees or [],
        location=None,
    )


class _FakeCalendarClient:
    """Stand-in for gcsa.GoogleCalendar in unit tests."""

    def __init__(self, events):
        self._events = events
        self.calls: list[dict] = []

    def get_events(self, time_min=None, time_max=None, single_events=False, **kwargs):
        self.calls.append(
            {"time_min": time_min, "time_max": time_max, "single_events": single_events}
        )
        return iter(self._events)


# --------------------------------------------------------------------------- #
# Unit tests — pure logic (no Postgres)                                       #
# --------------------------------------------------------------------------- #


def test_load_credentials_raises_when_keyring_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(calendar_sync, "_load_credentials", calendar_sync._load_credentials)
    fake_keyring = SimpleNamespace(
        get_password=lambda *a, **k: None,
        set_password=lambda *a, **k: None,
    )
    monkeypatch.setitem(__import__("sys").modules, "keyring", fake_keyring)
    with pytest.raises(RuntimeError, match="not authorized"):
        calendar_sync._load_credentials()


def test_store_token_writes_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def _set(service, user, value):
        captured["service"] = service
        captured["user"] = user
        captured["value"] = value

    fake_keyring = SimpleNamespace(set_password=_set, get_password=lambda *a, **k: None)
    monkeypatch.setitem(__import__("sys").modules, "keyring", fake_keyring)

    creds = SimpleNamespace(
        token="ACCESS",
        refresh_token="REFRESH",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="cid",
        client_secret="csec",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    calendar_sync._store_token(creds)

    assert captured["service"] == calendar_sync.CALENDAR_KEYRING_SERVICE
    assert captured["user"] == calendar_sync.CALENDAR_KEYRING_USERNAME
    payload = json.loads(captured["value"])
    assert payload["refresh_token"] == "REFRESH"
    assert payload["token"] == "ACCESS"
    assert payload["client_id"] == "cid"


def test_authorize_missing_secret_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    bogus = tmp_path / "nope.json"
    monkeypatch.setattr(calendar_sync, "_oauth_secret_path", lambda: str(bogus))
    with pytest.raises(RuntimeError, match="OAuth client secret not found"):
        calendar_sync.authorize()


def test_serialize_event_handles_datetimes() -> None:
    start = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    end = datetime(2026, 5, 15, 11, 0, tzinfo=UTC)
    ev = _fake_event(
        eid="abc",
        summary="Standup",
        start=start,
        end=end,
        attendees=[_fake_attendee("a@example.com", display_name="A")],
        description="hi",
    )
    payload = calendar_sync._serialize_event(ev)
    assert payload["id"] == "abc"
    assert payload["summary"] == "Standup"
    assert payload["start"].startswith("2026-05-15T10:00")
    assert payload["attendees"][0]["email"] == "a@example.com"


def test_coerce_datetime_promotes_date_to_midnight_utc() -> None:
    from datetime import date

    out = calendar_sync._coerce_datetime(date(2026, 5, 15))
    assert out == datetime(2026, 5, 15, 0, 0, tzinfo=UTC)


def test_coerce_datetime_passes_datetime_through() -> None:
    in_ = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    assert calendar_sync._coerce_datetime(in_) is in_


# --------------------------------------------------------------------------- #
# Integration tests — testcontainer Postgres                                  #
# --------------------------------------------------------------------------- #


pytestmark_integration = pytest.mark.integration


def _seed_person(url: str, *, email: str, name: str) -> int:
    import psycopg

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO people (display_name, email) VALUES (%s, %s) RETURNING id",
            (name, email),
        )
        row = cur.fetchone()
        assert row is not None
        return row[0]


def _count(url: str, table: str, where: str = "", params=()) -> int:
    import psycopg

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table} {where}", params)
        row = cur.fetchone()
        assert row is not None
        return row[0]


@pytest.fixture
def fake_client_factory(monkeypatch: pytest.MonkeyPatch):
    """Patch _make_calendar_client to return a fake whose events the test sets."""

    holder: dict = {"client": None}

    def _set_events(events):
        holder["client"] = _FakeCalendarClient(events)

    def _maker():
        if holder["client"] is None:
            holder["client"] = _FakeCalendarClient([])
        return holder["client"]

    monkeypatch.setattr(calendar_sync, "_make_calendar_client", _maker)
    return _set_events


@pytest.fixture(autouse=True)
def _ensure_db_url(postgres_url: str, monkeypatch: pytest.MonkeyPatch):
    if not os.environ.get("JARVIS_DB_URL"):
        monkeypatch.setenv("JARVIS_DB_URL", postgres_url)
    yield


@pytest.mark.integration
def test_sync_inserts_events_and_attendees(postgres_url: str, fake_client_factory) -> None:
    person_id = _seed_person(postgres_url, email="known@example.com", name="Known")

    start = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    events = [
        _fake_event(
            eid="evt-1",
            summary="Design review",
            start=start,
            end=end,
            attendees=[
                _fake_attendee("known@example.com", display_name="Known"),
                _fake_attendee("stranger@example.com", display_name="Stranger"),
            ],
        )
    ]
    fake_client_factory(events)

    n = calendar_sync.sync_calendar(start - timedelta(days=1), end + timedelta(days=1))
    assert n == 1

    assert _count(postgres_url, "events", "WHERE google_event_id = %s", ("evt-1",)) == 1
    assert _count(postgres_url, "event_attendees") == 2

    import psycopg

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT email, person_id, display_name, response_status "
            "FROM event_attendees ORDER BY email"
        )
        rows = cur.fetchall()
    by_email = {r[0]: r for r in rows}
    assert by_email["known@example.com"][1] == person_id
    assert by_email["known@example.com"][2] == "Known"
    assert by_email["stranger@example.com"][1] is None  # unknown email -> NULL


@pytest.mark.integration
def test_sync_idempotent_no_duplicates(postgres_url: str, fake_client_factory) -> None:
    start = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    events = [
        _fake_event(
            eid="evt-dup",
            summary="Sync 1:1",
            start=start,
            end=end,
            attendees=[_fake_attendee("a@example.com")],
        )
    ]
    fake_client_factory(events)

    calendar_sync.sync_calendar(start - timedelta(days=1), end + timedelta(days=1))
    rows_after_first = _count(postgres_url, "events", "WHERE google_event_id = %s", ("evt-dup",))

    # Re-run same window. Title changed upstream — verify update-in-place.
    events[0].summary = "Sync 1:1 (renamed)"
    fake_client_factory(events)
    calendar_sync.sync_calendar(start - timedelta(days=1), end + timedelta(days=1))

    assert rows_after_first == 1
    assert _count(postgres_url, "events", "WHERE google_event_id = %s", ("evt-dup",)) == 1
    # Scope to this event: postgres_url is session-scoped so other integration
    # tests' attendees coexist in the same DB.
    assert (
        _count(
            postgres_url,
            "event_attendees",
            "WHERE event_id = (SELECT id FROM events WHERE google_event_id = %s)",
            ("evt-dup",),
        )
        == 1
    )

    import psycopg

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT title FROM events WHERE google_event_id = %s", ("evt-dup",))
        title = cur.fetchone()[0]
    assert title == "Sync 1:1 (renamed)"


@pytest.mark.integration
def test_find_event_picks_highest_overlap(postgres_url: str, fake_client_factory) -> None:
    # Recording: 1h block from 10:00 to 11:00.
    rec_start = datetime(2026, 5, 16, 10, 0, tzinfo=UTC)
    rec_end = rec_start + timedelta(hours=1)

    # Three candidate events with different overlap fractions.
    #   30%: starts 09:00, ends 10:18  -> 18m overlap
    #   60%: starts 10:24, ends 11:30  -> 36m overlap
    #   80%: starts 09:50, ends 10:58  -> 48m overlap (winner)
    events = [
        _fake_event(
            eid="evt-30",
            summary="30pct",
            start=rec_start - timedelta(hours=1),
            end=rec_start + timedelta(minutes=18),
        ),
        _fake_event(
            eid="evt-60",
            summary="60pct",
            start=rec_start + timedelta(minutes=24),
            end=rec_end + timedelta(minutes=30),
        ),
        _fake_event(
            eid="evt-80",
            summary="80pct",
            start=rec_start - timedelta(minutes=10),
            end=rec_end - timedelta(minutes=2),
        ),
    ]
    fake_client_factory(events)
    calendar_sync.sync_calendar(rec_start - timedelta(hours=2), rec_end + timedelta(hours=2))

    winner = calendar_sync.find_event_for_recording(rec_start, rec_end)
    assert winner is not None
    assert winner.google_event_id == "evt-80"


@pytest.mark.integration
def test_find_event_returns_none_when_below_threshold(
    postgres_url: str, fake_client_factory
) -> None:
    rec_start = datetime(2026, 5, 17, 10, 0, tzinfo=UTC)
    rec_end = rec_start + timedelta(hours=1)
    # 30% and 20% overlap — neither clears 50%.
    events = [
        _fake_event(
            eid="below-1",
            summary="below-1",
            start=rec_start - timedelta(hours=1),
            end=rec_start + timedelta(minutes=18),
        ),
        _fake_event(
            eid="below-2",
            summary="below-2",
            start=rec_end - timedelta(minutes=12),
            end=rec_end + timedelta(hours=1),
        ),
    ]
    fake_client_factory(events)
    calendar_sync.sync_calendar(rec_start - timedelta(hours=2), rec_end + timedelta(hours=2))

    assert calendar_sync.find_event_for_recording(rec_start, rec_end) is None


@pytest.mark.integration
def test_find_event_tiebreak_prefers_closest_start(postgres_url: str, fake_client_factory) -> None:
    rec_start = datetime(2026, 5, 18, 10, 0, tzinfo=UTC)
    rec_end = rec_start + timedelta(hours=1)
    # Both events overlap exactly 80%: 48 minutes inside the recording window.
    #   evt-A: 09:48..10:48  -> overlap = 10:00..10:48 = 48m, |start-rec| = 12m
    #   evt-B: 10:12..11:12  -> overlap = 10:12..11:00 = 48m, |start-rec| = 12m
    # That gives identical deltas. Make A 14m earlier to make the tie strict on
    # ratio but distinct on start-delta (closer to recording start should win).
    #   evt-CLOSE: 09:55..10:55 -> overlap = 10:00..10:55 = 55m (~92%), delta=5m
    #   evt-FAR:   10:05..11:05 -> overlap = 10:05..11:00 = 55m (~92%), delta=5m
    # Both deltas equal -> ratio determines. Force a tie at exactly 80% by
    # constructing windows that agree on overlap but differ on start delta:
    events = [
        # event_close: from 10:06 to 11:06 (overlap 10:06..11:00 = 54m) -> 90%
        _fake_event(
            eid="close",
            summary="close",
            start=rec_start + timedelta(minutes=6),
            end=rec_end + timedelta(minutes=6),
        ),
        # event_far: from 10:18 to 11:18 (overlap 10:18..11:00 = 42m) -> 70%
        _fake_event(
            eid="far",
            summary="far",
            start=rec_start + timedelta(minutes=18),
            end=rec_end + timedelta(minutes=18),
        ),
    ]
    fake_client_factory(events)
    calendar_sync.sync_calendar(rec_start - timedelta(hours=2), rec_end + timedelta(hours=2))
    # `close` wins on both overlap and start-delta; the explicit "true tie"
    # case is impossible to construct with arbitrary precision, so we exercise
    # the tiebreak by injecting two equal-overlap rows directly.
    winner = calendar_sync.find_event_for_recording(rec_start, rec_end)
    assert winner is not None
    assert winner.google_event_id == "close"

    # Now construct an exact tie at 60% overlap and confirm the closer-start wins.
    import psycopg

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        # 60% = 36 minutes.
        # tie-A starts 5 minutes before recording ends in the future: from 10:24 -> 11:00 = 36m, delta=24
        # tie-B starts at 09:24 -> 10:00 = wait that's overlap 0. Re-do:
        # Goal: equal overlap = 36 minutes, different start deltas.
        #   A: starts 09:24, ends 10:36 -> overlap = 10:00..10:36 = 36m, delta=36
        #   B: starts 10:24, ends 11:36 -> overlap = 10:24..11:00 = 36m, delta=24  (closer)
        cur.execute(
            """
            INSERT INTO events (google_event_id, title, started_at, ended_at)
            VALUES
              ('tie-A', 'A', %s, %s),
              ('tie-B', 'B', %s, %s)
            ON CONFLICT (google_event_id) DO NOTHING
            """,
            (
                rec_start - timedelta(minutes=36),
                rec_start + timedelta(minutes=36),
                rec_start + timedelta(minutes=24),
                rec_start + timedelta(hours=1, minutes=36),
            ),
        )

    # Pick a fresh recording window that ONLY tie-A and tie-B overlap with at exactly 60%.
    # Use the same window: tie-A overlap = 36m, tie-B overlap = 36m. close/far above
    # also overlap; remove them by widening the window check.
    # Easier: directly use this window — both `close` and `far` also overlap, and
    # their overlaps are 90% and 70% respectively, beating both ties. So instead,
    # use a *new* recording window that only the new tie rows overlap with.
    fresh_start = datetime(2026, 5, 19, 10, 0, tzinfo=UTC)
    fresh_end = fresh_start + timedelta(hours=1)
    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        # Replace the tie rows with windows aligned to fresh_start:
        cur.execute("DELETE FROM events WHERE google_event_id IN ('tie-A','tie-B')")
        cur.execute(
            """
            INSERT INTO events (google_event_id, title, started_at, ended_at) VALUES
              ('tie-A', 'A', %s, %s),
              ('tie-B', 'B', %s, %s)
            """,
            (
                fresh_start - timedelta(minutes=36),
                fresh_start + timedelta(minutes=36),
                fresh_start + timedelta(minutes=24),
                fresh_end + timedelta(minutes=36),
            ),
        )

    winner2 = calendar_sync.find_event_for_recording(fresh_start, fresh_end)
    assert winner2 is not None
    assert winner2.google_event_id == "tie-B"  # smaller start delta


@pytest.mark.integration
def test_find_event_attendee_person_ids(postgres_url: str, fake_client_factory) -> None:
    pid = _seed_person(postgres_url, email="someone@example.com", name="Someone")
    start = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    events = [
        _fake_event(
            eid="evt-people",
            summary="With person",
            start=start,
            end=end,
            attendees=[
                _fake_attendee("someone@example.com"),
                _fake_attendee("nobody@example.com"),
            ],
        )
    ]
    fake_client_factory(events)
    calendar_sync.sync_calendar(start - timedelta(days=1), end + timedelta(days=1))

    found = calendar_sync.find_event_for_recording(start, end)
    assert found is not None
    assert found.attendee_person_ids == [pid]


# --------------------------------------------------------------------------- #
# CLI smoke (unit; no Postgres)                                               #
# --------------------------------------------------------------------------- #


def test_cli_calendar_sync_invokes_module(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_sync(since, until):
        captured["since"] = since
        captured["until"] = until
        return 7

    from jarvis import calendar_sync as cs

    monkeypatch.setattr(cs, "sync_calendar", fake_sync)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["calendar", "sync"])
    assert result.exit_code == 0, result.output
    assert "synced 7 events" in result.output
    assert "since" in captured
    assert "until" in captured


def test_cli_calendar_sync_with_explicit_window(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_sync(since, until):
        captured["since"] = since
        captured["until"] = until
        return 0

    from jarvis import calendar_sync as cs

    monkeypatch.setattr(cs, "sync_calendar", fake_sync)
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["calendar", "sync", "--since", "2026-05-01", "--until", "2026-05-10"],
    )
    assert result.exit_code == 0, result.output
    assert captured["since"] == datetime(2026, 5, 1, tzinfo=UTC)
    assert captured["until"] == datetime(2026, 5, 10, tzinfo=UTC)


def test_cli_calendar_authorize_unauthorized_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jarvis import calendar_sync as cs

    def boom():
        raise RuntimeError("OAuth client secret not found at /nope")

    monkeypatch.setattr(cs, "authorize", boom)
    runner = CliRunner()
    result = runner.invoke(cli.main, ["calendar", "authorize"])
    assert result.exit_code != 0
    assert "OAuth client secret not found" in result.output


def test_cli_calendar_sync_unauthorized_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    from jarvis import calendar_sync as cs

    def fake_sync(since, until):
        raise RuntimeError("calendar not authorized; run `jarvis calendar authorize`")

    monkeypatch.setattr(cs, "sync_calendar", fake_sync)
    runner = CliRunner()
    result = runner.invoke(cli.main, ["calendar", "sync"])
    assert result.exit_code != 0
    assert "not authorized" in result.output
