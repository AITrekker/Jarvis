# Phase 2 — overnight build plan

**Goal:** wake up to a `phase2/integration` branch where (a) diarization
produces real per-speaker labels, (b) the speaker resolver maps those labels
to known people via voice embeddings, (c) calendar events are mirrored into
Postgres and joined to recordings, and (d) the existing Phase 1 pipeline
still works end-to-end.

**Owner approval gate:** the orchestration script (below) must be launched
explicitly. It does not run automatically. The pre-flight commits land under
`main` so the plan stays inspectable.

---

## Pre-flight (synchronous, completed before sleep)

These were done before the overnight run is allowed to start. Each is a
separate commit on `main`:

- [x] Lock new types in `jarvis/types.py` (`EventAttendee`, `EnrolledSpeaker`).
- [x] Strengthen Phase 2 module stubs (`speaker_resolver.py`, `calendar_sync.py`)
      with locked function signatures and per-function docstrings.
- [x] Update `jarvis/transcriber.py` module docstring with the Phase 2
      contract change (real `speaker_raw`, `num_speakers_hint` becomes
      load-bearing).
- [x] Add CLI stubs for `jarvis enroll-self` and `jarvis calendar authorize`
      (raise `ClickException` until agents implement them).
- [x] Address Phase 1 carry-forwards on main (segmenter VAD threshold kwarg,
      persister `FOR UPDATE`, transcriber LRU+lock, Windows SIGBREAK).
- [x] HF_TOKEN gate verified — pyannote/speaker-diarization-3.1 downloads
      cleanly. Weights cached at `~/.cache/huggingface/`.
- [x] Verify baseline `uv run pytest` passes (66/66 unit; 4/4 integration).

## Pre-flight blockers for the owner (~10 min when back)

1. **Docker Desktop running** — testcontainers needs it for integration tests.
2. **Approve the PRD edits** (skim diff on `main`).
3. **4-speaker fixture WAV** — drop `tests/fixtures/local/four_speaker.wav`
   plus a hand-labeled JSON sidecar. If absent at run time, agents synthesize
   one from 4 distinct TTS voices as a structural test only — diarization
   quality on TTS audio is meaningless, but the wiring still gets exercised.
4. **Say "go".** Then I fire the orchestration script.

---

## Sub-agent assignments (parallel, isolated worktrees)

Each runs in its own git worktree branched from `main`. None can touch
`jarvis/types.py` — that's locked.

### Agent C — diarization + speaker resolver + enroll
- **Branch / worktree:** `phase2/speakers` at `.claude/worktrees/agent-c<hash>`
- **Owns:**
  - `jarvis/transcriber.py` — switch to `whisperx` (faster-whisper backend +
    pyannote diarization). Drop `SPEAKER_RAW_PHASE1`. Real per-word speaker
    labels. Honor `num_speakers_hint`.
  - `jarvis/speaker_resolver.py` — implement every function in the stub:
    `resolve_speakers`, `load_enrolled_speakers`, `enroll_from_session`,
    `enroll_self`. Use pyannote's embedding model (192-dim ECAPA-TDNN).
  - `jarvis/cli.py` — wire `jarvis enroll`, `jarvis enroll-self`, and
    `jarvis people list/add/remove`.
  - Tests: `tests/test_transcriber.py` (extend), `tests/test_speaker_resolver.py`
    (new, both unit-mocked and integration with testcontainer Postgres),
    `tests/test_cli.py` (extend for new commands).
- **Forbidden:** editing `jarvis/types.py`, `jarvis/calendar_sync.py`,
  `jarvis/audio_source.py`, `jarvis/segmenter.py`, `jarvis/persister.py`,
  `jarvis/recorder.py`, `PRD.md`. Coordination is via the locked types only.
- **Pass criteria:**
  - On the synthetic 5s fixture (1 voiced region or fake 2-speaker variant),
    transcribe returns real speaker labels (not "SPEAKER_00" hardcoded).
  - `enroll_self` writes a row to `speaker_embeddings` with is_self=True.
  - `resolve_speakers` against a 2-fixture-speaker scenario assigns the
    enrolled person above threshold_high and the unenrolled as
    `unknown_<sess>_0` with needs_review=True.
  - Unit tests use mocks for pyannote calls; one `@pytest.mark.ml`
    integration test runs against the real cached pyannote weights.
  - `ruff check` + `ruff format --check` clean.

### Agent D — calendar_sync + event matching
- **Branch / worktree:** `phase2/calendar` at `.claude/worktrees/agent-d<hash>`
- **Owns:**
  - `jarvis/calendar_sync.py` — implement `sync_calendar`,
    `find_event_for_recording`, `authorize`. Use `gcsa`
    (google-calendar-simple-api). Persist refresh token in `keyring`
    (service: "jarvis-google-calendar"). Upsert `events` and
    `event_attendees`.
  - `jarvis/cli.py` — wire `jarvis calendar sync` and
    `jarvis calendar authorize`.
  - Tests: `tests/test_calendar_sync.py` (new). Mock the gcsa client and
    keyring; one integration test against testcontainer Postgres asserts
    upsert-then-update yields no duplicates.
