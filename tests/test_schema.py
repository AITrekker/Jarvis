"""Phase 0 integration gate: the migration applies and the schema is queryable."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_schema_applies_and_extensions_present(postgres_url: str) -> None:
    import psycopg

    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension")
        exts = {row[0] for row in cur.fetchall()}
        assert {"vector", "pg_trgm"}.issubset(exts)

        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
        expected = {
            "people",
            "speaker_embeddings",
            "events",
            "event_attendees",
            "recordings",
            "turns",
            "chunks",
        }
        assert expected.issubset(tables)
