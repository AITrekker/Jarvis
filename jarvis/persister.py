"""Single-transaction write to Postgres. PRD §3.6.

No dual-store writes. Embeddings live in pgvector columns on the same rows
written in this transaction.

Phase 1 scope: writes only `recordings` + `turns`. `chunks` and `embeddings`
are Phase 3. The `speakers` and `calendar_event` arguments are accepted in
the signature but ignored on write until Phase 2.
"""

from __future__ import annotations

from pathlib import Path

from .types import CalendarEvent, ResolvedSpeaker, SessionMeta, Transcript


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
    raise NotImplementedError("persist_recording: implemented in Phase 1")