- **Forbidden:** editing `jarvis/types.py`, `jarvis/transcriber.py`,
  `jarvis/speaker_resolver.py`, `jarvis/audio_source.py`,
  `jarvis/segmenter.py`, `jarvis/persister.py`, `jarvis/recorder.py`,
  `PRD.md`. Coordination is via the locked types only.
- **Pass criteria:**
  - `sync_calendar(since, until)` against a fake gcsa returning 5 events
    upserts 5 events + their attendees. Re-running returns 0 new rows
    (existing events updated in place).
  - `find_event_for_recording` returns the highest-overlap event when
    multiple events overlap >= 50%. Returns None when overlap < 50%.
  - Attendees with emails matching `people.email` get linked; unknown
    emails get a row with person_id=None.
  - `ruff` clean.

### Finalizer — merge + verify
- **Branch:** `phase2/integration` (sequential, after C and D)
- **Steps:**
  1. Merge `phase2/speakers`, `phase2/calendar` into `phase2/integration`.
     Resolve conflicts (cli.py is the only likely overlap; both agents add
     subcommands).
  2. Wire calendar enrichment + speaker resolution into `recorder.run` —
     this is the integration step that lives in the finalizer pass:
     - `recorder.run` calls `calendar_sync.find_event_for_recording`
       to get an event id.
     - With an event, it loads `calendar_sync` attendees and passes their
       `person_ids` as `candidate_person_ids` to `speaker_resolver`.
     - `transcriber.transcribe` gets `num_speakers_hint=len(attendees)`.
     - `persister.persist_recording` finally receives non-empty
       `speakers={...}` and a non-None `calendar_event`. Update the
       persister to write `recordings.event_id`, `turns.person_id`,
       `turns.speaker_confidence`, `turns.needs_review`.
  3. Run `uv run nox -s lint`.
  4. Run `uv run nox -s test_unit` — all unit tests pass.
  5. Run `uv run nox -s test_integration` — Docker required.
  6. Run end-to-end smoke against `tests/fixtures/local/four_speaker.wav`
     (if present) or a TTS-synthesized fallback. Assert ≥4 distinct
     `speaker_raw` values in the resulting `turns` rows; assert
     `recordings.event_id` is non-NULL when the smoke uses a fake calendar
     event covering the recording window.
  7. Spawn AI code review against the diff; apply blocking fixes.
  8. Write `docs/phase2-overnight-report.md` (mirror Phase 1 structure).
  9. Push `phase2/integration` (and the agent branches). **Do not push to
     `main`.**

## What the owner does in the morning

1. Read `docs/phase2-overnight-report.md`.
2. Skim merge commit on `phase2/integration`.
3. Run the L5 manual smoke:
   - `uv run jarvis calendar authorize` (browser OAuth).
   - `uv run jarvis calendar sync` — verify rows in `events`.
   - `uv run jarvis enroll-self <30s ref WAV>` — verify
     `speaker_embeddings` row with is_self=True.
   - `uv run jarvis record --source mic` during a real meeting; let it
     finish; verify (a) `recordings.event_id` is set, (b) `turns.person_id`
     resolves the owner's voice as "me", (c) other speakers either resolve
     to attendees or carry `unknown_*` labels.
4. If green: merge `phase2/integration` → `main`, tag `phase2`. If not:
   pair-debug.

## Failure modes covered

- **Pyannote weights missing.** Pre-flight downloads them; the agents'
  diarization tests use the cached weights.
- **HF_TOKEN expired or revoked.** Pre-flight verifies it. Run-time
  failures surface as a 401 in agent logs; the finalizer reports them
  rather than silently masking.
- **gcsa OAuth requires a browser.** Agent D's tests mock the gcsa
  client; the real OAuth flow stays a manual L5 step.
- **4-speaker fixture absent.** Finalizer falls back to TTS-synthesized
  audio for structural verification only; quality assertion (e.g. WER)
  becomes a manual L5 step on real audio.
- **Sub-agents conflict on `cli.py`.** Both add new subcommands. Click
  groups are independent so merges concatenate cleanly; the finalizer
  resolves any line-level overlap.
- **Recorder integration is owned by the finalizer**, not by C or D.
  This keeps the agents' blast radius narrow.

## Orchestration script

`scripts/preflight_phase2.sh` is the gate; the orchestrator script will
land in the same commit. It:

1. Verifies pre-flight (HF token, weights cache, fixture, Docker, baseline
   tests).
2. Creates two git worktrees from `main`.
3. Spawns two parallel `Agent` calls (C and D), each self-contained.
4. Waits for both. Each writes a small status JSON.
5. Spawns the finalizer, which reads statuses and proceeds with merge +
   recorder integration + smoke + report.
6. Pushes results to GitHub.

**The script is not auto-run.** Owner says "go" before launch.
