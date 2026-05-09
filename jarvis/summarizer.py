"""Best-effort meeting summary via Ollama. PRD §3.7."""

from __future__ import annotations

from .types import Summary


def summarize(recording_id: int) -> Summary:
    raise NotImplementedError("summarize: implemented in Phase 3")
