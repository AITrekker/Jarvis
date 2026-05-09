"""Voice enrollment & identity assignment. PRD §3.4."""

from __future__ import annotations

import numpy as np

from .types import ResolvedSpeaker, Transcript


def resolve_speakers(
    transcript: Transcript,
    audio: np.ndarray,
    sample_rate: int,
    candidate_person_ids: list[int] | None = None,
) -> dict[str, ResolvedSpeaker]:
    raise NotImplementedError("resolve_speakers: implemented in Phase 2")
