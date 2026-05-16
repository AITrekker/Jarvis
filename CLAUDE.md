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

**Current state: Phase 2 complete on `main` (tag `phase2`, as of 2026-05-15). Ready to start Phase 3.**

What's done:
- **Phase 0** (`./bootstrap.sh`): Python 3.12, uv, ffmpeg, psql, Postgres.app with pgvector+pg_trgm, Ollama daemon with `qwen2.5`. 21 unit tests.
- **Phase 1** (tag `phase1`): WAV → `turns` rows in Postgres. `audio_source`, `segmenter`, `transcriber` (faster-whisper, single-speaker), `persister` (recordings + turns), `recorder`, `tray`, `cli`.
- **Phase 2** (tag `phase2`): Real diarization (pyannote 3.1 + 3.4-DiarizeOutput compatibility), `speaker_resolver` (512-dim X-vector centroid + cosine + threshold gating), `enroll`/`enroll-self`/`people` CLI, `calendar_sync` (gcsa-based, OAuth in keyring), recorder integrates all three best-effort, persister writes `event_id` + `person_id` + `speaker_confidence` + `needs_review`. Verified end-to-end against pyannote's tutorial WAV — 2 speakers correctly diarized, the enrolled speaker resolved at conf 0.752.
- 109 tests green (91 unit + 17 integration + 1 ml). Lint clean.

`HF_TOKEN` is in `.env` (gitignored). Pyannote weights are cached at `~/.cache/huggingface/`.

Do not start Phase N+1 until Phase N's gate is met.

### Next: Phase 3 (per PRD §7) — search & summarization

