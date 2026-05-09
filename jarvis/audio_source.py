"""Audio capture abstraction. PRD §3.1.

Pipeline depends only on the `AudioSource` protocol; sources are interchangeable.
Implementations land in Phase 1.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from .types import AudioChunk


class AudioSource(Protocol):
    sample_rate: int
    channels: int
    source_label: str

    def __iter__(self) -> Iterator[AudioChunk]: ...
    def close(self) -> None: ...
