"""Audio capture abstraction. PRD §3.1.

Pipeline depends only on the `AudioSource` protocol; sources are interchangeable.
Per PRD §2.1, MicSource writes incoming PCM to a session WAV on disk; the
segmenter and transcriber always read from a WAV file post-stop. There is no
streaming pipeline in v1.

Implementations land in Phase 1.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile as sf

from .types import AudioChunk

log = logging.getLogger(__name__)

_TARGET_SR = 16000
_TARGET_CHANNELS = 1
# Sentinel pushed onto the mic queue to signal end-of-stream.
_MIC_SENTINEL: object = object()
# Cap the mic queue at ~60s of audio (PRD §2.1). On overflow we drop the
# oldest chunk with a logged warning; the on-disk WAV is the source of
# truth, so dropping in-memory chunks does not lose recording fidelity.
_MIC_QUEUE_MAX_SECONDS = 60.0


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

    sample_rate: int = _TARGET_SR
    channels: int = _TARGET_CHANNELS

    def __init__(
        self,
        path: Path | str,
        *,
        pacing: str = "fast",
        chunk_seconds: float = 1.0,
    ) -> None:
        if pacing not in ("fast", "real"):
            raise ValueError(f"pacing must be 'fast' or 'real', got {pacing!r}")
        if chunk_seconds <= 0:
            raise ValueError(f"chunk_seconds must be > 0, got {chunk_seconds}")

        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(self._path)

        self._pacing = pacing
        self._chunk_seconds = chunk_seconds
        self._closed = False

        # Read whole file; Phase 1 fixtures are small, simple is fine.
        data, sr = sf.read(str(self._path), dtype="int16", always_2d=False)

        # Downmix to mono if needed.
        if data.ndim == 2:
            # Average across channels and round back to int16.
            data = data.mean(axis=1).astype(np.int16)

        # Resample if needed. The Phase 1 fixture is already 16k mono, but
        # handle the off-path defensively rather than raising.
        if sr != _TARGET_SR:
            data = _resample_int16(data, sr, _TARGET_SR)
            sr = _TARGET_SR

        # Ensure contiguous int16.
        self._pcm: np.ndarray = np.ascontiguousarray(data, dtype=np.int16)
        self._sr = sr
        self._chunk_samples = max(1, int(round(chunk_seconds * self._sr)))

    @property
    def source_label(self) -> str:
        return f"wav:{self._path.name}"

    @property
    def path(self) -> Path:
        """Absolute path to the WAV file. Used by the Recorder to resolve
        the session audio for the post-stop pipeline (PRD §2.1)."""
        return self._path

    def __iter__(self) -> Iterator[AudioChunk]:
        if self._closed:
            raise RuntimeError("WavFileSource: iteration after close()")

        total = self._pcm.shape[0]
        n = self._chunk_samples
        sr = float(self._sr)
        wall_start = time.monotonic()

        for start in range(0, total, n):
            if self._closed:
                # close() called mid-iteration; stop cleanly.
                return
            end = min(start + n, total)
            chunk = self._pcm[start:end]
            t_start = start / sr
            t_end = end / sr

            if self._pacing == "real":
                target = wall_start + t_end
                now = time.monotonic()
                if target > now:
                    time.sleep(target - now)

            yield AudioChunk(pcm=chunk, t_start=t_start, t_end=t_end)

    def close(self) -> None:
        # Idempotent.
        self._closed = True


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

    sample_rate: int = _TARGET_SR
    channels: int = _TARGET_CHANNELS

    def __init__(self, wav_out_path: Path) -> None:
        # Imported here so test environments without PortAudio installed can
        # still import the module (e.g. for type checking).
        import sounddevice as sd  # noqa: F401  (used via _stream_factory)

        self._wav_out_path = Path(wav_out_path)
        self._wav_out_path.parent.mkdir(parents=True, exist_ok=True)

        self._closed = False
        self._started = False
        self._iter_started = False
        self._t0_samples = 0  # running sample count for timestamping

        # Bounded queue: ~60s @ 16 kHz, conservatively assuming the smallest
        # PortAudio chunk size is 256 samples (~16ms). 60s / 16ms ≈ 3750.
        # Drop-oldest on overflow per PRD §2.1.
        self._queue: queue.Queue = queue.Queue(
            maxsize=int(_MIC_QUEUE_MAX_SECONDS * _TARGET_SR / 256)
        )
        self._dropped_chunks = 0
        self._lock = threading.Lock()

        # WAV file is opened up-front so the first callback can write
        # immediately. Closed in `close()`.
        self._wav = sf.SoundFile(
            str(self._wav_out_path),
            mode="w",
            samplerate=_TARGET_SR,
            channels=_TARGET_CHANNELS,
            subtype="PCM_16",
        )

        # If the input stream fails to construct (no input device, permission
        # denied, PortAudio error), we must close the WAV we just opened —
        # otherwise the file handle leaks until process exit.
        try:
            self._stream = self._make_stream()
        except BaseException:
            try:
                self._wav.close()
            finally:
                # Remove the empty WAV so the data dir stays clean.
                self._wav_out_path.unlink(missing_ok=True)
            raise

    @property
    def source_label(self) -> str:
        return "mic"

    # --- internals -----------------------------------------------------

    def _make_stream(self):
        """Construct a sounddevice InputStream. Patched in tests."""
        import sounddevice as sd

        return sd.InputStream(
            samplerate=_TARGET_SR,
            channels=_TARGET_CHANNELS,
            dtype="int16",
            callback=self._callback,
        )

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            log.warning("MicSource stream status: %s", status)

        # `indata` from sounddevice is shape (frames, channels). Squeeze to 1-D
        # mono int16. We make a copy because the buffer is reused by PortAudio.
        if hasattr(indata, "ndim") and indata.ndim == 2:
            mono = indata[:, 0].copy()
        else:
            mono = np.asarray(indata, dtype=np.int16).copy()
        mono = np.ascontiguousarray(mono, dtype=np.int16)

        with self._lock:
            if self._closed:
                return
            t_start = self._t0_samples / float(_TARGET_SR)
            self._t0_samples += int(mono.shape[0])
            t_end = self._t0_samples / float(_TARGET_SR)
            try:
                self._wav.write(mono)
            except Exception:  # pragma: no cover - file I/O failure mid-stream
                log.exception("MicSource: failed to write WAV chunk")

        chunk = AudioChunk(pcm=mono, t_start=t_start, t_end=t_end)
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            # Drop oldest, push newest. The WAV-on-disk is the source of
            # truth; we only lose live-monitoring fidelity, not recording
            # data. Log periodically so a wedged consumer is visible.
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()
            self._dropped_chunks += 1
            if self._dropped_chunks % 100 == 1:
                log.warning(
                    "MicSource queue full; dropped %d chunks (consumer is slow)",
                    self._dropped_chunks,
                )
            with contextlib.suppress(queue.Full):  # pragma: no cover - extremely rare race
                self._queue.put_nowait(chunk)

    # --- public API ----------------------------------------------------

    def __iter__(self) -> Iterator[AudioChunk]:
        if self._iter_started:
            raise RuntimeError("MicSource is single-shot; cannot re-iterate")
        self._iter_started = True

        if not self._started and not self._closed:
            self._stream.start()
            self._started = True

        return self._drain()

    def _drain(self) -> Iterator[AudioChunk]:
        while True:
            item = self._queue.get()
            if item is _MIC_SENTINEL:
                return
            yield item

    def close(self) -> None:
        # Idempotent.
        with self._lock:
            if self._closed:
                return
            self._closed = True

        # Stop and close the sounddevice stream first to ensure no further
        # callbacks fire while we close the WAV.
        try:
            self._stream.stop()
        except Exception:  # pragma: no cover - defensive
            log.exception("MicSource: error stopping stream")
        try:
            self._stream.close()
        except Exception:  # pragma: no cover
            log.exception("MicSource: error closing stream")

        try:
            self._wav.close()
        except Exception:  # pragma: no cover
            log.exception("MicSource: error closing WAV")

        # Wake any iterator that's blocked on the queue.
        self._queue.put(_MIC_SENTINEL)


def _resample_int16(pcm: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Linear-interp resample for the off-path. Phase 1 fixture never hits this.

    Adequate for tone fixtures / fallback scenarios; production pipeline's
    mic and WAV inputs are already 16 kHz so this code path stays cold.
    """
    if src_sr == dst_sr:
        return pcm.astype(np.int16, copy=False)
    n_src = pcm.shape[0]
    n_dst = max(1, int(round(n_src * dst_sr / src_sr)))
    src_idx = np.linspace(0, n_src - 1, num=n_dst, dtype=np.float64)
    floor = np.floor(src_idx).astype(np.int64)
    ceil = np.minimum(floor + 1, n_src - 1)
    frac = src_idx - floor
    out = pcm[floor].astype(np.float64) * (1.0 - frac) + pcm[ceil].astype(np.float64) * frac
    return np.clip(np.round(out), -32768, 32767).astype(np.int16)
