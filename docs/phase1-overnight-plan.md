# Phase 1 — overnight build plan

**Goal:** wake up to a `phase1/integration` branch where unit + integration tests pass, with WAV → `turns` rows in Postgres demonstrably working on the synthetic fixture.

**Owner approval gate:** the orchestration script (below) must be launched explicitly. It does not run automatically. The pre-flight commits land under `main` so the plan stays inspectable.

---

## Pre-flight (synchronous, completed before sleep)

These were done before the overnight run is allowed to start. Each is a separate commit on `main`:

- [x] Lock `jarvis/types.py` — every Phase 1+ dataclass present, contract comment at the top.
- [x] Add Recorder spec (PRD §3.14) + stub `jarvis/recorder.py`.
- [x] Tighten Phase 1 persister scope in PRD §3.6 (recordings + turns only).
- [x] Document mic-to-disk model in PRD §2.1 and §3.1.
- [x] Stub `audio_source` (WavFileSource + MicSource), `segmenter`, `transcriber`, `persister` with crisp Phase 1 contracts.
- [x] Generate + commit `tests/fixtures/synthetic_5s.wav` + sidecar JSON.
- [x] Pre-download `faster-whisper tiny.en` into `~/.cache/huggingface/hub/`.
- [x] Verify baseline `uv run pytest` passes (21/21 unit; integration skipped without Docker).

## Pre-flight blockers for the owner (~10 min when back)

1. **Docker Desktop running.** `testcontainers` needs it for the integration tests. Without it, the finalizer can't run L3 (pipeline) or L4 (fault injection).
2. **Approve the PRD edits.** Skim the diff on `main`.
3. **Say "go".** Then I fire the orchestration script.

---

## Sub-agent assignments (parallel, isolated worktrees)

Each runs in its own git worktree branched from `main`. None can touch `jarvis/types.py` or PRD §3 — those are locked.

### Agent A — audio + segmenter
- **Branch / worktree:** `phase1/audio` at `/tmp/jarvis-wt-audio`
- **Owns:**
  - `jarvis/audio_source.py` — implement `WavFileSource` and `MicSource`
  - `jarvis/segmenter.py` — implement `segment()` over Silero VAD
  - `tests/test_audio_source.py`, `tests/test_segmenter.py`
- **Deps already installed:** numpy, soundfile, sounddevice, silero-vad, onnxruntime
- **Forbidden:** editing `jarvis/types.py`, `jarvis/transcriber.py`, `jarvis/persister.py`, `jarvis/recorder.py`, `PRD.md`
- **Pass criteria:**
  - WavFileSource yields chunks summing to 5.0s ±0.1 from `synthetic_5s.wav`
  - segment() finds 2 voiced regions matching the sidecar JSON within 0.2s
  - MicSource has unit tests (mock sounddevice; assert WAV is written)
  - `uv run pytest tests/test_audio_source.py tests/test_segmenter.py` passes
  - `ruff check` + `ruff format --check` clean

### Agent B — transcriber
- **Branch / worktree:** `phase1/transcriber` at `/tmp/jarvis-wt-transcriber`
- **Owns:**
  - `jarvis/transcriber.py` — implement `transcribe()` using faster-whisper directly (whisperx wraps it; for Phase 1 we only need word-timestamped transcription, no alignment, no diarization)
  - `tests/test_transcriber.py`
