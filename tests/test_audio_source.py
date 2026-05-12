"""Tests for jarvis.audio_source. Phase 1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from jarvis.audio_source import MicSource, WavFileSource

FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "synthetic_5s.wav"


# ----- WavFileSource ---------------------------------------------------


def test_wav_file_source_iterates_full_duration() -> None:
    src = WavFileSource(FIXTURE_WAV)
    chunks = list(src)
    assert chunks, "expected at least one chunk"

    # Each chunk's pcm length determines its duration; sum should ≈ 5.0s.
    total_samples = sum(c.pcm.shape[0] for c in chunks)
    assert abs(total_samples / src.sample_rate - 5.0) < 0.1

    # Chunks tile the source contiguously: t_end of chunk N == t_start of N+1.
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert abs(prev.t_end - nxt.t_start) < 1e-6

    # First chunk starts at 0, dtype is int16, mono.
    assert chunks[0].t_start == 0.0
    assert chunks[0].pcm.dtype == np.int16
    assert chunks[0].pcm.ndim == 1


def test_wav_file_source_label() -> None:
    src = WavFileSource(FIXTURE_WAV)
    assert src.source_label == "wav:synthetic_5s.wav"


def test_wav_file_source_close_is_idempotent() -> None:
    src = WavFileSource(FIXTURE_WAV)
    src.close()
    src.close()  # must not raise


def test_iter_after_close_raises() -> None:
    src = WavFileSource(FIXTURE_WAV)
    src.close()
    with pytest.raises(RuntimeError):
        list(iter(src))


def test_wav_file_source_chunk_seconds_respected(tmp_path: Path) -> None:
    src = WavFileSource(FIXTURE_WAV, chunk_seconds=0.5)
    chunks = list(src)
    # 5s @ 0.5s = 10 chunks (last may be shorter; here exact).
    assert len(chunks) == 10
    for c in chunks:
        assert c.pcm.shape[0] <= int(0.5 * src.sample_rate)


def test_wav_file_source_rejects_bad_pacing() -> None:
    with pytest.raises(ValueError):
        WavFileSource(FIXTURE_WAV, pacing="medium")


def test_wav_file_source_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        WavFileSource(tmp_path / "nope.wav")


# ----- MicSource (mocked) ----------------------------------------------


class _FakeStream:
    """Stand-in for sounddevice.InputStream.

    Captures the callback so the test can drive PCM through the source
    without touching real audio hardware.
    """

    def __init__(self, callback) -> None:
        self.callback = callback
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


def _make_mic_source(tmp_path: Path) -> tuple[MicSource, _FakeStream]:
    """Build a MicSource whose stream is replaced by `_FakeStream`."""
    fake_holder: dict[str, _FakeStream] = {}

    def fake_input_stream(*, callback, **_kwargs) -> _FakeStream:
        s = _FakeStream(callback)
        fake_holder["stream"] = s
        return s

    with patch("sounddevice.InputStream", side_effect=fake_input_stream):
        src = MicSource(tmp_path / "session.wav")
    return src, fake_holder["stream"]


def _push_pcm(stream: _FakeStream, n_samples: int, *, value: int = 1000) -> None:
    """Drive the captured callback with a chunk of fake PCM."""
    pcm = np.full((n_samples, 1), value, dtype=np.int16)
    stream.callback(pcm, n_samples, None, None)


def test_mic_source_writes_wav(tmp_path: Path) -> None:
    src, stream = _make_mic_source(tmp_path)
    out = tmp_path / "session.wav"

    # Iterate in a thread-like loop: feed callbacks, drain the queue.
    iterator = iter(src)
    assert stream.started

    _push_pcm(stream, 1600, value=500)  # 0.1s
    _push_pcm(stream, 1600, value=-500)
    chunk1 = next(iterator)
    chunk2 = next(iterator)
    assert chunk1.pcm.shape[0] == 1600
    assert chunk2.pcm.shape[0] == 1600

    src.close()
    assert stream.stopped
    assert stream.closed

    # Re-open and verify integrity.
    data, sr = sf.read(str(out), dtype="int16")
    assert sr == 16000
    assert data.shape[0] == 3200
    # First 1600 samples should be 500, next 1600 should be -500.
    assert np.all(data[:1600] == 500)
    assert np.all(data[1600:] == -500)


def test_mic_source_yields_chunks(tmp_path: Path) -> None:
    src, stream = _make_mic_source(tmp_path)
    iterator = iter(src)

    _push_pcm(stream, 800, value=100)
    chunk = next(iterator)
    assert chunk.pcm.dtype == np.int16
    assert chunk.t_start == 0.0
    assert abs(chunk.t_end - 800 / 16000) < 1e-9

    _push_pcm(stream, 800, value=200)
    chunk2 = next(iterator)
    assert abs(chunk2.t_start - 800 / 16000) < 1e-9
    assert abs(chunk2.t_end - 1600 / 16000) < 1e-9

    src.close()


def test_mic_source_close_unblocks_iteration(tmp_path: Path) -> None:
    src, _stream = _make_mic_source(tmp_path)
    iterator = iter(src)
    src.close()
    # No more chunks; sentinel should end the loop.
    with pytest.raises(StopIteration):
        next(iterator)


def test_mic_source_close_is_idempotent(tmp_path: Path) -> None:
    src, _stream = _make_mic_source(tmp_path)
    src.close()
    src.close()  # must not raise


def test_mic_source_label(tmp_path: Path) -> None:
    src, _stream = _make_mic_source(tmp_path)
    assert src.source_label == "mic"
    src.close()


def test_mic_source_double_iter_raises(tmp_path: Path) -> None:
    src, _stream = _make_mic_source(tmp_path)
    iter(src)
    with pytest.raises(RuntimeError):
        iter(src)
    src.close()
