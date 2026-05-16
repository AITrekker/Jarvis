"""Voice enrollment & identity assignment. PRD §3.4.

Phase 2 — implemented 2026-05-15.

Algorithm:
1. ``resolve_speakers(transcript, audio, sample_rate, ...)``: for each unique
   ``speaker_raw`` in the transcript, gather the per-speaker audio samples
   (from each word's t_start/t_end), concat, run pyannote's embedding model
   to get a 192-dim ECAPA-TDNN centroid.
2. Cosine-similarity vs ``speaker_embeddings`` rows (optionally restricted
   to ``candidate_person_ids`` for precision).
3. Threshold gating:
   - score >= threshold_high (0.75) -> assign person, needs_review=False
   - threshold_low (0.55) <= score < high -> assign person, needs_review=True
   - score < low -> person_id=None, display_name="unknown_<sess>_<n>",
     needs_review=True

The embedding model is pyannote's `pyannote/embedding` checkpoint (192-dim
ECAPA-TDNN), matching the schema's ``VECTOR(192)`` column.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
import psycopg

from .types import EnrolledSpeaker, ResolvedSpeaker, Transcript, Word

log = logging.getLogger(__name__)

THRESHOLD_HIGH = 0.75
THRESHOLD_LOW = 0.55
# pyannote/embedding ships a 512-dim X-vector model (PRD §3.4 originally said
# 192-dim ECAPA-TDNN; that was an outdated reference — the current pyannote
# release uses 512). Schema migrations 0003+ widen speaker_embeddings.embedding
# to VECTOR(512) to match. If pyannote ships a different model in the future,
# bump this constant and write a new migration in the same PR.
EMBEDDING_DIM = 512
_EMBEDDING_MODEL_NAME = "pyannote/embedding"

# Single-slot cache for the embedding model.
_EMBEDDING_MODEL: Any | None = None
_EMBEDDING_LOCK = threading.Lock()


def _db_url() -> str:
    url = os.environ.get("JARVIS_DB_URL")
    if not url:
        raise RuntimeError(
            "JARVIS_DB_URL is not set. Configure it before running the speaker resolver."
        )
    return url


# --- Embedding model ---------------------------------------------------------


def _load_embedding_model() -> Any:
    """Lazy-load pyannote's embedding model, cached process-wide."""
    global _EMBEDDING_MODEL
    with _EMBEDDING_LOCK:
        if _EMBEDDING_MODEL is not None:
            return _EMBEDDING_MODEL
        from pyannote.audio import Model  # noqa: PLC0415
        from pyannote.audio.pipelines.speaker_verification import (
            PretrainedSpeakerEmbedding,  # noqa: PLC0415
        )

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HF_TOKEN is not set; pyannote needs a Hugging Face token to load "
                "the gated embedding model. See PRD §8."
            )
        log.info("loading pyannote embedding model %s", _EMBEDDING_MODEL_NAME)
        # PretrainedSpeakerEmbedding accepts the model checkpoint name and
        # returns a callable that maps (waveform, masks) -> (n, dim) embeddings.
        # We pass the underlying Model so we can run it on arbitrary chunks.
        try:
            _EMBEDDING_MODEL = PretrainedSpeakerEmbedding(
                _EMBEDDING_MODEL_NAME, use_auth_token=token
            )
        except TypeError:
            # Some pyannote releases changed the kwarg name.
            base_model = Model.from_pretrained(_EMBEDDING_MODEL_NAME, token=token)
            _EMBEDDING_MODEL = PretrainedSpeakerEmbedding(base_model)
        return _EMBEDDING_MODEL


def _embed_audio(pcm_int16: np.ndarray, sample_rate: int) -> np.ndarray:
    """Compute a 192-dim ECAPA-TDNN embedding for a mono int16 waveform.

    Pyannote expects float32 in [-1, 1], shape (channels, samples).
    """
    if pcm_int16.dtype != np.int16:
        raise TypeError(f"_embed_audio expects int16, got {pcm_int16.dtype}")
    waveform = pcm_int16.astype(np.float32) / 32768.0
    if waveform.ndim == 1:
        waveform = waveform[np.newaxis, :]  # (1, samples)
    model = _load_embedding_model()
    # PretrainedSpeakerEmbedding accepts a torch tensor of shape (batch, channels, samples).
    import torch  # noqa: PLC0415

    tensor = torch.from_numpy(waveform).unsqueeze(0)  # (1, 1, samples)
    embedding = model(tensor)
    if hasattr(embedding, "detach"):
        embedding = embedding.detach().cpu().numpy()
    embedding = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if embedding.shape[0] != EMBEDDING_DIM:
        raise RuntimeError(f"expected {EMBEDDING_DIM}-dim embedding, got {embedding.shape[0]}-dim")
    return embedding


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _slice_speaker_audio(
    audio: np.ndarray,
    sample_rate: int,
    words: list[Word],
) -> np.ndarray:
    """Concatenate audio samples covered by a speaker's words."""
    if not words:
        return np.zeros(0, dtype=np.int16)
    pieces: list[np.ndarray] = []
    for w in words:
        s = max(0, int(round(w.t_start * sample_rate)))
        e = min(audio.shape[0], int(round(w.t_end * sample_rate)))
        if e > s:
            pieces.append(audio[s:e])
    if not pieces:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(pieces)


