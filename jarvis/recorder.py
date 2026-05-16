"""Recording session orchestrator. PRD §3.14.

The recorder is the single entry point that owns a session end-to-end:
pidfile, audio source, segmenter, transcriber, persister. Phase 1 runs the
pipeline post-stop (not streaming) on a session WAV that the source wrote
to disk during capture.

Implemented in Phase 1.
"""

from __future__ import annotations

import contextlib
import logging
import signal
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import _proc
from .audio_source import AudioSource
from .types import SessionMeta

log = logging.getLogger(__name__)


class RecorderAlreadyRunning(RuntimeError):  # noqa: N818 — name fixed by PRD §3.14
    """Raised when a pidfile points at a live recorder process."""


@dataclass
class RecorderResult:
    session_uuid: str
    recording_id: int | None  # None if pipeline failed but WAV is on disk
    audio_path: Path
    turns_written: int


def _resolve_audio_path(source: AudioSource) -> Path:
    """Find the WAV file backing this source.

    The downstream pipeline (segment + transcribe) always reads from a WAV on
    disk per PRD §2.1, so every source must expose its session WAV path. We
    try the conventional attributes that `WavFileSource` and `MicSource` are
    expected to set, then fall back to parsing the source_label.
    """
    for attr in ("wav_out_path", "path", "audio_path"):
        candidate = getattr(source, attr, None)
        if candidate is not None:
            return Path(candidate)

    label = getattr(source, "source_label", "")
    if isinstance(label, str) and label.startswith("wav:"):
        return Path(label[4:])

    raise RuntimeError(
        f"Cannot determine audio path for source {type(source).__name__}; "
        "expected .wav_out_path, .path, or a 'wav:<path>' source_label."
    )


def _drain_source(source: AudioSource, stop_event: threading.Event) -> None:
    """Iterate the source until exhausted or stop_event is set.

    For `WavFileSource` this drains the file. For `MicSource` this iterates
    until close() is called from the SIGTERM handler. We don't process chunks
    live in Phase 1; the iteration is just "wait for capture to finish" and
    the WAV-on-disk drives the post-stop pipeline.
    """
    try:
        for _chunk in source:
            if stop_event.is_set():
                break
    except Exception:
        log.exception("audio source iteration failed")
        raise


def run(source: AudioSource, *, session_uuid: str | None = None) -> RecorderResult:
    """Run a full recording session and return the persisted result.

    Phase 1 contract:
    - Writes pidfile on entry, clears on exit (success or failure).
    - On SIGTERM, closes the source gracefully and runs the pipeline.
    - Pipeline failure does NOT delete the WAV; re-run via `jarvis process`.
    - Single-speaker mode: all turns get speaker_raw="SPEAKER_00".
    """
    # Imports are deferred so that the recorder module can be imported (and
    # the CLI registered) without forcing every dependency to load eagerly.
    from . import persister, segmenter, transcriber
    from .audio_source import WavFileSource

    session_uuid = session_uuid or str(uuid.uuid4())

    existing_pid = _proc.read_pidfile()
    if existing_pid is not None:
        raise RecorderAlreadyRunning(
            f"recorder already running with pid={existing_pid}; "
            "use `jarvis stop` first or wait for it to finish."
        )

    audio_path = _resolve_audio_path(source)
    started_at = datetime.now(tz=UTC)

    stop_event = threading.Event()
    previous_handler = None

    def _on_sigterm(signum: int, frame: object) -> None:  # pragma: no cover - signal path
        log.info("recorder received signal %s; closing source", signum)
        stop_event.set()
        try:
            source.close()
        except Exception:
            log.exception("source.close() raised in signal handler")

    pidfile_path = _proc.write_pidfile()
    # SIGTERM on Unix; SIGBREAK on Windows (sent by GenerateConsoleCtrlEvent
    # for CTRL_BREAK_EVENT). Windows' subprocess module delivers SIGBREAK
    # only when the child was launched with CREATE_NEW_PROCESS_GROUP — see
    # _proc.ManagedProcess. Without this branch a Windows mic recording
    # leaves an unfinalized WAV header.
    stop_signal = signal.SIGBREAK if sys.platform == "win32" else signal.SIGTERM
    try:
        previous_handler = signal.signal(stop_signal, _on_sigterm)
    except ValueError:
        # Not in main thread — skip handler, tests use this path.
        previous_handler = None

    recording_id: int | None = None
    turns_written = 0

    try:
        log.info("recorder starting session=%s audio=%s", session_uuid, audio_path)

        try:
            _drain_source(source, stop_event)
        finally:
            try:
                source.close()
            except Exception:
                log.exception("source.close() during shutdown raised")

        ended_at = datetime.now(tz=UTC)

        # Post-stop pipeline. Re-open the WAV from disk per PRD §2.1.
        try:
            pipeline_source = WavFileSource(audio_path)
            try:
                segments = list(segmenter.segment(pipeline_source))
            finally:
                try:
                    pipeline_source.close()
                except Exception:
                    log.exception("pipeline source close raised")

            transcript = transcriber.transcribe(segments)

            session_meta = SessionMeta(
                session_uuid=session_uuid,
                source_label=getattr(source, "source_label", "") or f"wav:{audio_path}",
                started_at=started_at,
                ended_at=ended_at,
            )

            recording_id = persister.persist_recording(
                audio_path=audio_path,
                transcript=transcript,
                speakers={},
                calendar_event=None,
                session_meta=session_meta,
            )
            turns_written = len(transcript.turns)
            log.info(
                "recorder finished session=%s recording_id=%s turns=%d",
                session_uuid,
                recording_id,
                turns_written,
            )
        except Exception:
            log.exception(
                "post-stop pipeline failed for session=%s; WAV preserved at %s "
                "— re-run with `jarvis process %s`",
                session_uuid,
                audio_path,
                session_uuid,
            )
            recording_id = None
            turns_written = 0
    finally:
        if previous_handler is not None:
            with contextlib.suppress(ValueError):
                signal.signal(stop_signal, previous_handler)
        _proc.clear_pidfile(pidfile_path)

    return RecorderResult(
        session_uuid=session_uuid,
        recording_id=recording_id,
        audio_path=audio_path,
        turns_written=turns_written,
    )
