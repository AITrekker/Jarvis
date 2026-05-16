"""WhisperX wrapper. PRD §3.3.

Phase 1: single-speaker mode. Every word gets speaker_raw="SPEAKER_00".
Phase 2: optional diarization via pyannote, overlaid onto faster-whisper's
word-level transcription. When the caller passes a diarizer (or sets
``diarize=True``), speaker_raw values come from pyannote's labels
("SPEAKER_00", "SPEAKER_01", ...) and turns split on speaker change.

Implementation note: Phase 1 used faster-whisper directly (no alignment, no
diarization). Phase 2 keeps faster-whisper for transcription (it's faster on
CPU than whisperx's wav2vec2 alignment for our use case) and runs pyannote
separately, mapping words to speakers by timestamp overlap. This keeps the
diarization provider swappable behind the ``DiarizationProvider`` protocol.

Models load lazily and LRU-cache (size 1) under a lock — production loads
``large-v3`` once and the diarizer is loaded once and reused. Use
``tiny.en`` in tests; ``large-v3`` in production (config-driven).
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from .types import AudioSegment, Transcript, Turn, Word

if TYPE_CHECKING:  # pragma: no cover - import-time only for type checkers
    from faster_whisper import WhisperModel

DEFAULT_TEST_MODEL = "tiny.en"
SPEAKER_RAW_PHASE1 = "SPEAKER_00"

# int16 PCM -> float32 in [-1, 1] for whisper.
_INT16_MAX = 32768.0

log = logging.getLogger(__name__)

# Module-level cache, keyed by (model_name, device, compute_type). LRU-capped
# to 1 entry — Phase 2 loads whisper alongside pyannote, and keeping two
# whisper variants resident isn't worth the RAM. Lock prevents races on miss.
_MODEL_CACHE_MAX = 1
_MODEL_CACHE: OrderedDict[tuple[str, str, str], WhisperModel] = OrderedDict()
_MODEL_CACHE_LOCK = threading.Lock()

# Single-slot diarizer cache. The pyannote pipeline is multi-GB; loading it
# once and keeping it pinned is the only reasonable choice on a laptop.
_DIARIZER_CACHE: dict[str, PyannoteDiarizer] = {}
_DIARIZER_LOCK = threading.Lock()


# --- Diarization provider protocol -------------------------------------------


class SpeakerSegment:
    """One per-speaker time region produced by diarization."""

    __slots__ = ("speaker_raw", "t_start", "t_end")

    def __init__(self, speaker_raw: str, t_start: float, t_end: float) -> None:
        self.speaker_raw = speaker_raw
        self.t_start = t_start
        self.t_end = t_end


class DiarizationProvider(Protocol):
    """Anything that turns a WAV into per-speaker time spans."""

    def diarize(
        self,
        audio_path: Path,
        *,
        num_speakers: int | None = None,
    ) -> list[SpeakerSegment]: ...


class PyannoteDiarizer:
    """Real pyannote-based diarizer. Lazy-loads weights on first call."""

    def __init__(self, model_name: str = "pyannote/speaker-diarization-3.1") -> None:
        self._model_name = model_name
        self._pipeline: Any | None = None

    def _load_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        from pyannote.audio import Pipeline  # noqa: PLC0415

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HF_TOKEN is not set; pyannote needs a Hugging Face token to load "
                "the gated speaker-diarization-3.1 weights. See PRD §8."
            )
        log.info("loading pyannote diarization pipeline %s", self._model_name)
        self._pipeline = Pipeline.from_pretrained(self._model_name, token=token)
        return self._pipeline

    def diarize(
        self,
        audio_path: Path,
        *,
        num_speakers: int | None = None,
    ) -> list[SpeakerSegment]:
        pipeline = self._load_pipeline()
        kwargs: dict[str, Any] = {}
        if num_speakers is not None and num_speakers > 0:
            kwargs["min_speakers"] = num_speakers
            kwargs["max_speakers"] = num_speakers
        annotation = pipeline(str(audio_path), **kwargs)

        segments: list[SpeakerSegment] = []
        # pyannote's Annotation has .itertracks(yield_label=True) -> (segment, _, label)
        for turn, _track, label in annotation.itertracks(yield_label=True):
            segments.append(
                SpeakerSegment(
                    speaker_raw=str(label),
                    t_start=float(turn.start),
                    t_end=float(turn.end),
                )
            )
        # Sort so word-overlap lookup is monotonic-friendly.
        segments.sort(key=lambda s: s.t_start)
        return segments


def get_diarizer(model_name: str = "pyannote/speaker-diarization-3.1") -> PyannoteDiarizer:
    """Return a process-wide cached PyannoteDiarizer."""
    with _DIARIZER_LOCK:
        cached = _DIARIZER_CACHE.get(model_name)
        if cached is not None:
            return cached
        diarizer = PyannoteDiarizer(model_name=model_name)
        _DIARIZER_CACHE[model_name] = diarizer
        return diarizer


# --- Whisper helpers (Phase 1, unchanged signatures) -------------------------


def _resolve_default_model() -> str:
    try:
        from . import config as _config  # local import on purpose

        cfg = _config.load()
        return cfg.whisper.model
    except Exception:  # noqa: BLE001 - any config error → fall back
        log.debug("transcriber: config.load() failed, using DEFAULT_TEST_MODEL", exc_info=True)
        return DEFAULT_TEST_MODEL


def _resolve_device_and_compute_type() -> tuple[str, str]:
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

    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            _MODEL_CACHE.move_to_end(key)
            return cached

        from faster_whisper import WhisperModel  # noqa: PLC0415

        log.info(
            "loading whisper model %s (device=%s, compute_type=%s)",
            model_name,
            device,
            compute_type,
        )
        try:
            model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                local_files_only=True,
            )
        except Exception:
            log.warning("whisper model %s not in local cache; allowing download", model_name)
            model = WhisperModel(model_name, device=device, compute_type=compute_type)

        _MODEL_CACHE[key] = model
        while len(_MODEL_CACHE) > _MODEL_CACHE_MAX:
            _MODEL_CACHE.popitem(last=False)
        return model


def _segment_to_float32(seg: AudioSegment) -> np.ndarray:
    pcm = seg.pcm
    if pcm.dtype == np.float32:
        return pcm
    return pcm.astype(np.float32) / _INT16_MAX


def _word_confidence(w: Any) -> float:
    for attr in ("probability", "confidence"):
        val = getattr(w, attr, None)
        if val is not None:
            return float(val)
    return 1.0


def _word_text(w: Any) -> str:
    text = getattr(w, "word", None)
    if text is None:
        text = getattr(w, "text", "")
    return str(text)


# --- Speaker assignment ------------------------------------------------------


def _label_for_word(
    word_t_start: float,
    word_t_end: float,
    speakers: list[SpeakerSegment],
) -> str:
    """Pick the speaker label whose region overlaps this word the most.

    Falls back to SPEAKER_RAW_PHASE1 when no speaker region overlaps.
    """
    best_overlap = 0.0
    best_label = SPEAKER_RAW_PHASE1
    for s in speakers:
        if s.t_end < word_t_start:
            continue
        if s.t_start > word_t_end:
            break  # sorted by t_start
        overlap = min(s.t_end, word_t_end) - max(s.t_start, word_t_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = s.speaker_raw
    return best_label


def _split_turn_on_speaker_change(
    seg_t_start: float,
    seg_t_end: float,
    words: list[Word],
) -> list[Turn]:
    """Group consecutive same-speaker words into Turns.

    Empty word lists yield a single Turn with the segment's speaker
    inherited from SPEAKER_RAW_PHASE1.
    """
    if not words:
        return []
    turns: list[Turn] = []
    cur_speaker = words[0].speaker_raw
    cur_words: list[Word] = []
    cur_t_start = words[0].t_start

    def _flush(end_time: float) -> None:
        if not cur_words:
            return
        text = " ".join(w.text for w in cur_words).strip()
        turns.append(
            Turn(
                speaker_raw=cur_speaker,
                t_start=cur_t_start,
                t_end=end_time,
                text=text,
                words=list(cur_words),
            )
        )

    for w in words:
        if w.speaker_raw != cur_speaker:
            _flush(cur_words[-1].t_end if cur_words else cur_t_start)
            cur_speaker = w.speaker_raw
            cur_t_start = w.t_start
            cur_words = [w]
        else:
            cur_words.append(w)
    _flush(cur_words[-1].t_end if cur_words else seg_t_end)
    # Clamp the first turn's t_start and last turn's t_end to the segment so
    # the overall timeline stays consistent with the segmenter's boundaries.
    if turns:
        turns[0] = Turn(
            speaker_raw=turns[0].speaker_raw,
            t_start=min(turns[0].t_start, seg_t_start),
            t_end=turns[0].t_end,
            text=turns[0].text,
            words=turns[0].words,
        )
        last = turns[-1]
        turns[-1] = Turn(
            speaker_raw=last.speaker_raw,
            t_start=last.t_start,
            t_end=max(last.t_end, seg_t_end),
            text=last.text,
            words=last.words,
        )
    return turns


# --- Public API --------------------------------------------------------------


def transcribe(
    segments: Iterable[AudioSegment],
    num_speakers_hint: int | None = None,
    *,
    model: str | None = None,
    diarizer: DiarizationProvider | None = None,
    audio_path: Path | None = None,
) -> Transcript:
    """Run Whisper on the given segments and return a Transcript.

    Phase 1 contract (still valid when diarizer is None):
    - Single-speaker mode: every Word + Turn carries speaker_raw="SPEAKER_00".
    - num_speakers_hint is accepted but ignored.
    - One Turn per input AudioSegment. Empty whisper output is skipped.
    - Word timestamps offset by ``seg.t_start``.

    Phase 2 contract (diarizer != None):
    - The diarizer runs against ``audio_path`` (the full session WAV) and
      returns per-speaker time spans.
    - Each word's speaker_raw is the diarizer's label whose region overlaps
      the word the most. Words with no overlap inherit SPEAKER_RAW_PHASE1
      (rare; means whisper found a word in a region pyannote considered
      silent — usually a low-confidence whisper artifact).
    - Turns split on speaker change within a segment.
    - num_speakers_hint propagates into the diarizer (calendar attendee
      count is the source).
    - audio_path is required when diarizer is given (pyannote needs the WAV
      to build embeddings).
    """
    model_name = model or _resolve_default_model()
    whisper = _load_model(model_name)

    # Diarize once over the whole session (PRD §3.3 — speaker labels must be
    # consistent across the recording, not per-segment).
    speaker_spans: list[SpeakerSegment] = []
    if diarizer is not None:
        if audio_path is None:
            raise ValueError("transcribe(diarizer=...) requires audio_path")
        speaker_spans = diarizer.diarize(audio_path, num_speakers=num_speakers_hint)
        log.info(
            "diarization produced %d speaker spans across %d unique speakers",
            len(speaker_spans),
            len({s.speaker_raw for s in speaker_spans}),
        )

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
                w_t_start = float(w.start) + seg.t_start
                w_t_end = float(w.end) + seg.t_start
                if speaker_spans:
                    speaker_raw = _label_for_word(w_t_start, w_t_end, speaker_spans)
                else:
                    speaker_raw = SPEAKER_RAW_PHASE1
                words.append(
                    Word(
                        text=wt,
                        t_start=w_t_start,
                        t_end=w_t_end,
                        speaker_raw=speaker_raw,
                        confidence=_word_confidence(w),
                    )
                )

        joined = " ".join(text_parts).strip()
        if not joined and not words:
            continue

        if speaker_spans and words:
            turns.extend(_split_turn_on_speaker_change(seg.t_start, seg.t_end, words))
        else:
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
