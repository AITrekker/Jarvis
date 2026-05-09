"""Single-transaction write to Postgres. PRD §3.6.

No dual-store writes. Embeddings live in pgvector columns on the same rows
written in this transaction.
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
    raise NotImplementedError("persist_recording: implemented in Phase 1")
