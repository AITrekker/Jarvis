# Jarvis — context for Claude Code

This file is auto-loaded by Claude Code when it starts in this repo. It exists so any future session — on this machine, on Windows, on a fresh clone — picks up the load-bearing context without re-deriving it.

**The source of truth for the design is [`PRD.md`](./PRD.md). Read it first.** This file is the meta-context: how to work in the repo, decisions that aren't obvious from the code, and what's been tried.

## Project shape

- Personal tool: local meeting recorder + searchable memory. Runs entirely on the owner's laptop. No cloud LLMs. No cloud storage.
- Owner: Amit Gupta. Single-user, not a multi-tenant product.
- This is a **rebuild**. The previous version is preserved at tag `v1-2025` and branch `archive/2025`. Rollback: `git checkout v1-2025`.
- v1 failed in four specific ways (see PRD §1). Those four failure modes are hard constraints on the rebuild — do not undo them when shortcuts present themselves.

## Architecture in one paragraph

Single Python process. Audio source → VAD segmenter → WhisperX (transcribe + diarize) → speaker resolver (voice embeddings) → calendar enrichment → persister (Postgres + pgvector, single transaction) → fire-and-forget summarizer. Search is hybrid (FTS + vector + structured filters with RRF fusion). A primary agent sits in front of a tool registry; the agent is consumed via three surfaces — CLI, MCP server (for Claude Desktop / Cursor / ChatGPT Desktop), and a tray app for recording control. **No bespoke chat UI is built; the chat surface is the LLM host.**

## Hard rules

These are not preferences. Each maps to a v1 failure or to a 2026 architectural reality:

1. **Single store: Postgres + pgvector.** No separate vector DB, no SQLite-plus-Chroma. Embeddings live in pgvector columns on the same rows written in the same transaction.
2. **Recording pipeline stays deterministic.** No LLM in the capture path. Latency, cost, non-determinism, and no benefit.
3. **One primary agent in v1.** No multi-agent orchestration. Sub-agents only for bounded heavy reasoning (summarization, citation drafting from many hits).
4. **Three surfaces, one backend.** CLI, MCP server, tray are *adapters*. Business logic lives in the modules and the tools registry. A surface adds zero behavior the CLI doesn't already have.
5. **Cross-platform: Mac and Windows are both first-class.** Use `pathlib`, `sys.platform` branches, `_paths` helpers. Never write XDG paths as literals. CI runs on `ubuntu-latest`, `macos-latest`, `windows-latest`.
6. **Local LLM via Ollama by default**, but the `LLMClient` speaks OpenAI-compatible HTTP so any runtime (LM Studio, llama.cpp, vLLM) is a config swap.

## Repository conventions

- **Package code:** `jarvis/` (top-level), with private helpers prefixed `_` (e.g. `_paths.py`, `_proc.py`). Modules match PRD §3 names exactly.
- **Tests:** `tests/`, integration tests marked `@pytest.mark.integration`, ML tests `@pytest.mark.ml` (skipped in default CI). Fixtures: `tests/fixtures/`, with a README for what's deferred.
- **Migrations:** raw SQL in `migrations/0001_init.sql` for now; alembic wiring lands in Phase 1+.
- **Tooling:** `uv` for envs, `nox` for tasks (works on Windows where `make` doesn't), `ruff` for lint+format, `pytest` for tests.
- **Frozen v1 reference:** `docs/v1-reference/` keeps the old setup/start scripts. Never imported. Read its README before re-deriving cross-platform patterns.

## Working in this repo

- `uv sync --extra dev` to set up; `uv run jarvis <cmd>` or `source .venv/bin/activate` to run.
- Tasks: `uv run nox -s lint` / `test_unit` / `test_integration` / `smoke`. The Makefile is a convenience shim that calls nox; do not duplicate logic in both.
- Do not commit recordings, audio, the local DB, or `.env`. The `.gitignore` is broad on purpose.
- Surface changes (CLI, MCP, tray) live in the surface module. Do not put business logic in `cli.py`, `mcp_server.py`, or `tray.py`.
- When stubbing a future module, raise `NotImplementedError` with a message naming the phase that builds it. Silent `pass` or `return None` will rot.

## Build phases — see PRD §7

We are in Phase 0 → starting Phase 1. Do not start Phase N+1 until Phase N's gate is met.

## Decisions made in conversation that aren't in the PRD

If you're a future Claude session and one of these contradicts the PRD, the PRD wins — but flag the contradiction so the human can resolve it.

- **CLI binary is `jarvis`, not `recorder`** (PRD originally said `recorder`; renamed for consistency with the repo and brand).
- **Python 3.12 is the dev/CI baseline.** `>=3.11,<3.13` in `pyproject.toml`.
- **Postgres install path is user-choice:** Docker (cross-platform), Postgres.app (Mac), EDB installer (Windows), brew (Mac). README documents all of them; nothing in code assumes a specific path.
- **Tray uses `pystray`** specifically because it works on Mac, Windows, and Linux from one codebase. `rumps` is rejected (Mac-only).
- **MCP server is stdio-only in v1.** Remote MCP / HTTP transport is out of scope; Jarvis is a local tool, tunneling its mic and DB to a public endpoint defeats the design.
- **Memory of past conversations:** Claude Code's `~/.claude/.../memory/` cache is local to one machine. Durable memory lives here in `CLAUDE.md`, in `PRD.md`, and in commit messages. Do not rely on the local cache for anything load-bearing.

## Things that have already been tried and rejected

- **Gradio web UI** (v1) — rebuilding it would lose to Claude Desktop / Cursor / ChatGPT Desktop. Out of scope.
- **ChromaDB + SQLite dual-store** (v1) — caused consistency bugs. Hard rule: single store.
- **Chat-summary-only search** (v1) — turn-level queries failed. Hard rule: multi-granularity (turn / chunk / meeting).
- **`make` as the task runner** (Phase 0 first pass) — replaced by `nox` because `make` isn't on Windows by default. Makefile remains as a Mac/Linux convenience shim only.

## When in doubt

1. Re-read the relevant section of `PRD.md`.
2. Look at the most recent ~10 commits — every meaningful decision has a commit message that explains the *why*.
3. Ask the human before changing an interface in PRD §3 or a "hard rule" above.
