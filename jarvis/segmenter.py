"""VAD + chunking. PRD §3.2."""

from __future__ import annotations

from collections.abc import Iterator

from .audio_source import AudioSource
from .types import AudioSegment


def segment(source: AudioSource) -> Iterator[AudioSegment]:
    raise NotImplementedError("segment: implemented in Phase 1")
