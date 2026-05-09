.PHONY: help setup sync lint fmt test test.unit test.integration smoke db.up db.down db.psql migrate

# This Makefile is a thin convenience shim for Mac/Linux. On Windows, run nox
# directly: `uv run nox -s lint`, etc. See noxfile.py for the canonical task list.

help:
	@echo "Targets (Mac/Linux convenience; Windows: 'uv run nox -s <task>'):"
	@echo "  setup           - install uv-managed venv with dev + audio extras"
	@echo "  sync            - re-sync deps from pyproject.toml"
	@echo "  lint            - ruff check + format check"
	@echo "  fmt             - ruff fix + format"
	@echo "  test.unit       - unit tests only (no Docker)"
	@echo "  test.integration- integration tests (requires Docker)"
	@echo "  test            - unit + integration"
	@echo "  smoke           - CLI smoke check"
	@echo "  db.up           - start local Postgres + pgvector via docker compose"
	@echo "  db.down         - stop local Postgres"
	@echo "  db.psql         - open psql against local Postgres"
	@echo "  migrate         - apply migrations/0001_init.sql"

setup:
	uv sync --extra dev --extra audio

sync:
	uv sync

lint:
	uv run nox -s lint

fmt:
	uv run nox -s fmt

test:
	uv run nox -s test

test.unit:
	uv run nox -s test_unit

test.integration:
	uv run nox -s test_integration

smoke:
	uv run nox -s smoke

db.up:
	docker compose up -d db

db.down:
	docker compose down

db.psql:
	docker compose exec db psql -U jarvis -d jarvis

migrate:
	@test -n "$$JARVIS_DB_URL" || (echo "set JARVIS_DB_URL first" && exit 1)
	uv run psql "$$JARVIS_DB_URL" -f migrations/0001_init.sql
