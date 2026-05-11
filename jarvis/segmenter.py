"""VAD + chunking. PRD §3.2.

Converts continuous audio into utterance-bounded segments suitable for Whisper.
Implementation: Silero VAD. Adjacent voiced regions merge; cap segment length
at 30s; minimum segment 0.5s.

Implemented in Phase 1.
"""

from __future__ import annotations

from collections.abc import Iterator

from .audio_source import AudioSource
from .types import AudioSegment

MIN_SEGMENT_SECONDS = 0.5
MAX_SEGMENT_SECONDS = 30.0


def segment(source: AudioSource) -> Iterator[AudioSegment]:
    """Yield voiced AudioSegments from an AudioSource.

    Phase 1 contract:
    - Reads the entire source (Phase 1 always reads a WAV; live mic is
      buffered to disk and re-read post-stop per PRD §2.1).
    - Skips segments shorter than MIN_SEGMENT_SECONDS.
    - Splits at MAX_SEGMENT_SECONDS to keep Whisper happy.
    - Boundaries match ground truth within ±200ms on the test fixture.
    """
    raise NotImplementedError("segment: implemented in Phase 1")
