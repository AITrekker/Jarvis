"""Tests for jarvis.speaker_resolver. Phase 2.

Two layers:
1. Unit tests with the embedding model mocked. Fast, default CI.
2. Integration tests against testcontainer Postgres, also with the
   embedding model mocked so we exercise SQL paths without loading
   multi-GB pyannote weights.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import psycopg
import pytest

from jarvis import speaker_resolver
from jarvis.types import EnrolledSpeaker, Transcript, Turn, Word

# --- Helpers -----------------------------------------------------------------


def _make_word(text: str, t_start: float, t_end: float, speaker: str = "SPEAKER_00") -> Word:
    return Word(text=text, t_start=t_start, t_end=t_end, speaker_raw=speaker, confidence=0.9)


def _make_transcript(words_per_speaker: dict[str, list[tuple[float, float, str]]]) -> Transcript:
    turns: list[Turn] = []
    for speaker, spans in words_per_speaker.items():
        words = [_make_word(text, s, e, speaker=speaker) for s, e, text in spans]
        if not words:
            continue
        turns.append(
            Turn(
                speaker_raw=speaker,
                t_start=words[0].t_start,
                t_end=words[-1].t_end,
                text=" ".join(w.text for w in words),
                words=words,
            )
        )
    return Transcript(turns=turns, language="en")


def _make_audio(seconds: float, sample_rate: int = 16000) -> np.ndarray:
    return np.zeros(int(seconds * sample_rate), dtype=np.int16)


# --- Unit: cosine + helpers --------------------------------------------------


def test_cosine_identity_is_one() -> None:
    a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert speaker_resolver._cosine(a, a) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero() -> None:
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    assert speaker_resolver._cosine(a, b) == pytest.approx(0.0)


def test_cosine_zero_vector_is_zero() -> None:
    a = np.array([0.0, 0.0], dtype=np.float32)
    b = np.array([1.0, 1.0], dtype=np.float32)
    assert speaker_resolver._cosine(a, b) == 0.0


def test_pgvector_string_roundtrip() -> None:
    arr = np.array([1.0, -2.5, 3.125], dtype=np.float32)
    s = speaker_resolver._array_to_pgvector(arr)
    back = speaker_resolver._pgvector_to_array(s)
    assert back.dtype == np.float32
    np.testing.assert_array_almost_equal(back, arr, decimal=5)


def test_slice_speaker_audio_concat() -> None:
    sr = 16000
    audio = np.arange(sr, dtype=np.int16)  # 1s ramp
    words = [_make_word("a", 0.1, 0.2), _make_word("b", 0.5, 0.7)]
    sliced = speaker_resolver._slice_speaker_audio(audio, sr, words)
    assert sliced.shape[0] == int(0.1 * sr) + int(0.2 * sr)


# --- Unit: resolve_speakers with mocked embedder ----------------------------


def test_resolve_speakers_above_high_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    me_emb = np.array([1.0, 0.0, 0.0] + [0.0] * 189, dtype=np.float32)
    them_emb = np.array([0.0, 1.0, 0.0] + [0.0] * 189, dtype=np.float32)

    def fake_load() -> list[EnrolledSpeaker]:
        return [
            EnrolledSpeaker(person_id=1, display_name="me", embedding=me_emb, is_self=True),
        ]

    monkeypatch.setattr(speaker_resolver, "load_enrolled_speakers", lambda **k: fake_load())
    # Mock the embedder so the centroid matches the enrolled "me" vector.
    monkeypatch.setattr(speaker_resolver, "_embed_audio", lambda pcm, sr: me_emb.copy())

    transcript = _make_transcript({"SPEAKER_00": [(0.0, 1.0, "hello"), (1.0, 2.0, "world")]})
    audio = _make_audio(2.0)

    out = speaker_resolver.resolve_speakers(transcript, audio, 16000)
    assert "SPEAKER_00" in out
    rs = out["SPEAKER_00"]
    assert rs.person_id == 1
    assert rs.display_name == "me"
    assert rs.confidence == pytest.approx(1.0)
    assert rs.needs_review is False
    # them_emb didn't make the candidate list; just confirm the orth case
    # would have been rejected.
    assert speaker_resolver._cosine(me_emb, them_emb) < speaker_resolver.THRESHOLD_LOW


def test_resolve_speakers_unenrolled_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speaker_resolver, "load_enrolled_speakers", lambda **k: [])
    monkeypatch.setattr(
        speaker_resolver, "_embed_audio", lambda pcm, sr: np.ones(192, dtype=np.float32)
    )

    transcript = _make_transcript({"SPEAKER_00": [(0.0, 1.0, "hi")]})
    out = speaker_resolver.resolve_speakers(
        transcript, _make_audio(1.5), 16000, session_uuid="abcd1234"
    )
    rs = out["SPEAKER_00"]
    assert rs.person_id is None
    assert rs.display_name.startswith("unknown_abcd1234_")
    assert rs.needs_review is True


def test_resolve_speakers_between_thresholds_needs_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Build candidate embedding such that cosine ≈ 0.65 against the centroid.
    target = np.zeros(192, dtype=np.float32)
    target[0] = 1.0
    cand = np.zeros(192, dtype=np.float32)
    cand[0] = 0.65
    cand[1] = float(np.sqrt(1 - 0.65**2))

    monkeypatch.setattr(
        speaker_resolver,
        "load_enrolled_speakers",
        lambda **k: [
            EnrolledSpeaker(person_id=2, display_name="bob", embedding=cand, is_self=False)
        ],
    )
    monkeypatch.setattr(speaker_resolver, "_embed_audio", lambda pcm, sr: target.copy())

    transcript = _make_transcript({"SPEAKER_00": [(0.0, 1.0, "hi")]})
    out = speaker_resolver.resolve_speakers(transcript, _make_audio(1.0), 16000)
    rs = out["SPEAKER_00"]
    assert rs.person_id == 2
    assert rs.display_name == "bob"
    assert speaker_resolver.THRESHOLD_LOW <= rs.confidence < speaker_resolver.THRESHOLD_HIGH
    assert rs.needs_review is True


def test_resolve_speakers_short_audio_skips_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Words covering < 0.5s total — should not call the embedder.
    monkeypatch.setattr(speaker_resolver, "load_enrolled_speakers", lambda **k: [])

    def fail_embed(pcm: np.ndarray, sr: int) -> np.ndarray:
        raise AssertionError("embedder should not be called for sub-0.5s audio")

    monkeypatch.setattr(speaker_resolver, "_embed_audio", fail_embed)

    transcript = _make_transcript({"SPEAKER_00": [(0.0, 0.1, "hi")]})
    out = speaker_resolver.resolve_speakers(transcript, _make_audio(0.5), 16000)
    rs = out["SPEAKER_00"]
    assert rs.person_id is None
    assert rs.display_name.startswith("unknown_")


def test_resolve_speakers_int16_typecheck() -> None:
    transcript = _make_transcript({"SPEAKER_00": [(0.0, 1.0, "hi")]})
    bad = np.zeros(16000, dtype=np.float32)
    with pytest.raises(TypeError, match="int16"):
        speaker_resolver.resolve_speakers(transcript, bad, 16000)


def test_resolve_speakers_empty_transcript_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(speaker_resolver, "load_enrolled_speakers", lambda **k: [])
    out = speaker_resolver.resolve_speakers(
        Transcript(turns=[], language="en"), _make_audio(0.1), 16000
    )
    assert out == {}


# --- Integration: SQL paths against testcontainer Postgres ------------------


def _make_wav(path: Path, seconds: float = 3.0, sr: int = 16000) -> None:
    n = int(seconds * sr)
    pcm = (np.sin(2 * np.pi * 220 * np.arange(n) / sr) * 8000).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


@pytest.mark.integration
def test_load_enrolled_speakers_filters_by_person_id(postgres_url: str) -> None:
    # Use uniquely-suffixed emails — the session-scoped DB is shared with
    # other integration tests that also seed `people` rows.
    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO people (display_name, email, is_self) VALUES (%s, %s, %s) RETURNING id",
            ("alice-load", "alice-load@example.com", False),
        )
        alice_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO people (display_name, email, is_self) VALUES (%s, %s, %s) RETURNING id",
            ("bob-load", "bob-load@example.com", False),
        )
        bob_id = cur.fetchone()[0]

        emb_a = np.array([1.0] + [0.0] * 191, dtype=np.float32)
        emb_b = np.array([0.0, 1.0] + [0.0] * 190, dtype=np.float32)
        for pid, emb in [(alice_id, emb_a), (bob_id, emb_b)]:
            cur.execute(
                "INSERT INTO speaker_embeddings (person_id, embedding) VALUES (%s, %s::vector)",
                (pid, speaker_resolver._array_to_pgvector(emb)),
            )

    only_alice = speaker_resolver.load_enrolled_speakers(person_ids=[alice_id])
    assert len(only_alice) == 1
    assert only_alice[0].display_name == "alice-load"
    assert only_alice[0].embedding.shape == (192,)
    np.testing.assert_array_almost_equal(only_alice[0].embedding, emb_a, decimal=5)

    # The full set must include both new rows (and may include rows from
    # other tests that ran first against the session-scoped container).
    all_enrolled = speaker_resolver.load_enrolled_speakers()
    names = {e.display_name for e in all_enrolled}
    assert {"alice-load", "bob-load"}.issubset(names)


@pytest.mark.integration
def test_enroll_self_idempotent(
    postgres_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav_path = tmp_path / "self.wav"
    _make_wav(wav_path, seconds=3.0)

    fixed_emb = np.linspace(0.0, 1.0, 192, dtype=np.float32)
    monkeypatch.setattr(speaker_resolver, "_embed_audio", lambda pcm, sr: fixed_emb.copy())

    id1 = speaker_resolver.enroll_self(wav_path, display_name="me")
    id2 = speaker_resolver.enroll_self(wav_path, display_name="me")
    # Idempotent: the second call replaces the first row, returns a new id.
    assert id1 != id2

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM people WHERE is_self = TRUE")
        (n_self,) = cur.fetchone()
        assert n_self == 1

        cur.execute(
            "SELECT COUNT(*) FROM speaker_embeddings e "
            "JOIN people p ON p.id = e.person_id WHERE p.is_self = TRUE"
        )
        (n_emb,) = cur.fetchone()
        assert n_emb == 1


@pytest.mark.integration
def test_enroll_self_rejects_short_wav(
    postgres_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav_path = tmp_path / "tiny.wav"
    _make_wav(wav_path, seconds=0.5)
    monkeypatch.setattr(
        speaker_resolver, "_embed_audio", lambda pcm, sr: np.zeros(192, dtype=np.float32)
    )
    with pytest.raises(ValueError, match="shorter than 2s"):
        speaker_resolver.enroll_self(wav_path, display_name="me")


@pytest.mark.integration
def test_enroll_from_session(
    postgres_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav_path = tmp_path / "session.wav"
    _make_wav(wav_path, seconds=4.0)

    # Seed a recording + a couple of turns for SPEAKER_00.
    session_uuid = "11111111-1111-1111-1111-111111111111"
    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recordings (session_uuid, audio_path, source_label, started_at, ended_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING id
            """,
            (session_uuid, str(wav_path), "wav:test"),
        )
        rec_id = cur.fetchone()[0]
        for s, e in [(0.0, 1.0), (2.0, 3.0)]:
            cur.execute(
                "INSERT INTO turns (recording_id, speaker_raw, t_start, t_end, text) "
                "VALUES (%s, %s, %s, %s, %s)",
                (rec_id, "SPEAKER_00", s, e, "hi"),
            )

    fixed_emb = np.linspace(-1.0, 1.0, 192, dtype=np.float32)
    monkeypatch.setattr(speaker_resolver, "_embed_audio", lambda pcm, sr: fixed_emb.copy())

    new_id = speaker_resolver.enroll_from_session(
        session_uuid, "SPEAKER_00", "Alice Example", person_email="alice2@example.com"
    )
    assert new_id > 0

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT person_id, source_recording_id FROM speaker_embeddings WHERE id = %s",
            (new_id,),
        )
        person_id, src_rec = cur.fetchone()
        assert src_rec == rec_id
        cur.execute("SELECT display_name, email FROM people WHERE id = %s", (person_id,))
        name, email = cur.fetchone()
        assert name == "Alice Example"
        assert email == "alice2@example.com"


@pytest.mark.integration
def test_enroll_from_session_rejects_unknown_session(postgres_url: str) -> None:
    with pytest.raises(ValueError, match="no recording found"):
        speaker_resolver.enroll_from_session(
            "00000000-0000-0000-0000-000000000000", "SPEAKER_00", "ghost"
        )
