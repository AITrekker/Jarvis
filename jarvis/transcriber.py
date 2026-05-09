"""WhisperX wrapper. PRD §3.3."""

from __future__ import annotations

from collections.abc import Iterable

from .types import AudioSegment, Transcript


def transcribe(
    segments: Iterable[AudioSegment],
    num_speakers_hint: int | None = None,
) -> Transcript:
    raise NotImplementedError("transcribe: implemented in Phase 1/2")