One agent scope:
- **`jarvis/summarizer.py`** — fire-and-forget Ollama summarization producing `Summary(abstract, action_items, topics)`. Stored on the `recordings` row (`summary_abstract`, `summary_action_items`, `summary_topics`, `summary_embedding`). Failure must not block the persister's commit.
- **`jarvis/search.py`** — hybrid query (FTS over turn text + pgvector cosine over chunk embeddings + structured filters), RRF fusion. Direct CLI surface (`jarvis search "<query>"`); no LLM planner yet (that's Phase 5).
- **`chunks` writes** — Phase 1/2 deliberately deferred chunk + embedding rows. Phase 3 adds them in the persister (still single transaction). PRD §8 q1 (embedding model + dim) needs to be locked **before** writing.

**Gate:** *"what did I say to <name> last week"* on seeded data returns correct results via direct hybrid search.

**Phase 3 prerequisites the owner must lock before agents run:**
1. **Embedding model + dim.** Schema fixes `chunks.embedding VECTOR(768)`. Pick from PRD §8 q1: `bge-small-en` (384, doesn't fit), `nomic-embed-text` (768, fits), `all-mpnet-base-v2` (768, fits). Recommendation: `nomic-embed-text` via Ollama (already a runtime dep, no extra surface).
2. **Query-parser failure mode** (PRD §8 q2): when Ollama is down, does `search` fall back to pure semantic or fail loudly? Default proposal: fall back, log warning.
3. **Audio retention** (PRD §8 q3): keep WAVs forever or delete after N days? Default: keep.

### Phase 1/2 carry-forwards still open (low priority)

None block Phase 3. Worth doing as Phase 3 housekeeping or a Phase 2.5 cleanup pass:
- Diarizer fallback silently downgrades; surface a `RecorderResult.diarization_skipped` flag (Phase 6 polish).
- enroll_self requires ≥ 2s but PRD recommends 30s; add a quality warning between 2 and 30s.
- gcsa client kwarg `save_token=False` is gcsa-version specific; wrap in try/except TypeError.
- Pyannote `use_auth_token` vs `token` kwarg drift; if both surfaces ever disappear, switch to `huggingface_hub.login(...)` once at startup.

The cross-platform helpers Phase 1 will build on are already in place: `jarvis/_proc.py` (pidfile + ManagedProcess + cross-platform stop), `jarvis/_progress.py` (TTY-aware spinner for slow Whisper imports), `jarvis/_paths.py` (per-OS data/config/runtime dirs), `jarvis/_logging.py` (handler reset + Windows UTF-8 + httpx silenced).

## Decisions made in conversation that aren't in the PRD

If you're a future Claude session and one of these contradicts the PRD, the PRD wins — but flag the contradiction so the human can resolve it.

- **CLI binary is `jarvis`, not `recorder`** (PRD originally said `recorder`; renamed for consistency with the repo and brand).
- **Python 3.12 is the dev/CI baseline.** `>=3.11,<3.13` in `pyproject.toml`.
- **Postgres install path is user-choice:** Docker (cross-platform), Postgres.app (Mac), EDB installer (Windows), brew (Mac). README documents all of them; nothing in code assumes a specific path.
- **Tray uses `pystray`** specifically because it works on Mac, Windows, and Linux from one codebase. `rumps` is rejected (Mac-only).
- **MCP server is stdio-only in v1.** Remote MCP / HTTP transport is out of scope; Jarvis is a local tool, tunneling its mic and DB to a public endpoint defeats the design.
- **Memory of past conversations:** Claude Code's `~/.claude/.../memory/` cache is local to one machine. Durable memory lives here in `CLAUDE.md`, in `PRD.md`, and in commit messages. Do not rely on the local cache for anything load-bearing.
- **`jarvis setup` was pulled forward from Phase 6 to Phase 0** because the manual install path was friction enough to justify it. The bootstrap scripts (`bootstrap.sh`, `bootstrap.ps1`) are the recommended entry point for a fresh clone on either OS.
- **Ollama install on Mac uses the cask** (`brew install --cask ollama`), not the formula. The cask installs the menu-bar app which auto-starts the daemon; the formula installs only the CLI and forces the user to keep `ollama serve` running manually.
- **Ollama model selection is RAM-aware.** `jarvis setup` detects total RAM via `sysctl hw.memsize` (Mac), `/proc/meminfo` (Linux), `GlobalMemoryStatusEx` (Windows). ≥24 GB pulls both `qwen2.5:7b` (query parsing) and `qwen2.5:14b` (summarizer + agent); below 24 GB pulls only the 7b to avoid swap with Whisper loaded. Matched by exact tag — `qwen2.5:14b` is not satisfied by a `qwen2.5:7b` install.
- **WhisperX + sounddevice are required at bootstrap, not deferred.** Earlier draft tried to defer them to Phase 1 to keep bootstrap fast; that was the wrong call — Jarvis is "a recording bot first," and a bootstrap that doesn't install the recording stack is doing the wrong job. `bootstrap.sh` defaults to `uv sync --extra dev --extra ml --extra audio` and `jarvis setup` lists WhisperX + sounddevice under a top-level "Recording stack:" section. Use `--no-ml` (or `-NoMl` on Windows) only on a future query-only host that talks to the same Postgres but never records.

## Things that have already been tried and rejected

- **Gradio web UI** (v1) — rebuilding it would lose to Claude Desktop / Cursor / ChatGPT Desktop. Out of scope.
- **ChromaDB + SQLite dual-store** (v1) — caused consistency bugs. Hard rule: single store.
- **Chat-summary-only search** (v1) — turn-level queries failed. Hard rule: multi-granularity (turn / chunk / meeting).
- **`make` as the task runner** (Phase 0 first pass) — replaced by `nox` because `make` isn't on Windows by default. Makefile remains as a Mac/Linux convenience shim only.

## How to start a new session

Run these first so you're grounded in current reality, not in this file's snapshot:

```bash
git -C /Users/gupta.amit2/claude-sessions/Jarvis status
git -C /Users/gupta.amit2/claude-sessions/Jarvis log --oneline -15
uv run jarvis setup           # confirms toolchain, DB, Ollama, recording stack
uv run nox -s test_unit       # confirms 21 unit tests still green
```

If `jarvis setup` shows anything ✗ that the build phase claims should be ✓, fix that *before* writing new code — Phase 0 is the foundation. If commits past the ones referenced here exist, read their messages: they may have changed decisions captured above.

## When in doubt

1. Re-read the relevant section of `PRD.md`.
2. Look at the most recent ~10 commits — every meaningful decision has a commit message that explains the *why*.
3. Ask the human before changing an interface in PRD §3 or a "hard rule" above.
