"""Cross-module dataclasses. Modules depend on these, not on each other.

Locked 2026-05-11 as the Phase 1 interface contract; extended 2026-05-15
for Phase 2 (EnrolledSpeaker, EventAttendee). Sub-agents must not rename
or repurpose fields without updating this file *and* PRD §3 in the same
PR. Adding optional fields is fine; renaming is a breaking change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class AudioChunk:
    """Fixed-frame PCM block emitted by an AudioSource. PRD §3.1."""

    pcm: np.ndarray  # int16, shape (n_samples,), mono, 16 kHz
    t_start: float  # seconds since session start
    t_end: float


@dataclass
class AudioSegment:
    """Voiced region produced by the segmenter. PRD §3.2."""

    pcm: np.ndarray  # int16, shape (n_samples,), mono, 16 kHz
    t_start: float
    t_end: float


@dataclass
class Word:
    text: str
    t_start: float
    t_end: float
    speaker_raw: str
    confidence: float


@dataclass
class Turn:
    speaker_raw: str
    t_start: float
    t_end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    turns: list[Turn]
    language: str


@dataclass
class ResolvedSpeaker:
    person_id: int | None
    display_name: str
    confidence: float
    needs_review: bool


@dataclass
class CalendarEvent:
    id: int
    google_event_id: str
    title: str
    started_at: datetime
    ended_at: datetime
    description: str | None
    attendee_person_ids: list[int]


@dataclass
class EventAttendee:
    """One row of the `event_attendees` table. PRD §3.5, §4.

    `person_id` is None when calendar_sync sees an attendee email it cannot
    resolve to a known `people` row yet. Phase 2 calendar_sync upserts the
    raw email so the speaker_resolver can later associate it with a person.
    """

    event_id: int
    person_id: int | None
    email: str
    display_name: str | None
    response_status: str | None  # "accepted" | "declined" | "tentative" | "needsAction"


@dataclass
class EnrolledSpeaker:
    """One row of `speaker_embeddings` joined to `people`. PRD §3.4.

    The speaker_resolver loads these as candidates when scoring a session's
    raw speakers against known voices. `embedding` is the 192-dim ECAPA-TDNN
    centroid pyannote produces.
    """

    person_id: int
    display_name: str
    embedding: np.ndarray  # float32, shape (192,)
    is_self: bool


@dataclass
class SessionMeta:
    session_uuid: str
    source_label: str
    started_at: datetime
    ended_at: datetime


@dataclass
class Summary:
    abstract: str
    action_items: list[str]
    topics: list[str]


@dataclass
class StructuredQuery:
    speaker: str | None
    attendees: list[str]
    date_from: datetime | None
    date_to: datetime | None
    semantic_query: str


@dataclass
class SearchHit:
    recording_id: int
    turn_id: int | None
    chunk_id: int | None
    score: float
    speaker: str
    text: str
    t_start: float
    event_title: str | None
    started_at: datetime


@dataclass
class Citation:
    source: str  # "turn", "chunk", "recording", "slack", "gmail", ...
    id: str


@dataclass
class ToolResult:
    ok: bool
    data: object
    error: str | None = None
    citations: list[Citation] = field(default_factory=list)
