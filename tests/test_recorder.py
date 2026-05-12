"""Recorder unit tests. PRD §3.14.

Mocks all neighboring modules — audio_source / segmenter / transcriber /
persister — so the recorder is exercised in isolation. Real audio + DB
behavior is covered by tests/test_persister.py and the end-to-end smoke.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from jarvis import _proc, recorder
from jarvis.types import AudioChunk, Transcript


class FakeWavSource:
    """Stand-in for WavFileSource: yields N AudioChunks then exhausts."""

    sample_rate = 16000
    channels = 1

    def __init__(self, path: Path, *, n_chunks: int = 2) -> None:
        self.path = path
        self.source_label = f"wav:{path}"
        self._n = n_chunks
        self.closed = False

    def __iter__(self) -> Iterator[AudioChunk]:
        import numpy as np

        for i in range(self._n):
            yield AudioChunk(
                pcm=np.zeros(16000, dtype=np.int16),
                t_start=float(i),
                t_end=float(i + 1),
            )

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point pidfile + data dir at tmp_path so tests don't touch the real one."""
    monkeypatch.setenv("JARVIS_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "data"))
    return tmp_path


@pytest.fixture
def patched_pipeline(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the lazy-imported pipeline modules. Returns the recorders for assertions."""
    calls: dict[str, Any] = {"order": [], "persist_args": None}

    def fake_segment(src):
        calls["order"].append("segment")
        # exhaust the source so its close() is reachable
        list(src)
        return iter([])

    def fake_transcribe(segments, *args, **kwargs):
        calls["order"].append("transcribe")
        list(segments)
        return Transcript(turns=[], language="en")

    def fake_persist(audio_path, transcript, speakers, calendar_event, session_meta):
        calls["order"].append("persist")
        calls["persist_args"] = {
            "audio_path": audio_path,
            "transcript": transcript,
            "speakers": speakers,
            "calendar_event": calendar_event,
            "session_meta": session_meta,
        }
        return 42

    class FakePipelineWav:
        sample_rate = 16000
        channels = 1

        def __init__(self, path):
            self.path = Path(path)
            self.source_label = f"wav:{path}"
            self.closed = False

        def __iter__(self):
            return iter([])

        def close(self):
            self.closed = True

    # Use lazy import-time patching: replace the attributes the recorder reads
    # via `from . import segmenter, transcriber, persister` and via
    # `from .audio_source import WavFileSource`.
    from jarvis import audio_source as audio_source_mod
    from jarvis import persister as persister_mod
    from jarvis import segmenter as segmenter_mod
    from jarvis import transcriber as transcriber_mod

    monkeypatch.setattr(segmenter_mod, "segment", fake_segment)
    monkeypatch.setattr(transcriber_mod, "transcribe", fake_transcribe)
    monkeypatch.setattr(persister_mod, "persist_recording", fake_persist)
    monkeypatch.setattr(audio_source_mod, "WavFileSource", FakePipelineWav)

    return calls


def test_run_writes_pidfile_and_clears_it(
    isolated_runtime: Path,
    patched_pipeline: dict[str, Any],
    tmp_path: Path,
) -> None:
    """During run(), pidfile contains our PID; after, the file is gone."""
    pidfile = _proc.default_pidfile()
    assert _proc.read_pidfile(pidfile) is None

    seen: dict[str, int | None] = {}

    def spy_segment(src):
        # Sample the pidfile mid-pipeline.
        seen["pid"] = _proc.read_pidfile(pidfile)
        list(src)
        return iter([])

    from jarvis import segmenter as segmenter_mod

    segmenter_mod.segment = spy_segment  # type: ignore[assignment]

    src = FakeWavSource(tmp_path / "fake.wav")
    result = recorder.run(src)

    assert seen["pid"] == os.getpid()
    assert _proc.read_pidfile(pidfile) is None
    assert result.recording_id == 42


def test_run_pipeline_called_in_order(
    isolated_runtime: Path,
    patched_pipeline: dict[str, Any],
    tmp_path: Path,
) -> None:
    src = FakeWavSource(tmp_path / "fake.wav")
    result = recorder.run(src, session_uuid="11111111-1111-1111-1111-111111111111")

    assert patched_pipeline["order"] == ["segment", "transcribe", "persist"]
    assert result.recording_id == 42
    assert result.session_uuid == "11111111-1111-1111-1111-111111111111"
    assert src.closed
    persist_args = patched_pipeline["persist_args"]
    assert persist_args["audio_path"] == tmp_path / "fake.wav"
    assert persist_args["session_meta"].session_uuid == result.session_uuid
    assert persist_args["calendar_event"] is None
    assert persist_args["speakers"] == {}


def test_recorder_already_running(
    isolated_runtime: Path,
    patched_pipeline: dict[str, Any],
    tmp_path: Path,
) -> None:
    pidfile = _proc.default_pidfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))  # our own pid is provably alive.

    with pytest.raises(recorder.RecorderAlreadyRunning):
        recorder.run(FakeWavSource(tmp_path / "fake.wav"))


def test_pipeline_failure_preserves_wav_and_clears_pidfile(
    isolated_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Transcriber blowing up leaves the WAV alone, clears pidfile, and
    returns a result with recording_id=None so the caller knows to retry."""
    wav_path = tmp_path / "real.wav"
    wav_path.write_bytes(b"FAKE-WAV")  # touch a file we can assert is preserved.

    from jarvis import audio_source as audio_source_mod
    from jarvis import persister as persister_mod
    from jarvis import segmenter as segmenter_mod
    from jarvis import transcriber as transcriber_mod

    class FakePipelineWav:
        sample_rate = 16000
        channels = 1

        def __init__(self, path):
            self.path = Path(path)
            self.source_label = f"wav:{path}"

        def __iter__(self):
            return iter([])

        def close(self):
            pass

    persisted = []

    def fake_segment(src):
        list(src)
        return iter([])

    def fake_transcribe(segments, *args, **kwargs):
        list(segments)
        raise RuntimeError("whisper blew up")

    def fake_persist(*args, **kwargs):
        persisted.append(args)
        return 99

    monkeypatch.setattr(audio_source_mod, "WavFileSource", FakePipelineWav)
    monkeypatch.setattr(segmenter_mod, "segment", fake_segment)
    monkeypatch.setattr(transcriber_mod, "transcribe", fake_transcribe)
    monkeypatch.setattr(persister_mod, "persist_recording", fake_persist)

    src = FakeWavSource(wav_path)
    result = recorder.run(src)

    assert result.recording_id is None
    assert result.turns_written == 0
    assert result.audio_path == wav_path
    assert wav_path.exists()
    assert wav_path.read_bytes() == b"FAKE-WAV"
    assert persisted == []  # never reached the persister
    assert _proc.read_pidfile() is None


def test_resolve_audio_path_uses_path_attribute(tmp_path: Path) -> None:
    """WavFileSource exposes .path; we should use it directly."""
    src = FakeWavSource(tmp_path / "x.wav")
    assert recorder._resolve_audio_path(src) == tmp_path / "x.wav"


def test_resolve_audio_path_uses_wav_out_path(tmp_path: Path) -> None:
    """MicSource exposes .wav_out_path."""

    class _MicLike:
        sample_rate = 16000
        channels = 1
        source_label = "mic:default"

        def __init__(self, p: Path) -> None:
            self.wav_out_path = p

        def __iter__(self):
            return iter([])

        def close(self) -> None:
            pass

    p = tmp_path / "mic.wav"
    assert recorder._resolve_audio_path(_MicLike(p)) == p


def test_resolve_audio_path_falls_back_to_label(tmp_path: Path) -> None:
    class _LabelOnly:
        sample_rate = 16000
        channels = 1
        source_label = f"wav:{tmp_path / 'fromlabel.wav'}"

        def __iter__(self):
            return iter([])

        def close(self) -> None:
            pass

    assert recorder._resolve_audio_path(_LabelOnly()) == tmp_path / "fromlabel.wav"


def test_resolve_audio_path_raises_when_unknown() -> None:
    class _Unknown:
        sample_rate = 16000
        channels = 1
        source_label = "mystery:thing"

        def __iter__(self):
            return iter([])

        def close(self) -> None:
            pass

    with pytest.raises(RuntimeError, match="Cannot determine audio path"):
        recorder._resolve_audio_path(_Unknown())
