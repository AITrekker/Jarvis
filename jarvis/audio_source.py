"""Audio capture abstraction. PRD §3.1.

Pipeline depends only on the `AudioSource` protocol; sources are interchangeable.
Per PRD §2.1, MicSource writes incoming PCM to a session WAV on disk; the
segmenter and transcriber always read from a WAV file post-stop. There is no
streaming pipeline in v1.

Implementations land in Phase 1.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from .types import AudioChunk


class AudioSource(Protocol):
    sample_rate: int
    channels: int
    source_label: str

    def __iter__(self) -> Iterator[AudioChunk]: ...
    def close(self) -> None: ...


class WavFileSource:
    """Reads a WAV file and emits AudioChunks. PRD §3.1.

    Phase 1 contract:
    - Mono, 16 kHz, int16. Resamples on read if the file isn't already that.
    - `pacing="fast"` emits as fast as the consumer can read; `pacing="real"`
      sleeps to match wall-clock time (used only for end-to-end demos).
    - `t_start`/`t_end` on each chunk is seconds from the start of the file.
    """

    sample_rate: int = 16000
    channels: int = 1

    def __init__(
        self,
        path: Path | str,
        *,
        pacing: str = "fast",
        chunk_seconds: float = 1.0,
    ) -> None:
        raise NotImplementedError("WavFileSource: implemented in Phase 1")

    @property
    def source_label(self) -> str:
        raise NotImplementedError

    def __iter__(self) -> Iterator[AudioChunk]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class MicSource:
    """Live mic capture via sounddevice. PRD §3.1.

    Phase 1 contract:
    - Opens default input device; mono, 16 kHz, int16.
    - **Writes incoming PCM to `wav_out_path` while iterating.** This is the
      source-of-truth recording — pipeline reads it post-stop. The yielded
      AudioChunks are a convenience for live UIs (none exist in Phase 1).
    - Iteration ends when `close()` is called (typically by SIGTERM via the
      Recorder). Closing flushes the WAV header.
    """

    sample_rate: int = 16000
    channels: int = 1

    def __init__(self, wav_out_path: Path) -> None:
        raise NotImplementedError("MicSource: implemented in Phase 1")

    @property
    def source_label(self) -> str:
        raise NotImplementedError

    def __iter__(self) -> Iterator[AudioChunk]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
