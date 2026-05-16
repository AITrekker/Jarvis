"""Single-transaction write to Postgres. PRD §3.6.

No dual-store writes. Embeddings live in pgvector columns on the same rows
written in this transaction.

Phase 1 scope: writes only `recordings` + `turns`. `chunks` and `embeddings`
are Phase 3. The `speakers` and `calendar_event` arguments are accepted in
the signature but ignored on write until Phase 2.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import psycopg

from .types import CalendarEvent, ResolvedSpeaker, SessionMeta, Transcript

log = logging.getLogger(__name__)


def _db_url() -> str:
    url = os.environ.get("JARVIS_DB_URL")
    if not url:
        raise RuntimeError("JARVIS_DB_URL is not set. Configure it before running the persister.")
    return url


def persist_recording(
    audio_path: Path,
    transcript: Transcript,
    speakers: dict[str, ResolvedSpeaker],
    calendar_event: CalendarEvent | None,
    session_meta: SessionMeta,
) -> int:
    """Persist a recording atomically. Returns the recording_id.

    Phase 1 contract:
    - Single transaction over `recordings` + `turns` only.
    - Idempotent on session_meta.session_uuid: re-running deletes child rows
      and re-inserts within the same transaction.
    - On any error, the transaction rolls back; the database is unchanged.
    - speakers/calendar_event are stored as no-ops; Phase 2 wires them in.
    """
    del speakers, calendar_event  # Phase 2.

    url = _db_url()

    # `with psycopg.connect(...)` opens an implicit transaction and commits on
    # clean exit, rolls back on exception. That's exactly the contract we want.
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        # Idempotency: if a row with this session_uuid already exists, update
        # it and wipe its children before re-inserting turns.
        cur.execute(
            "SELECT id FROM recordings WHERE session_uuid = %s",
            (session_meta.session_uuid,),
        )
        existing = cur.fetchone()

        if existing is not None:
            recording_id = existing[0]
            cur.execute(
                """
                UPDATE recordings
                   SET audio_path = %s,
                       source_label = %s,
                       started_at = %s,
                       ended_at = %s
                 WHERE id = %s
                """,
                (
                    str(audio_path),
                    session_meta.source_label,
                    session_meta.started_at,
                    session_meta.ended_at,
                    recording_id,
                ),
            )
            cur.execute("DELETE FROM turns WHERE recording_id = %s", (recording_id,))
        else:
            cur.execute(
                """
                INSERT INTO recordings
                    (session_uuid, audio_path, source_label, started_at, ended_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session_meta.session_uuid,
                    str(audio_path),
                    session_meta.source_label,
                    session_meta.started_at,
                    session_meta.ended_at,
                ),
            )
            row = cur.fetchone()
            if row is None:  # pragma: no cover - INSERT...RETURNING always yields a row
                raise RuntimeError("INSERT into recordings did not return an id")
            recording_id = row[0]

        if transcript.turns:
            cur.executemany(
                """
                INSERT INTO turns
                    (recording_id, speaker_raw, t_start, t_end, text)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        recording_id,
                        turn.speaker_raw,
                        float(turn.t_start),
                        float(turn.t_end),
                        turn.text,
                    )
                    for turn in transcript.turns
                ],
            )

    log.info(
        "persisted recording id=%s session=%s turns=%s",
        recording_id,
        session_meta.session_uuid,
        len(transcript.turns),
    )
    return recording_id