# --- Public API --------------------------------------------------------------


def resolve_speakers(
    transcript: Transcript,
    audio: np.ndarray,
    sample_rate: int,
    *,
    candidate_person_ids: list[int] | None = None,
    threshold_high: float = THRESHOLD_HIGH,
    threshold_low: float = THRESHOLD_LOW,
    session_uuid: str = "session",
) -> dict[str, ResolvedSpeaker]:
    """Resolve raw speaker labels to known people. PRD §3.4."""
    if audio.dtype != np.int16:
        raise TypeError(f"resolve_speakers expects int16 audio, got {audio.dtype}")

    # Group words by raw speaker.
    by_speaker: dict[str, list[Word]] = {}
    for turn in transcript.turns:
        by_speaker.setdefault(turn.speaker_raw, []).extend(turn.words)

    if not by_speaker:
        return {}

    enrolled = load_enrolled_speakers(person_ids=candidate_person_ids)
    log.info(
        "resolve_speakers: %d raw speakers, %d enrolled candidates",
        len(by_speaker),
        len(enrolled),
    )

    out: dict[str, ResolvedSpeaker] = {}
    unknown_idx = 0
    short_session = session_uuid[:8] if session_uuid else "session"

    for speaker_raw, words in sorted(by_speaker.items()):
        speaker_pcm = _slice_speaker_audio(audio, sample_rate, words)
        # Need at least 0.5s of audio to embed reliably.
        if speaker_pcm.shape[0] < int(0.5 * sample_rate):
            label = f"unknown_{short_session}_{unknown_idx}"
            unknown_idx += 1
            out[speaker_raw] = ResolvedSpeaker(
                person_id=None,
                display_name=label,
                confidence=0.0,
                needs_review=True,
            )
            continue

        try:
            centroid = _embed_audio(speaker_pcm, sample_rate)
        except Exception:
            log.exception("embedding failed for speaker_raw=%s", speaker_raw)
            label = f"unknown_{short_session}_{unknown_idx}"
            unknown_idx += 1
            out[speaker_raw] = ResolvedSpeaker(
                person_id=None,
                display_name=label,
                confidence=0.0,
                needs_review=True,
            )
            continue

        best: tuple[float, EnrolledSpeaker] | None = None
        for cand in enrolled:
            score = _cosine(centroid, cand.embedding)
            if best is None or score > best[0]:
                best = (score, cand)

        if best is None or best[0] < threshold_low:
            label = f"unknown_{short_session}_{unknown_idx}"
            unknown_idx += 1
            out[speaker_raw] = ResolvedSpeaker(
                person_id=None,
                display_name=label,
                confidence=float(best[0]) if best else 0.0,
                needs_review=True,
            )
            continue

        score, cand = best
        out[speaker_raw] = ResolvedSpeaker(
            person_id=cand.person_id,
            display_name=cand.display_name,
            confidence=float(score),
            needs_review=score < threshold_high,
        )

    return out


def load_enrolled_speakers(*, person_ids: list[int] | None = None) -> list[EnrolledSpeaker]:
    """Read speaker_embeddings JOIN people from Postgres."""
    url = _db_url()
    sql = """
        SELECT e.person_id, p.display_name, e.embedding, p.is_self
          FROM speaker_embeddings e
          JOIN people p ON p.id = e.person_id
    """
    params: tuple[Any, ...] = ()
    if person_ids:
        sql += " WHERE p.id = ANY(%s)"
        params = (person_ids,)

    out: list[EnrolledSpeaker] = []
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        for person_id, display_name, embedding, is_self in cur.fetchall():
            arr = _pgvector_to_array(embedding)
            out.append(
                EnrolledSpeaker(
                    person_id=person_id,
                    display_name=display_name,
                    embedding=arr,
                    is_self=bool(is_self),
                )
            )
    return out


def _pgvector_to_array(embedding: Any) -> np.ndarray:
    """Convert a pgvector value (string or list) to a float32 ndarray."""
    if isinstance(embedding, str):
        # pgvector returns "[1.0,2.0,...]" by default.
        s = embedding.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        return np.fromstring(s, sep=",", dtype=np.float32)
    return np.asarray(embedding, dtype=np.float32).reshape(-1)


def _array_to_pgvector(arr: np.ndarray) -> str:
    """Format a float32 ndarray as a pgvector literal."""
    return "[" + ",".join(f"{float(x):.8f}" for x in arr.reshape(-1)) + "]"


