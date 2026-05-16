"""Tests for jarvis.transcriber.

Two layers:

1. Fast unit test (default CI) — mocks faster_whisper.WhisperModel so the
   whole transcribe() path is exercised in <1s without loading any real
   model. Validates the AudioSegment → Transcript shape, the speaker-tag
   convention (every Word + Turn carries "SPEAKER_00" in Phase 1), the
   t_start offsetting, and that empty whisper output is skipped.

2. Slow ml-marked test (skipped in default CI, run by the finalizer) —
   loads the pre-cached ``tiny.en`` faster-whisper model from the local HF
   cache and runs it against a slice of the synthetic fixture WAV. We do
   *not* assert on text content (synthetic tones produce nonsense), only
   on the structural invariants: Transcript shape, speaker tagging, and
   monotonic timestamps within a turn.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from jarvis import transcriber
from jarvis.types import AudioSegment, Transcript, Turn, Word

FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "synthetic_5s.wav"


# --- Fakes for the mocked unit test --------------------------------------


class _FakeWord:
    def __init__(self, start: float, end: float, word: str, probability: float) -> None:
        self.start = start
        self.end = end
        self.word = word
        self.probability = probability


class _FakeWhisperSegment:
    def __init__(self, start: float, end: float, text: str, words: list[_FakeWord]) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class _FakeInfo:
    language = "en"
    language_probability = 0.99


class _FakeWhisperModel:
    """Minimal stand-in for faster_whisper.WhisperModel.

    Mirrors the (segments_iterator, info) tuple return shape of
    ``WhisperModel.transcribe``. Each call yields a single voiced segment
    or no segments at all, depending on the audio length, so we can drive
    the "skip empty segments" branch from the test side.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.init_args = args
        self.init_kwargs = kwargs

    def transcribe(self, audio: np.ndarray, **_kwargs: Any) -> tuple[Any, Any]:
        # Heuristic: a >0.5s segment yields fake speech; shorter yields nothing.
        # 16 kHz mono assumed.
        if audio.shape[0] >= 8000:
            words = [
                _FakeWord(start=0.10, end=0.30, word="hello", probability=0.95),
                _FakeWord(start=0.35, end=0.60, word="world", probability=0.88),
            ]
            seg = _FakeWhisperSegment(start=0.10, end=0.60, text=" hello world", words=words)
            return iter([seg]), _FakeInfo()
        return iter([]), _FakeInfo()


def _silence_segment(t_start: float, t_end: float) -> AudioSegment:
    n = int((t_end - t_start) * 16000)
    return AudioSegment(pcm=np.zeros(n, dtype=np.int16), t_start=t_start, t_end=t_end)


# --- Fast unit test ------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_model_cache() -> None:
    """Don't let one test's cached model leak into another."""
    transcriber._MODEL_CACHE.clear()
    yield
    transcriber._MODEL_CACHE.clear()


def test_transcribe_with_mocked_whisper_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcriber, "_load_model", lambda name: _FakeWhisperModel())

    seg_a = _silence_segment(t_start=10.0, t_end=11.0)  # >0.5s → fake words
    seg_b = _silence_segment(t_start=20.0, t_end=20.2)  # <0.5s → empty whisper output → skipped
    seg_c = _silence_segment(t_start=30.0, t_end=31.0)

    transcript = transcriber.transcribe([seg_a, seg_b, seg_c], model="tiny.en")

    assert isinstance(transcript, Transcript)
    assert transcript.language == "en"
    # seg_b is skipped because the fake whisper produced no text/words.
    assert len(transcript.turns) == 2

    turn_a = transcript.turns[0]
    assert isinstance(turn_a, Turn)
    assert turn_a.speaker_raw == "SPEAKER_00"
    assert turn_a.t_start == 10.0
    assert turn_a.t_end == 11.0
    assert turn_a.text == "hello world"
    assert len(turn_a.words) == 2

    w0, w1 = turn_a.words
    assert isinstance(w0, Word)
    assert w0.text == "hello"
    assert w0.speaker_raw == "SPEAKER_00"
    # Word timestamps should be offset by the segment's t_start.
    assert w0.t_start == pytest.approx(10.10)
    assert w0.t_end == pytest.approx(10.30)
    assert w1.t_start == pytest.approx(10.35)
    assert w1.t_end == pytest.approx(10.60)
    # Confidence forwarded from probability.
    assert w0.confidence == pytest.approx(0.95)
    assert w1.confidence == pytest.approx(0.88)

    # Every word in every turn must carry the Phase 1 speaker tag.
    for turn in transcript.turns:
        assert turn.speaker_raw == "SPEAKER_00"
        for word in turn.words:
            assert word.speaker_raw == "SPEAKER_00"


def test_transcribe_accepts_num_speakers_hint_but_ignores_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transcriber, "_load_model", lambda name: _FakeWhisperModel())
    seg = _silence_segment(t_start=0.0, t_end=1.0)

    a = transcriber.transcribe([seg], num_speakers_hint=None, model="tiny.en")
    b = transcriber.transcribe([seg], num_speakers_hint=3, model="tiny.en")

    assert len(a.turns) == len(b.turns) == 1
    assert a.turns[0].speaker_raw == b.turns[0].speaker_raw == "SPEAKER_00"


def test_transcribe_empty_segments_returns_empty_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transcriber, "_load_model", lambda name: _FakeWhisperModel())
    transcript = transcriber.transcribe([], model="tiny.en")
    assert transcript.turns == []
    assert transcript.language == "en"


# --- Slow ml test --------------------------------------------------------


def _read_wav_slice(path: Path, t_start: float, t_end: float) -> AudioSegment:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    pcm = np.frombuffer(raw, dtype=np.int16)
    if n_channels > 1:
        pcm = pcm.reshape(-1, n_channels).mean(axis=1).astype(np.int16)
    start_idx = int(t_start * sr)
    end_idx = int(t_end * sr)
    return AudioSegment(pcm=pcm[start_idx:end_idx].copy(), t_start=t_start, t_end=t_end)


@pytest.mark.ml
def test_transcribe_real_tiny_en_against_synthetic_fixture() -> None:
    """End-to-end with a real (cached) tiny.en model.

    The synthetic fixture is tones, not speech, so we make NO claims about
    the transcribed text — just that the call returns a well-formed
    Transcript with our Phase 1 speaker convention and monotonic word
    timestamps within each turn.
    """
    pytest.importorskip("faster_whisper")
    assert FIXTURE_WAV.exists(), f"missing test fixture: {FIXTURE_WAV}"

    seg = _read_wav_slice(FIXTURE_WAV, t_start=0.5, t_end=2.0)
    assert seg.pcm.dtype == np.int16
    assert seg.pcm.shape[0] > 0

    transcript = transcriber.transcribe([seg], model="tiny.en")

    assert isinstance(transcript, Transcript)
    assert transcript.language == "en"
    # turns may be 0 (whisper found no speech) or >=1; both are acceptable.
    for turn in transcript.turns:
        assert isinstance(turn, Turn)
        assert turn.speaker_raw == "SPEAKER_00"
        assert turn.t_start == pytest.approx(0.5)
        assert turn.t_end == pytest.approx(2.0)
        prev_end = -1.0
        for word in turn.words:
            assert isinstance(word, Word)
            assert word.speaker_raw == "SPEAKER_00"
            assert word.t_start <= word.t_end
            # Monotonic non-decreasing within the turn.
            assert word.t_start >= prev_end - 1e-6
            prev_end = word.t_end
            # Word timestamps live on the session timeline (offset by t_start).
            assert word.t_start >= seg.t_start - 1e-6
