"""Recording session orchestrator. PRD §3.14.

The recorder is the single entry point that owns a session end-to-end:
pidfile, audio source, segmenter, transcriber, persister. Phase 1 runs the
pipeline post-stop (not streaming) on a session WAV that the source wrote
to disk during capture.

Implemented in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .audio_source import AudioSource


class RecorderAlreadyRunning(RuntimeError):
    """Raised when a pidfile points at a live recorder process."""


@dataclass
class RecorderResult:
    session_uuid: str
    recording_id: int | None  # None if pipeline failed but WAV is on disk
    audio_path: Path
    turns_written: int


def run(source: AudioSource, *, session_uuid: str | None = None) -> RecorderResult:
    """Run a full recording session and return the persisted result.

    Phase 1 contract:
    - Writes pidfile on entry, clears on exit (success or failure).
    - On SIGTERM, closes the source gracefully and runs the pipeline.
    - Pipeline failure does NOT delete the WAV; re-run via `jarvis process`.
    - Single-speaker mode: all turns get speaker_raw="SPEAKER_00".
    """
    raise NotImplementedError("recorder.run: implemented in Phase 1")
