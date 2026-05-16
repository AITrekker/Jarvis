"""Phase 2 integration tests for recorder.run.

Validates the post-stop pipeline's calendar + speaker enrichments against
a real testcontainer Postgres. Pyannote and faster-whisper are mocked so
we exercise the SQL paths and the integration glue without loading
multi-GB models.
"""

from __future__ import annotations

import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import psycopg
import pytest

from jarvis import _proc, recorder, segmenter, speaker_resolver, transcriber
from jarvis.audio_source import WavFileSource
from jarvis.transcriber import SpeakerSegment
from jarvis.types import AudioSegment


def _write_wav(path: Path, seconds: float = 4.0, sr: int = 16000) -> None:
    n = int(seconds * sr)
    pcm = (np.sin(2 * np.pi * 220 * np.arange(n) / sr) * 8000).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


class _FakeWord:
    def __init__(self, start: float, end: float, word: str) -> None:
        self.start = start
        self.end = end
        self.word = word
        self.probability = 0.95


class _FakeWhisperSegment:
    def __init__(self, start: float, end: float, text: str, words: list[_FakeWord]) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class _FakeInfo:
    language = "en"
    language_probability = 0.99


class _FakeWhisper:
    def transcribe(self, audio: np.ndarray, **_: object) -> tuple[object, object]:
        # Always emit two words.
        words = [
            _FakeWord(0.10, 0.50, "hello"),
            _FakeWord(0.60, 0.90, "world"),
        ]
        seg = _FakeWhisperSegment(0.10, 0.90, " hello world", words)
        return iter([seg]), _FakeInfo()


class _FakeDiarizer:
    def __init__(self, segments: list[SpeakerSegment]) -> None:
        self._segments = segments

    def diarize(self, audio_path: Path, *, num_speakers: int | None = None) -> list[SpeakerSegment]:
        return list(self._segments)


@pytest.fixture
def _isolate_pidfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pidfile = tmp_path / "recorder.pid"
    monkeypatch.setattr(_proc, "default_pidfile", lambda: pidfile)


@pytest.fixture
def _force_one_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass real VAD; emit a single 0.0-1.0s AudioSegment."""

    def fake_segment(src):
        # Drain the source so its lifecycle behaves normally.
        for _ in src:
            pass
        sr = 16000
        yield AudioSegment(pcm=np.zeros(sr, dtype=np.int16), t_start=0.0, t_end=1.0)

    monkeypatch.setattr(segmenter, "segment", fake_segment)


@pytest.mark.integration
def test_recorder_phase2_persists_speakers_and_event(
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _isolate_pidfile: None,
    _force_one_segment: None,
) -> None:
    # Seed: one calendar event covering "now", one enrolled person matching
    # the diarizer's SPEAKER_01 label by mocked embedding.
    now = datetime.now(tz=UTC)
    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (google_event_id, title, started_at, ended_at)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            ("evt-phase2", "1:1 with Alice", now - timedelta(hours=1), now + timedelta(hours=1)),
        )
        event_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO people (display_name, email) VALUES (%s, %s) RETURNING id",
            ("alice", "alice@example.com"),
        )
        alice_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO event_attendees (event_id, person_id, email)
            VALUES (%s, %s, %s)
            """,
            (event_id, alice_id, "alice@example.com"),
        )
        # Enroll alice with a known unit-vector embedding.
        emb = np.zeros(192, dtype=np.float32)
        emb[0] = 1.0
        cur.execute(
            "INSERT INTO speaker_embeddings (person_id, embedding) VALUES (%s, %s::vector)",
            (alice_id, speaker_resolver._array_to_pgvector(emb)),
        )

    # Mock whisper + diarizer + embedder. The diarizer puts both words on
    # SPEAKER_01; the embedder returns alice's exact vector for that speaker.
    monkeypatch.setattr(transcriber, "_load_model", lambda name: _FakeWhisper())
    diarizer = _FakeDiarizer([SpeakerSegment("SPEAKER_01", 0.0, 5.0)])
    monkeypatch.setattr(transcriber, "get_diarizer", lambda: diarizer)
    monkeypatch.setattr(speaker_resolver, "_embed_audio", lambda pcm, sr: emb.copy())

    # Fake WAV input.
    wav = tmp_path / "session.wav"
    _write_wav(wav, seconds=2.0)
    src = WavFileSource(wav)

    result = recorder.run(src, session_uuid="22222222-2222-2222-2222-222222222222")

    assert result.recording_id is not None
    assert result.turns_written >= 1

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT event_id FROM recordings WHERE id = %s", (result.recording_id,))
        (persisted_event_id,) = cur.fetchone()
        assert persisted_event_id == event_id

        cur.execute(
            "SELECT speaker_raw, person_id, speaker_confidence, needs_review "
            "FROM turns WHERE recording_id = %s ORDER BY t_start",
            (result.recording_id,),
        )
        rows = cur.fetchall()
        assert rows, "expected at least one turn"
        for speaker_raw, person_id, conf, needs_review in rows:
            assert speaker_raw == "SPEAKER_01"
            assert person_id == alice_id
            assert conf == pytest.approx(1.0, rel=1e-3)
            assert needs_review is False


@pytest.mark.integration
def test_recorder_phase2_diarizer_failure_falls_back(
    postgres_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _isolate_pidfile: None,
    _force_one_segment: None,
) -> None:
    """If pyannote fails to load, recorder still persists with single-speaker."""
    monkeypatch.setattr(transcriber, "_load_model", lambda name: _FakeWhisper())

    def boom() -> object:
        raise RuntimeError("simulated pyannote load failure")

    monkeypatch.setattr(transcriber, "get_diarizer", boom)

    wav = tmp_path / "session.wav"
    _write_wav(wav, seconds=1.5)
    src = WavFileSource(wav)

    result = recorder.run(src, session_uuid="33333333-3333-3333-3333-333333333333")
    assert result.recording_id is not None

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT speaker_raw, person_id FROM turns WHERE recording_id = %s",
            (result.recording_id,),
        )
        for speaker_raw, person_id in cur.fetchall():
            assert speaker_raw == "SPEAKER_00"  # phase 1 fallback
            assert person_id is None
