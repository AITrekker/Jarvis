.PHONY: help setup sync lint test test.unit test.integration db.up db.down db.psql migrate migrate.new

help:
	@echo "Targets:"
	@echo "  setup           - install uv-managed venv with dev + audio extras"
	@echo "  sync            - re-sync deps from pyproject.toml"
	@echo "  lint            - ruff check + format check"
	@echo "  test            - pytest (unit + integration)"
	@echo "  test.unit       - unit tests only"
	@echo "  test.integration- integration tests (requires docker)"
	@echo "  db.up           - start local Postgres + pgvector via docker compose"
	@echo "  db.down         - stop local Postgres"
	@echo "  db.psql         - open psql against local Postgres"
	@echo "  migrate         - run alembic upgrade head"
	@echo "  migrate.new name=<desc> - create a new migration"

setup:
	uv sync --extra dev --extra audio

sync:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

test: test.unit test.integration

test.unit:
	uv run pytest -m "not integration and not ml"

test.integration:
	uv run pytest -m integration

db.up:
	docker compose up -d db

db.down:
	docker compose down

db.psql:
	docker compose exec db psql -U jarvis -d jarvis

migrate:
	uv run alembic upgrade head

migrate.new:
	@test -n "$(name)" || (echo "usage: make migrate.new name=<description>" && exit 1)
	uv run alembic revision -m "$(name)"
