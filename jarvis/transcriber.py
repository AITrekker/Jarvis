"""WhisperX wrapper. PRD §3.3.

Phase 1: single-speaker mode. Every word gets speaker_raw="SPEAKER_00".
Diarization (real speaker labels) lands in Phase 2.

Implementation note: we use ``faster-whisper`` directly. The ``whisperx``
package wraps faster-whisper and adds alignment + diarization, but Phase 1
needs neither — just word-timestamped transcription with a single speaker
label. Going through whisperx would add startup cost (extra alignment model
load) for no benefit at this stage. Phase 2 will likely switch the
implementation to use whisperx + pyannote when diarization comes online.

Models load lazily and cache. Use ``tiny.en`` in tests; ``large-v3`` in
production (config-driven).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import numpy as np

from .types import AudioSegment, Transcript, Turn, Word

if TYPE_CHECKING:  # pragma: no cover - import-time only for type checkers
    from faster_whisper import WhisperModel

DEFAULT_TEST_MODEL = "tiny.en"
SPEAKER_RAW_PHASE1 = "SPEAKER_00"

# int16 PCM -> float32 in [-1, 1] for whisper.
_INT16_MAX = 32768.0

log = logging.getLogger(__name__)

# Module-level cache, keyed by (model_name, device, compute_type). Loading
# even ``tiny.en`` takes ~2s on a cold start; production ``large-v3`` is
# multi-GB. Reusing the cached model across calls is essential for the
# Phase 1 pipeline where each AudioSegment turns into one transcribe() call.
_MODEL_CACHE: dict[tuple[str, str, str], WhisperModel] = {}


def _resolve_default_model() -> str:
    """Return the configured Whisper model name, falling back to the test default.

    We import ``jarvis.config`` lazily so the unit tests can mock everything
    out without requiring config.toml or a populated environment.
    """
    try:
        from . import config as _config  # local import on purpose

        cfg = _config.load()
        return cfg.whisper.model
    except Exception:  # noqa: BLE001 - any config error → fall back
        log.debug("transcriber: config.load() failed, using DEFAULT_TEST_MODEL", exc_info=True)
        return DEFAULT_TEST_MODEL


def _resolve_device_and_compute_type() -> tuple[str, str]:
    """Pick a device + compute_type for faster-whisper.

    faster-whisper does not natively support Apple's MPS backend (it uses
    CTranslate2, which has CPU + CUDA). When config says ``device = "mps"``
    we silently fall back to CPU with int8 — Phase 1 just needs correctness,
    not throughput. Phase 2 can revisit if perf becomes a problem.
    """
    try:
        from . import config as _config

        cfg = _config.load()
        device = cfg.whisper.device
        compute_type = cfg.whisper.compute_type
    except Exception:  # noqa: BLE001
        return ("cpu", "int8")

    if device == "mps":
        return ("cpu", "int8")
    if device == "cuda":
        return (device, compute_type)
    return ("cpu", compute_type if compute_type in {"int8", "float32"} else "int8")


def _load_model(model_name: str) -> WhisperModel:
    device, compute_type = _resolve_device_and_compute_type()
    key = (model_name, device, compute_type)
    cached = _MODEL_CACHE.get(key)
    if cached is not None:
        return cached

    # Imported lazily so importing this module is cheap (matters for the CLI
    # cold-start path; faster-whisper pulls in ctranslate2 + tokenizers).
    from faster_whisper import WhisperModel  # noqa: PLC0415

    log.info(
        "loading whisper model %s (device=%s, compute_type=%s)", model_name, device, compute_type
    )
    try:
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            local_files_only=True,
        )
    except Exception:
        # Cache miss: fall back to allowing a download. The slow ml test
        # explicitly relies on a pre-populated HF cache, so this branch only
        # fires in real usage where a download is acceptable.
        log.warning("whisper model %s not in local cache; allowing download", model_name)
        model = WhisperModel(model_name, device=device, compute_type=compute_type)

    _MODEL_CACHE[key] = model
    return model


def _segment_to_float32(seg: AudioSegment) -> np.ndarray:
    """Convert int16 PCM to float32 in [-1, 1] as whisper expects."""
    pcm = seg.pcm
    if pcm.dtype == np.float32:
        return pcm
    return pcm.astype(np.float32) / _INT16_MAX


def _word_confidence(w: Any) -> float:
    """Pull a confidence out of a faster-whisper word object, defaulting to 1.0.

    faster-whisper exposes ``probability`` on its Word namedtuple. Some mock
    objects in tests may set ``confidence`` instead; we accept either.
    """
    for attr in ("probability", "confidence"):
        val = getattr(w, attr, None)
        if val is not None:
            return float(val)
    return 1.0


def _word_text(w: Any) -> str:
    """faster-whisper's Word uses ``.word`` for the token; some libs use ``.text``."""
    text = getattr(w, "word", None)
    if text is None:
        text = getattr(w, "text", "")
    return str(text)


def transcribe(
    segments: Iterable[AudioSegment],
    num_speakers_hint: int | None = None,
    *,
    model: str | None = None,
) -> Transcript:
    """Run Whisper on the given segments and return a Transcript.

    Phase 1 contract:
    - Single-speaker mode: every Word + Turn carries speaker_raw="SPEAKER_00".
    - num_speakers_hint is accepted in the signature but ignored (Phase 2 wires
      it into pyannote diarization).
    - One Turn per input AudioSegment. Segments where Whisper returns no text
      (e.g. our synthetic tone fixture) are skipped.
    - Word timestamps are populated, offset by ``seg.t_start`` so they live in
      the same session timeline as the input segments.
    """
    del num_speakers_hint  # Phase 2

    model_name = model or _resolve_default_model()
    whisper = _load_model(model_name)

    turns: list[Turn] = []
    for seg in segments:
        audio = _segment_to_float32(seg)
        whisper_segments, _info = whisper.transcribe(
            audio,
            word_timestamps=True,
            language="en",
            vad_filter=False,
        )

        words: list[Word] = []
        text_parts: list[str] = []
        for ws in whisper_segments:
            seg_text = (ws.text or "").strip()
            if seg_text:
                text_parts.append(seg_text)
            for w in ws.words or []:
                wt = _word_text(w).strip()
                if not wt:
                    continue
                words.append(
                    Word(
                        text=wt,
                        t_start=float(w.start) + seg.t_start,
                        t_end=float(w.end) + seg.t_start,
                        speaker_raw=SPEAKER_RAW_PHASE1,
                        confidence=_word_confidence(w),
                    )
                )

        joined = " ".join(text_parts).strip()
        if not joined and not words:
            # Whisper produced nothing for this segment — skip it rather than
            # emit an empty Turn that the persister would have to special-case.
            continue

        turns.append(
            Turn(
                speaker_raw=SPEAKER_RAW_PHASE1,
                t_start=seg.t_start,
                t_end=seg.t_end,
                text=joined,
                words=words,
            )
        )

    return Transcript(turns=turns, language="en")
