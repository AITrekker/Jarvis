"""Hybrid query API. PRD §3.8."""

from __future__ import annotations

from .types import SearchHit


def search(query: str, k: int = 20) -> list[SearchHit]:
    raise NotImplementedError("search: implemented in Phase 3")
