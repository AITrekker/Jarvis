"""Persister integration tests against a pgvector testcontainer.

PRD §3.6 acceptance:
- Single-transaction write of recordings + turns
- Idempotent on session_uuid (delete-and-reinsert child rows)
- Mid-write failure rolls back to the prior state
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jarvis import persister
from jarvis.types import SessionMeta, Transcript, Turn

pytestmark = pytest.mark.integration


def _fake_transcript(turns: int = 2) -> Transcript:
    return Transcript(
        turns=[
            Turn(
                speaker_raw="SPEAKER_00",
                t_start=float(i),
                t_end=float(i + 1),
                text=f"hello world {i}",
                words=[],
            )
            for i in range(turns)
        ],
        language="en",
    )


def _session_meta(session_uuid: str | None = None) -> SessionMeta:
    return SessionMeta(
        session_uuid=session_uuid or str(uuid.uuid4()),
        source_label="wav:tests/fixtures/synthetic_5s.wav",
        started_at=datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 11, 12, 0, 5, tzinfo=UTC),
    )


def _row_counts(url: str, session_uuid: str) -> tuple[int, int]:
    import psycopg

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM recordings WHERE session_uuid = %s", (session_uuid,))
        rec = cur.fetchone()
        if rec is None:
            return 0, 0
        cur.execute("SELECT COUNT(*) FROM turns WHERE recording_id = %s", (rec[0],))
        result = cur.fetchone()
        assert result is not None
        return 1, result[0]


def test_persist_writes_recording_and_turns(postgres_url: str) -> None:
    import psycopg

    meta = _session_meta()
    transcript = _fake_transcript(turns=2)

    rec_id = persister.persist_recording(
        audio_path=Path("/tmp/fake.wav"),
        transcript=transcript,
        speakers={},
        calendar_event=None,
        session_meta=meta,
    )

    assert rec_id > 0

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT session_uuid, audio_path, source_label FROM recordings WHERE id = %s",
            (rec_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert str(row[0]) == meta.session_uuid
        assert row[1] == "/tmp/fake.wav"
        assert row[2] == meta.source_label

        cur.execute(
            "SELECT speaker_raw, t_start, t_end, text FROM turns "
            "WHERE recording_id = %s ORDER BY t_start",
            (rec_id,),
        )
        rows = cur.fetchall()
        assert len(rows) == 2
        assert rows[0] == ("SPEAKER_00", 0.0, 1.0, "hello world 0")
        assert rows[1] == ("SPEAKER_00", 1.0, 2.0, "hello world 1")


def test_persist_idempotent(postgres_url: str) -> None:
    """Running twice with the same session_uuid does not duplicate turns."""
    meta = _session_meta()
    transcript = _fake_transcript(turns=3)

    rec_id_1 = persister.persist_recording(Path("/tmp/fake.wav"), transcript, {}, None, meta)
    rec_id_2 = persister.persist_recording(Path("/tmp/fake.wav"), transcript, {}, None, meta)

    assert rec_id_1 == rec_id_2
    recordings, turns = _row_counts(postgres_url, meta.session_uuid)
    assert recordings == 1
    assert turns == 3

    # Third run with a different transcript shape should replace, not append.
    smaller = _fake_transcript(turns=1)
    rec_id_3 = persister.persist_recording(Path("/tmp/fake.wav"), smaller, {}, None, meta)
    assert rec_id_3 == rec_id_1
    recordings, turns = _row_counts(postgres_url, meta.session_uuid)
    assert recordings == 1
    assert turns == 1


def test_persist_rollback_on_error(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """If executemany fails, no recording or turn rows are persisted."""
    import psycopg

    meta = _session_meta()
    transcript = _fake_transcript(turns=2)

    real_connect = psycopg.connect

    class _CursorProxy:
        def __init__(self, real_cursor):
            self._real = real_cursor
            self._calls = 0

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def executemany(self, *args, **kwargs):
            raise RuntimeError("simulated DB failure mid-write")

        def fetchone(self):
            return self._real.fetchone()

        def fetchall(self):
            return self._real.fetchall()

        def close(self):
            return self._real.close()

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *exc):
            return self._real.__exit__(*exc)

    class _ConnProxy:
        def __init__(self, real_conn):
            self._real = real_conn

        def cursor(self):
            return _CursorProxy(self._real.cursor())

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *exc):
            return self._real.__exit__(*exc)

        def commit(self):
            return self._real.commit()

        def rollback(self):
            return self._real.rollback()

        def close(self):
            return self._real.close()

    def _fake_connect(url, *args, **kwargs):
        return _ConnProxy(real_connect(url, *args, **kwargs))

    monkeypatch.setattr(persister.psycopg, "connect", _fake_connect)

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        persister.persist_recording(Path("/tmp/fake.wav"), transcript, {}, None, meta)

    recordings, turns = _row_counts(postgres_url, meta.session_uuid)
    assert recordings == 0
    assert turns == 0


# Belt-and-suspenders: integration tests usually run with the postgres_url
# fixture which sets JARVIS_DB_URL; this guards against accidental ordering.
@pytest.fixture(autouse=True)
def _ensure_db_url(postgres_url: str, monkeypatch: pytest.MonkeyPatch):
    if not os.environ.get("JARVIS_DB_URL"):
        monkeypatch.setenv("JARVIS_DB_URL", postgres_url)
    yield
