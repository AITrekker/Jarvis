# Session resume — Jarvis project

You are picking up work on **Jarvis**, a personal local-only meeting recorder + searchable memory tool. The owner is Amit Gupta (single user, Mac primary, Windows second-class). This file is the only thing you've been told to read; you have NO other context from prior sessions.

**Read these first, in this order, before doing anything else:**

1. `CLAUDE.md` — project conventions, hard rules, current build phase status
2. `PRD.md` — full design spec; the source of truth for architecture (§3 module specs, §7 build phases)
3. `docs/phase1-overnight-report.md` — what Phase 1 delivered
4. `docs/phase2-overnight-report.md` — what Phase 2 delivered + the carry-forwards
5. `docs/references.md` — OSS repos worth borrowing from per phase

Run these to ground yourself in current reality (not this file's snapshot):

```bash
git -C /Users/gupta.amit2/claude-sessions/Jarvis status
git -C /Users/gupta.amit2/claude-sessions/Jarvis log --oneline -20
git -C /Users/gupta.amit2/claude-sessions/Jarvis branch -a | head -20
git -C /Users/gupta.amit2/claude-sessions/Jarvis tag -l "phase*"
uv run pytest -q -m "not integration and not ml"
```

If commits past the ones referenced below exist, read their messages — they may have changed decisions captured here. **The PRD wins over this file if they conflict; flag the contradiction to the owner before acting on it.**

---

## State as of 2026-05-15 (end of Phase 2)

### What is done

**Phase 0** (foundation) — complete and on `main`. Toolchain, Postgres+pgvector schema, Ollama daemon with `qwen2.5` pulled, 21 unit tests, `bootstrap.sh` / `bootstrap.ps1`, cross-platform helpers (`_proc.py`, `_paths.py`, `_progress.py`, `_logging.py`).

**Phase 1** (capture + transcribe + persist) — complete on `main`, tag `phase1`. WAV → `recordings` + `turns` rows in Postgres. `audio_source` (WavFileSource + MicSource), `segmenter` (Silero VAD), `transcriber` (faster-whisper, single-speaker mode `SPEAKER_00`), `persister` (single transaction over recordings + turns; chunks/embeddings deferred to Phase 3), `recorder` (pidfile lifecycle + post-stop pipeline + Windows SIGBREAK), `tray` (pystray), `cli` (record / stop / process / tray).

**Phase 1 carry-forwards (already addressed before Phase 2):** segmenter VAD threshold as kwarg (`DEFAULT_VAD_THRESHOLD = 0.5` for production, `FIXTURE_VAD_THRESHOLD = 0.05` for the synthetic tone fixture); persister `FOR UPDATE` row lock; Whisper model cache LRU+lock (size 1); Windows graceful stop via SIGBREAK + CREATE_NEW_PROCESS_GROUP.

**Phase 2** (speakers + calendar) — complete on `main`, tag `phase2`. Three real things:

- **Diarization** (`jarvis/transcriber.py`): pyannote 3.1 wired in via a `DiarizationProvider` protocol + `PyannoteDiarizer` (single-slot lock-protected cache, gated on `HF_TOKEN`). `transcribe()` gains optional `diarizer` and `audio_path` params. Words tagged via max-overlap with diarizer spans; turns split on speaker change. `num_speakers_hint` propagates to pyannote when set. Phase 1 path preserved when `diarizer=None`.
- **Speaker resolution** (`jarvis/speaker_resolver.py`): per-speaker centroid via `pyannote/embedding` (512-dim X-vector — the PRD originally said 192-dim ECAPA-TDNN, but the current pyannote release uses 512; migration `0003_phase2_embedding_dim.sql` widens the schema column to match). Cosine vs enrolled candidates → threshold gating into `ResolvedSpeaker` rows. `THRESHOLD_HIGH = 0.75`, `THRESHOLD_LOW = 0.55`. Sub-0.5s audio short-circuits to `unknown_<sess>_<n>`.
- **Calendar sync** (`jarvis/calendar_sync.py`): gcsa-based GoogleCalendar client. OAuth flow stores full Credentials payload to keyring under service `"jarvis-google-calendar"`. `sync_calendar(since, until)` upserts events + event_attendees idempotently. `find_event_for_recording(started, ended)` picks highest overlap ≥50% of recording duration; tie-break by smallest start-delta. Migration `0002_phase2.sql` switched `event_attendees` PK from `(event_id, person_id)` to `(event_id, email)` so unmatched calendar attendees can be persisted with `person_id=NULL`.

**Recorder integration** (`jarvis/recorder.py`): `recorder.run()` calls calendar lookup + diarizer load + speaker resolution in sequence, all best-effort. Any single failure (no `HF_TOKEN`, calendar not authorized, embedder dies, etc.) degrades gracefully without losing the recording. New kwargs `diarize / enrich_calendar / resolve_speakers` (default `True`) so tests can drive Phase 1 behavior without monkeypatching pyannote.

**Persister** (`jarvis/persister.py`): now writes `recordings.event_id` from `CalendarEvent` and `turns.person_id / speaker_confidence / needs_review` from the `speakers` map keyed on `Turn.speaker_raw`. Single transaction unchanged.

**CLI surface (`jarvis/cli.py`):** `record`, `stop [--force]`, `process <session_uuid>`, `tray`, `enroll <session> <speaker_raw> <name> [--email]`, `enroll-self <wav> [--name]`, `people list / add / remove`, `calendar authorize`, `calendar sync [--since/--until]`. Phase 3 stubs raising `ClickException`: `search`.

**Tests:** 91 unit + 17 integration + 1 ml = 109 total. Lint clean. Mocked tests fully cover all module contracts; one real-pyannote end-to-end smoke verified against `tests/fixtures/local/pyannote_sample.wav` (Sheila + Diane, 30s, 2-speaker, downloaded from pyannote-audio's tutorial).

### Real-world Phase 2 verification (2026-05-15)

Owner asked for a real-audio test. Downloaded https://github.com/pyannote/pyannote-audio/raw/develop/tutorials/assets/sample.wav (30s, 16kHz mono, 2 speakers). Three real bugs surfaced and were fixed in the same pass (commit `6f03eb5`):

1. **Pyannote `AudioDecoder` import error** — torchcodec ships compiled against ffmpeg 4-7; system has ffmpeg 8 (`libavutil.60`). Fix: feed pyannote a `{"waveform": tensor, "sample_rate": sr}` dict instead of a path. Bypasses torchcodec entirely.
2. **Pyannote 3.4 `DiarizeOutput` wrapper** — pipeline now returns `DiarizeOutput` with `.exclusive_speaker_diarization` (Annotation), not the bare Annotation. Fix: prefer `.exclusive_speaker_diarization`, fall back to legacy.
3. **Embedding dim mismatch** — `pyannote/embedding` is actually 512-dim X-vector, not 192-dim ECAPA-TDNN. Bumped `EMBEDDING_DIM` to 512; added migration 0003 to widen `speaker_embeddings.embedding`.

After fixes, 10 turns persisted across 2 distinct `speaker_raw` values; Sheila (enrolled from a 3s reference) resolved at conf 0.752 in every one of her turns; Diane (unenrolled) left at conf 0.348 with `needs_review=True`.

### Open Phase 2 carry-forwards (deferred, not blocking)

None block Phase 3. Address as Phase 3 housekeeping or a Phase 2.5 cleanup:

- **Diarizer fallback silently downgrades.** When pyannote fails to load (no HF_TOKEN, weights missing) the recorder logs a warning and proceeds with single-speaker mode. User only learns from log lines. Surface a `RecorderResult.diarization_skipped` flag in Phase 6.
- **enroll_self ≥ 2s minimum** but PRD recommends 30s. Add a quality warning for 2 ≤ duration < 30.
- **calendar_sync `save_token=False` is gcsa-version-specific.** Wrap constructor in try/except TypeError if a future gcsa drops the kwarg.
- **Pyannote `use_auth_token` vs `token` kwarg drift.** speaker_resolver tries `use_auth_token=` first, falls back via `Model.from_pretrained(token=...)`. If both surfaces ever disappear, switch to `huggingface_hub.login(token=...)` once at startup.

### Owner-only items (not blocking Phase 3)

- **L5 manual mic smoke against a real meeting** has not been run. Pyannote tutorial WAV verified the pipeline works against real audio, but a real mic recording (with macOS permission prompt + a real Google Calendar event covering the window + the owner pre-enrolled as "me") would close the loop on the *user-facing* path. Steps: see `docs/phase2-overnight-report.md` "Owner morning checklist". Skip if you don't have time — the automated tests + the pyannote sample run already cover the data path.

---

## What is next: Phase 3 — search & summarization

Per PRD §7, Phase 3 is a single-agent scope:

### `jarvis/summarizer.py`
- Fire-and-forget Ollama summarization. Reads transcript via `recording_id`, calls `qwen2.5:7b` (or `:14b` if RAM permits — see `config.toml`) with a small structured prompt, returns `Summary(abstract, action_items, topics)`.
- Persists to `recordings.summary_abstract / summary_action_items / summary_topics / summary_embedding`. The embedding column is 768-dim (schema-fixed); needs the embedding model decision below.
- Failure must not block the persister's commit. The current Phase 2 recorder calls `persister.persist_recording` synchronously; the summarizer should run in a background thread or subprocess after persist returns.

### `jarvis/search.py`
- `search(query: str, k: int = 20) -> list[SearchHit]` per PRD §3.8.
- Hybrid: BM25/Postgres FTS over `turns.text_tsv` + pgvector cosine over `chunks.embedding`, both filtered by structured criteria. RRF (reciprocal rank fusion) merges the two ranked lists.
- Structured filter extraction is small-LLM-driven (Ollama `qwen2.5:7b`): `StructuredQuery(speaker, attendees, date_from, date_to, semantic_query)`. PRD §8 q2 governs the failure mode (default proposal: fall back to pure semantic, log warning).
- Direct CLI surface (`jarvis search "<query>"`). No LLM planner yet (that's Phase 5).

### `chunks` writes (deferred from Phase 1/2)
- Persister gets a third write: `chunks` rows with `(recording_id, t_start, t_end, text, speakers[], embedding)`. Still single transaction.
- Chunk windowing is 30–90s rolling per PRD §4.
- Schema fixes `chunks.embedding VECTOR(768)`. The embedding model needs to be locked before writing — see prerequisites below.

### Phase 3 gate (per PRD §7)
*"What did I say to `<name>` last week"* on seeded test data returns correct results via direct hybrid search.

### Phase 3 prerequisites the owner must lock first

Confirm with the owner before spawning a Phase 3 agent:

1. **Embedding model + dim (PRD §8 q1).** Schema is `VECTOR(768)`. Candidates:
   - `nomic-embed-text` (768d) — Ollama-native, no extra Python dep, lowest friction. **Recommended.**
   - `bge-small-en` (384d) — would need a schema change; reject.
   - `all-mpnet-base-v2` (768d) — sentence-transformers dep already pulled in via the `ml` extra, but adding another runtime model.
   Default: lock `nomic-embed-text` via Ollama. One small change to `config.toml` adds it.
2. **Query-parser failure mode (PRD §8 q2).** When Ollama is down: fall back to pure semantic (current default proposal) or fail loudly?
3. **Audio retention (PRD §8 q3).** Keep WAVs forever (default proposal — reprocessing is the recovery path) or auto-delete after N days?

### Recommended Phase 3 process

Phase 3 is sequential, single-agent (the search + summarizer are tightly coupled to schema decisions and don't parallelize cleanly). Mirror Phase 1/2 shape:

1. **Pre-flight (synchronous, with owner):** lock the three §8 questions above, decide chunk windowing parameters (30s with 5s overlap is the typical default), pre-pull the embedding model. Stub `summarizer.py` and `search.py` with locked function signatures.
2. **Single agent:** implements summarizer + chunks writes + search + StructuredQuery parser. Tests against testcontainer Postgres.
3. **Finalizer:** runs full pyramid, verifies the gate against seeded fixture data, writes `docs/phase3-overnight-report.md`, pushes `phase3/integration`.
4. **Owner morning:** review diff, run a few real queries against the existing Phase 2 recordings (the pyannote sample + any new ones), merge to `main`, tag `phase3`.

### Notes on the agent stalling pattern (lessons from Phase 2)

Both Phase 2 sub-agents stalled on the stream watchdog (no progress for 600s during the discursive "let me read everything" phase). Recovery: I drove Agent C's work in-process; recovered Agent D's working changes from the parent worktree (D had run in the wrong worktree). For Phase 3:

- Tighter prompts pointing at specific `file:line` locations beat open-ended briefs.
- Explicit absolute worktree path in the prompt + an "all writes go here" line beats relying on the `isolation: worktree` parameter alone.
- For tightly-scoped phases (Phase 3 is one agent), driving in-process is often faster than waiting on respawns.

---

## Hard rules (do not violate without explicit owner approval)

These come from `CLAUDE.md` and the v1 failure modes in PRD §1:

1. **Single store: Postgres + pgvector.** No SQLite, no Chroma, no separate vector DB.
2. **No LLM in the recording pipeline.** Capture stays deterministic.
3. **One primary agent in v1.** Sub-agents only for bounded heavy reasoning (summarization, citation drafting). No multi-agent orchestration.
4. **Three surfaces, one backend.** CLI, MCP server (Phase 4), local agent / `jarvis chat` (Phase 5). All adapters; business logic lives in modules.
5. **Cross-platform.** `pathlib`, `sys.platform` branches, `_paths` helpers. Never hardcode XDG paths.
6. **Local LLM via Ollama by default**, OpenAI-compatible HTTP shim. No cloud LLM calls from Jarvis itself.
7. **No bespoke chat UI.** Owner's org disallows Claude Desktop. The end-state primary query surface is `jarvis chat` (Phase 5, local Ollama agent). Claude Code is the *bridge* during Phase 4 via `jarvis mcp serve`. Never propose building a web UI, Electron app, or desktop chat client.

## How to work in this repo (from CLAUDE.md)

- `uv sync --extra dev --extra ml --extra audio --extra calendar --extra tray` to install everything Phase 2 needs; `uv run jarvis <cmd>` to run.
- Tasks: `uv run nox -s lint / test_unit / test_integration / smoke` (the noxfile installs extras for all sessions, fixed in `fb254ca`).
- Lint scope excludes `docs/v1-reference` and `.claude/` (sub-agent worktrees).
- Migrations are raw SQL in `migrations/`; conftest applies all `*.sql` files in lexical order to the testcontainer.
- Recordings, audio, the local DB, and `.env` are gitignored on purpose. `tests/fixtures/local/` is also gitignored (real meeting WAVs go there).
- Surface modules (`cli.py`, `mcp_server.py`, `tray.py`) must contain zero business logic.
- Stub future modules with `raise NotImplementedError("built in Phase N")`. Never silent `pass`.

## Decisions made in conversation that aren't in the PRD body

(Most are now in the PRD; cross-check before acting.)

- CLI binary is `jarvis`, not `recorder`.
- Python 3.12 is the dev/CI baseline (`>=3.11,<3.13`).
- Tray uses `pystray` for cross-platform support (rejected `rumps`).
- MCP server is **stdio-only** in v1.
- Ollama install on Mac uses the cask, not the formula.
- Ollama model selection is RAM-aware (≥24 GB pulls 14b + 7b, <24 GB pulls 7b only).
- WhisperX + sounddevice are required at bootstrap, not deferred.
- Phase 1 persister scope: `recordings + turns` only. `chunks/embeddings` are Phase 3.
- Phase 1 transcriber: `faster-whisper` directly. Phase 2 added pyannote as an overlay (kept faster-whisper for transcription; whisperx alignment never wired in).
- Mic recording writes a WAV to disk live; pipeline runs **post-stop** on that WAV. No streaming pipeline in v1.
- `JARVIS_WHISPER_MODEL` / `_DEVICE` / `_COMPUTE_TYPE` env-var overrides exist.
- **Phase 2 (2026-05-15):** `EMBEDDING_DIM = 512` (pyannote/embedding is 512-dim X-vector, not 192-dim ECAPA-TDNN as PRD §3.4 originally said). Migration 0003 widened the schema column.
- **Phase 2 (2026-05-15):** `event_attendees` PK is `(event_id, email)`, not `(event_id, person_id)`. Calendar attendees may not match a known `people` row, so email is the natural key from the calendar's perspective. Migration 0002.
- **Phase 2 (2026-05-15):** `recorder.run()` exposes `diarize / enrich_calendar / resolve_speakers` kwargs for tests to drive Phase 1 behavior without monkeypatching pyannote.

## Things that have been tried and rejected (do not re-propose)

- **Gradio web UI** (v1) — out of scope.
- **ChromaDB + SQLite dual-store** (v1) — caused consistency bugs.
- **Chat-summary-only search** (v1) — turn-level queries failed.
- **`make` as task runner** — replaced by `nox` for Windows compatibility.
- **Forking whole-app meeting recorders** like Meetily — different stacks, would mean rewriting their storage layer. See `docs/references.md`.
- **Browser-side WebGPU/WASM transcription** — surveyed and rejected.
- **whisperx alignment (Phase 2 originally planned this)** — kept faster-whisper instead. Pyannote diarization runs separately and labels are mapped onto whisper words via timestamp overlap. Word timestamps from faster-whisper are good enough; whisperx's wav2vec2 alignment was never load-bearing.

## How to behave in this session

- The owner is software-literate and Salesforce Agentforce dev team. They want to learn agentic patterns by building Jarvis. They've been burned by jumping into code without locked APIs, so the workflow is: read first, lock interfaces, then build.
- They prefer concise responses. State results and decisions directly. No trailing summaries.
- For Phase work: lock `jarvis/types.py` and any new module stubs **before** spawning sub-agents. The Phase 1/2 pre-flight commit pattern is the template.
- For surface changes: keep `cli.py`, `mcp_server.py`, `tray.py` as adapters. Business logic must live in dedicated modules.
- Pushing to GitHub is OK. Pushing to `main` requires owner approval; integration branches push freely.
- The owner's GitHub remote is `AITrekker/Jarvis`. The git OAuth token in this environment cannot push files under `.github/workflows/` (missing `workflow` scope) — the CI workflow at `.github/workflows/ci.yml` is intentionally untracked.

---

## When in doubt

1. Re-read the relevant section of `PRD.md`.
2. `git log --oneline -20` — every meaningful decision has a commit message.
3. Ask the owner before changing an interface in PRD §3 or any of the seven hard rules above.
4. The session-resume command sequence at the top of this file is the right place to start every session.
