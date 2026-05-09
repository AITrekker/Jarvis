"""Cross-module dataclasses. Modules depend on these, not on each other."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class AudioChunk:
    pcm: np.ndarray
    t_start: float
    t_end: float


@dataclass
class AudioSegment:
    pcm: np.ndarray
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
