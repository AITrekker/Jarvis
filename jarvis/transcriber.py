"""WhisperX wrapper. PRD §3.3.

Phase 1: single-speaker mode. Every word gets speaker_raw="SPEAKER_00".
Diarization (real speaker labels) lands in Phase 2.

Models load lazily and cache. Use `tiny.en` in tests; `large-v3` in
production (config-driven).
"""

from __future__ import annotations

from collections.abc import Iterable

from .types import AudioSegment, Transcript

DEFAULT_TEST_MODEL = "tiny.en"


def transcribe(
    segments: Iterable[AudioSegment],
    num_speakers_hint: int | None = None,
    *,
    model: str | None = None,
) -> Transcript:
    """Run WhisperX on the given segments and return a Transcript.

    Phase 1 contract:
    - Single-speaker mode: every Word + Turn carries speaker_raw="SPEAKER_00".
    - num_speakers_hint is accepted in the signature but ignored (Phase 2 wires
      it into pyannote diarization).
    - Word timestamps are populated. WER ≤ 15% on the clean fixture.
    - Model defaults to config; tests pass `model="tiny.en"` explicitly.
    """
    raise NotImplementedError("transcribe: implemented in Phase 1")
