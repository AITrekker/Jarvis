"""Shared pytest fixtures.

`postgres_url` boots a pgvector-enabled Postgres in a container and applies
all migration files in `migrations/` in lexical order. Tests that need a DB
request this fixture and get a clean schema per session.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


@pytest.fixture(scope="session")
def postgres_url() -> str:
    pytest.importorskip("testcontainers.postgres")
    pytest.importorskip("psycopg")

    import psycopg  # type: ignore[import-not-found]
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-not-found]

    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            for sql_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cur.execute(sql_path.read_text())
        os.environ["JARVIS_DB_URL"] = url
        yield url
