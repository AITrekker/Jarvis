"""Voice enrollment & identity assignment. PRD §3.4.

Phase 2 contract (locked 2026-05-15):
- ``resolve_speakers`` maps each ``speaker_raw`` in the transcript (e.g.
  "SPEAKER_00") to a ResolvedSpeaker. The implementation:
    1. Compute a per-raw-speaker centroid embedding from samples of that
       speaker's audio (pyannote ECAPA-TDNN, 192-dim).
    2. Nearest-neighbor cosine vs ``speaker_embeddings`` rows. If
       ``candidate_person_ids`` is non-None, restrict the search to that
       subset (the calendar attendees) — major precision boost.
    3. > threshold_high (default 0.75) -> assign that person.
       in [threshold_low, threshold_high] -> assign + needs_review=True.
       < threshold_low (default 0.55) -> display_name="unknown_<sess>_<n>",
       person_id=None, needs_review=True.
- ``enroll_from_session`` adds an embedding row for a (session, raw_speaker,
  person) triple. The CLI ``jarvis enroll`` is a thin wrapper.
- ``enroll_self`` pre-enrolls the owner from a reference WAV (§8 q4).

Single-speaker Phase 1 callers (recorder.run) pass speakers={} into the
persister; Phase 2 wires the resolver in between transcribe and persist.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .types import EnrolledSpeaker, ResolvedSpeaker, Transcript

THRESHOLD_HIGH = 0.75
THRESHOLD_LOW = 0.55
EMBEDDING_DIM = 192  # pyannote ECAPA-TDNN; matches schema VECTOR(192).


def resolve_speakers(
    transcript: Transcript,
    audio: np.ndarray,
    sample_rate: int,
    *,
    candidate_person_ids: list[int] | None = None,
    threshold_high: float = THRESHOLD_HIGH,
    threshold_low: float = THRESHOLD_LOW,
) -> dict[str, ResolvedSpeaker]:
    """Resolve raw speaker labels to known people. Phase 2."""
    raise NotImplementedError("resolve_speakers: implemented in Phase 2")


def load_enrolled_speakers(*, person_ids: list[int] | None = None) -> list[EnrolledSpeaker]:
    """Read speaker_embeddings JOIN people from Postgres.

    If ``person_ids`` is None, return every enrolled speaker. Otherwise
    restrict to that subset (the calendar-attendee shortlist).
    """
    raise NotImplementedError("load_enrolled_speakers: implemented in Phase 2")


def enroll_from_session(
    session_uuid: str,
    speaker_raw: str,
    person_name: str,
    *,
    person_email: str | None = None,
) -> int:
    """Add an embedding to ``speaker_embeddings`` for this person.

    Computes the centroid from this session's audio, restricted to the
    raw-speaker's turns. Creates a ``people`` row if person_name is new.
    Returns the new ``speaker_embeddings.id``.
    """
    raise NotImplementedError("enroll_from_session: implemented in Phase 2")


def enroll_self(reference_wav: Path, display_name: str = "me") -> int:
    """Pre-enroll the owner from a reference recording. PRD §8 q4.

    Computes a centroid from ``reference_wav`` (any length ≥ 30s recommended),
    inserts a ``people`` row with is_self=True if absent, and writes the
    embedding. Returns the new ``speaker_embeddings.id``. Idempotent — calling
    twice replaces the prior self-embedding rather than duplicating.
    """
    raise NotImplementedError("enroll_self: implemented in Phase 2")