def enroll_from_session(
    session_uuid: str,
    speaker_raw: str,
    person_name: str,
    *,
    person_email: str | None = None,
) -> int:
    """Add an embedding to ``speaker_embeddings`` for this person.

    Computes the centroid from the recording's audio restricted to the
    given raw speaker's turns. Creates a ``people`` row (or reuses the
    existing one matching email/display_name). Returns the new
    ``speaker_embeddings.id``.
    """
    import soundfile as sf  # noqa: PLC0415

    url = _db_url()
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, audio_path FROM recordings WHERE session_uuid = %s",
            (session_uuid,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"no recording found for session_uuid={session_uuid}")
        recording_id, audio_path = row

        cur.execute(
            """
            SELECT t_start, t_end
              FROM turns
             WHERE recording_id = %s AND speaker_raw = %s
             ORDER BY t_start
            """,
            (recording_id, speaker_raw),
        )
        turn_spans = cur.fetchall()
        if not turn_spans:
            raise ValueError(f"no turns for speaker_raw={speaker_raw!r} in session {session_uuid}")

        person_id = _upsert_person(cur, person_name, person_email, is_self=False)

        # Load audio and slice to this speaker's spans.
        audio, sample_rate = sf.read(audio_path, dtype="int16", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1).astype(np.int16)

        pieces: list[np.ndarray] = []
        for t_start, t_end in turn_spans:
            s = max(0, int(round(float(t_start) * sample_rate)))
            e = min(audio.shape[0], int(round(float(t_end) * sample_rate)))
            if e > s:
                pieces.append(audio[s:e])
        if not pieces:
            raise ValueError(f"all turn spans for {speaker_raw} in {session_uuid} were empty audio")
        speaker_pcm = np.concatenate(pieces)
        centroid = _embed_audio(speaker_pcm, sample_rate)

        cur.execute(
            """
            INSERT INTO speaker_embeddings (person_id, embedding, source_recording_id)
            VALUES (%s, %s::vector, %s)
            RETURNING id
            """,
            (person_id, _array_to_pgvector(centroid), recording_id),
        )
        new_id = cur.fetchone()[0]

    log.info(
        "enrolled person_id=%s display=%r from session=%s speaker=%s -> embedding_id=%s",
        person_id,
        person_name,
        session_uuid,
        speaker_raw,
        new_id,
    )
    return new_id


def enroll_self(reference_wav: Path, display_name: str = "me") -> int:
    """Pre-enroll the owner from a reference recording. PRD §8 q4.

    Idempotent: replaces any prior self embedding rather than duplicating.
    """
    import soundfile as sf  # noqa: PLC0415

    audio, sample_rate = sf.read(str(reference_wav), dtype="int16", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1).astype(np.int16)
    if audio.shape[0] < int(2.0 * sample_rate):
        raise ValueError(
            f"reference WAV is shorter than 2s ({audio.shape[0] / sample_rate:.1f}s); "
            "use ≥ 30s of clean speech for reliable enrollment."
        )

    centroid = _embed_audio(audio, sample_rate)
    url = _db_url()
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        person_id = _upsert_person(cur, display_name, None, is_self=True)

        # Replace any prior self embedding (idempotent self-enrollment).
        cur.execute("DELETE FROM speaker_embeddings WHERE person_id = %s", (person_id,))
        cur.execute(
            """
            INSERT INTO speaker_embeddings (person_id, embedding, source_recording_id)
            VALUES (%s, %s::vector, NULL)
            RETURNING id
            """,
            (person_id, _array_to_pgvector(centroid)),
        )
        new_id = cur.fetchone()[0]

    log.info(
        "self-enrolled as person_id=%s display=%r -> embedding_id=%s",
        person_id,
        display_name,
        new_id,
    )
    return new_id


def _upsert_person(
    cur: psycopg.Cursor,
    display_name: str,
    email: str | None,
    *,
    is_self: bool,
) -> int:
    """Find-or-create a ``people`` row. Returns the row id."""
    if is_self:
        cur.execute("SELECT id FROM people WHERE is_self = TRUE LIMIT 1")
        row = cur.fetchone()
        if row is not None:
            cur.execute(
                "UPDATE people SET display_name = %s, email = COALESCE(%s, email) WHERE id = %s",
                (display_name, email, row[0]),
            )
            return row[0]
    if email:
        cur.execute("SELECT id FROM people WHERE email = %s", (email,))
        row = cur.fetchone()
        if row is not None:
            return row[0]
    cur.execute("SELECT id FROM people WHERE display_name = %s LIMIT 1", (display_name,))
    row = cur.fetchone()
    if row is not None and not is_self:
        # Reuse a non-self row matching by display_name. is_self rows are
        # handled above to avoid promoting a non-self row by accident.
        return row[0]

    cur.execute(
        "INSERT INTO people (display_name, email, is_self) VALUES (%s, %s, %s) RETURNING id",
        (display_name, email, is_self),
    )
    return cur.fetchone()[0]
