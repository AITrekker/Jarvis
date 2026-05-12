"""Tests for jarvis.segmenter. Phase 1."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

from jarvis.audio_source import WavFileSource
from jarvis.segmenter import segment

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_WAV = FIXTURES / "synthetic_5s.wav"
FIXTURE_JSON = FIXTURES / "synthetic_5s.json"


def _expected_regions() -> tuple[list[dict], float]:
    sidecar = json.loads(FIXTURE_JSON.read_text())
    return sidecar["expected_voiced_regions"], sidecar["tolerance_seconds"]


def test_segment_finds_two_voiced_regions() -> None:
    src = WavFileSource(FIXTURE_WAV)
    segs = list(segment(src))

    expected, tol = _expected_regions()
    assert len(segs) == len(expected), (
        f"expected {len(expected)} segments, got {len(segs)}: "
        f"{[(s.t_start, s.t_end) for s in segs]}"
    )

    for seg, exp in zip(segs, expected, strict=True):
        assert abs(seg.t_start - exp["t_start"]) < tol, (
            f"t_start {seg.t_start} not within {tol} of {exp['t_start']}"
        )
        assert abs(seg.t_end - exp["t_end"]) < tol, (
            f"t_end {seg.t_end} not within {tol} of {exp['t_end']}"
        )
        assert seg.pcm.dtype == np.int16
        # PCM length should match the (t_end - t_start) interval at 16k.
        expected_samples = int(round((seg.t_end - seg.t_start) * 16000))
        assert abs(seg.pcm.shape[0] - expected_samples) <= 1


def test_segment_drops_too_short(tmp_path: Path) -> None:
    """A 0.2s burst of 'voiced' audio is below MIN_SEGMENT_SECONDS."""
    sr = 16000
    duration = 0.2
    n = int(sr * duration)

    # 440 Hz tone, fairly loud; whether or not Silero classifies the tone as
    # speech, the duration filter should kick in and drop it.
    t = np.arange(n) / sr
    tone = (0.6 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    wav_path = tmp_path / "short.wav"
    sf.write(str(wav_path), tone, sr, subtype="PCM_16")

    src = WavFileSource(wav_path)
    segs = list(segment(src))
    assert segs == []


def test_segment_empty_source(tmp_path: Path) -> None:
    """Pure silence yields no segments."""
    sr = 16000
    silence = np.zeros(sr * 2, dtype=np.int16)
    wav_path = tmp_path / "silence.wav"
    sf.write(str(wav_path), silence, sr, subtype="PCM_16")

    src = WavFileSource(wav_path)
    segs = list(segment(src))
    assert segs == []