- **Forbidden:** editing types, audio_source, segmenter, persister, recorder, PRD
- **Pass criteria:**
  - Loads `tiny.en` from local cache (no network)
  - Given an `AudioSegment` with a 1s tone, returns a Transcript with at least one Turn (text content irrelevant — synthetic audio doesn't speak words; assert structure)
  - Every Word + Turn has `speaker_raw == "SPEAKER_00"`
  - Word timestamps are monotonically non-decreasing within a turn
  - Marked `@pytest.mark.ml` (slow); also a fast unit test with a mocked WhisperModel
  - `ruff` clean

### Agent C — persister + recorder + cli + tray
- **Branch / worktree:** `phase1/glue` at `/tmp/jarvis-wt-glue`
- **Owns:**
  - `jarvis/persister.py` — implement against `recordings + turns` only
  - `jarvis/recorder.py` — implement `run()`: pidfile lifecycle, source iteration, post-stop pipeline call, idempotent re-runs
  - `jarvis/cli.py` — wire `jarvis record` and `jarvis stop` (the latter is new; reads the pidfile and signals)
  - `jarvis/tray.py` — pystray icon, Start/Stop, polls pidfile every 1s
  - `tests/test_persister.py` (integration), `tests/test_recorder.py`, `tests/test_cli.py`
- **Forbidden:** editing types, audio_source, segmenter, transcriber, PRD
- **Pass criteria:**
  - `persister.persist_recording()` round-trips a 2-turn fake transcript against testcontainer Postgres
  - Idempotency: persisting twice with the same `session_uuid` does not duplicate rows
  - Fault injection: simulated DB error mid-write leaves zero new rows
  - `recorder.run(WavFileSource(synthetic_5s.wav))` end-to-end produces ≥1 recording row, with at least one turn (mock the transcriber if Agent B's branch isn't available — they run in parallel)
  - Second `recorder.run()` with active pidfile raises `RecorderAlreadyRunning`
  - `jarvis stop` sends SIGTERM via pidfile; recorder finalizes cleanly
  - `tray.py` has unit tests against a mock pystray; live test deferred to morning smoke
  - `ruff` clean

### Finalizer — merge + verify
- **Branch:** `phase1/integration` (sequential, after A/B/C)
- **Steps:**
  1. Merge `phase1/audio`, `phase1/transcriber`, `phase1/glue` into `phase1/integration` (in that order). Resolve any conflicts. Should be near-zero given the locked types and forbidden-file rules.
  2. Run `uv run nox -s lint`.
  3. Run `uv run nox -s test_unit` — all unit tests pass.
  4. Run `uv run nox -s test_integration` — Docker required; pipeline integration test against synthetic fixture writes turns to a real testcontainer Postgres.
  5. Run end-to-end smoke: `uv run jarvis record --source wav:tests/fixtures/synthetic_5s.wav` → SELECT against Postgres → assert turns row count > 0.
  6. Spawn `system-agents:code-review` against the diff for an AI second opinion.
  7. Write `docs/phase1-overnight-report.md` with: branches preserved, test results, any skipped items, code-review findings, files touched.
  8. Push `phase1/integration` (and `phase1/audio`, `/transcriber`, `/glue`) to GitHub. **Do not push to `main`.**

## What the owner does in the morning

1. Read `docs/phase1-overnight-report.md` (top of the diff).
2. Skim the merge commit on `phase1/integration`.
3. Run the L5 manual smoke (real mic):
   - Play a 30–60s YouTube clip on a Bluetooth speaker.
   - `uv run jarvis record --source mic` (responds to mic permission prompt).
   - Stop via tray *or* `uv run jarvis stop` (test both).
   - `psql "$JARVIS_DB_URL" -c "SELECT id, source_label, started_at, ended_at FROM recordings ORDER BY id DESC LIMIT 3;"`
   - `psql "$JARVIS_DB_URL" -c "SELECT speaker_raw, t_start, text FROM turns WHERE recording_id = (SELECT MAX(id) FROM recordings) ORDER BY t_start LIMIT 20;"`
4. If green: merge `phase1/integration` → `main`, tag `phase1`. If not: pair-debug.

## Failure modes covered

- **One sub-agent gets stuck.** Other branches still merge. Finalizer reports which agent was blocked and on what.
- **Whisper download attempt overnight.** Mitigated — model is pre-cached. Agent B is told to load offline; tests using `tiny.en` will fail loudly if the cache is missing rather than silently downloading.
- **Postgres testcontainer can't start.** Owner pre-flight verifies Docker. If Docker is down at run time, integration tests are skipped with a loud warning rather than failing the run.
- **Mic permission prompt blocks unattended runs.** Mitigated — Agent A's MicSource tests use mocked sounddevice. The real mic prompt is owner-approved in the morning during L5.
- **Sub-agents conflict on `types.py`.** Mitigated — types.py is locked; the agents' instructions explicitly forbid touching it.
- **Network blip downloading silero-vad model.** silero-vad ships its model in the wheel; no runtime download.

## Orchestration script

The script lives at `scripts/run_phase1.sh` (added in this commit). It will:

1. Verify pre-flight (model cache present, fixture present, Docker reachable, baseline tests green).
2. Create three git worktrees from `main`.
3. Spawn three parallel `Agent` calls (one per sub-agent), each with a self-contained prompt and explicit constraints.
4. Wait for all three. Each writes a small status JSON.
5. Spawn the finalizer, which reads the three statuses and proceeds with merge.
6. Push results.

**The script is not auto-run.** It is invoked manually after owner says "go".
