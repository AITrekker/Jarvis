# Phase 2 — overnight build report

**Status:** ✅ **Phase 2 gate met against mocked pyannote/whisper.** Diarization,
speaker resolution, and calendar enrichment all land on `phase2/integration` with
the test pyramid green. Real-pyannote L5 manual smoke is the remaining owner step
(cannot be automated — multi-GB model load + interactive calendar OAuth).

**Branch:** `phase2/integration` (HEAD: see `git log --oneline phase2/integration`)
**Owner action:** Review the diff, run the L5 manual smoke (real mic + real
diarization + real calendar OAuth), then merge to `main` and tag `phase2`.

---

## What landed

| Module | Owner | Implementation | Tests |
|---|---|---|---|
| `jarvis/calendar_sync.py` | Agent D (recovered) | gcsa-based GoogleCalendar client; OAuth flow stores full Credentials payload to keyring; sync upserts events + event_attendees idempotently; find_event_for_recording picks highest overlap ≥50% with start-time tie-break | 16 (unit + 6 integration) |
| `jarvis/transcriber.py` | Driven in-process | DiarizationProvider protocol + PyannoteDiarizer (HF_TOKEN-gated, single-slot lock-protected cache); transcribe() gains optional `diarizer` and `audio_path`; words tagged via max-overlap; turns split on speaker change | 9 (3 phase-1 + 4 phase-2 + 2 helpers) |
| `jarvis/speaker_resolver.py` | Driven in-process | resolve_speakers (centroid + cosine + threshold gating + unknown_<sess>_<n> for sub-low matches); load_enrolled_speakers (pgvector → np.float32); enroll_from_session (slice audio per turn t_start/t_end); enroll_self (idempotent — replaces prior is_self embedding) | 16 (10 unit + 5 integration) |
| `jarvis/persister.py` | Finalizer | Writes `recordings.event_id` from CalendarEvent; writes `turns.person_id / speaker_confidence / needs_review` from speakers map. Single transaction unchanged | shared with recorder phase-2 tests |
| `jarvis/recorder.py` | Finalizer | run() now calls calendar_sync + transcriber.get_diarizer + speaker_resolver.resolve_speakers in sequence, all best-effort. New kwargs `diarize`, `enrich_calendar`, `resolve_speakers` (default True) | 8 phase-1 + 2 phase-2 integration |
| `jarvis/cli.py` | Both agents (clean merge) | `enroll`, `enroll-self`, `people list/add/remove`, `calendar authorize`, `calendar sync [--since/--until]` all wired | covered by module tests |
| `migrations/0002_phase2.sql` | Agent D | event_attendees: add email + display_name columns, swap PK to (event_id, email), make person_id nullable. Idempotent | applied by conftest |

**Schema delta:** the only migration was `0002_phase2.sql`. The Phase 1
schema already had `recordings.event_id`, `turns.person_id`,
`turns.speaker_confidence`, `turns.needs_review`, and the
`speaker_embeddings VECTOR(192)` column.

---

## Test results

```
unit (m="not integration and not ml") :  91 passed
integration (m=integration)           :  17 passed   [pgvector/pgvector:pg16 testcontainer]
ml (m=ml)                             :   1 passed   [cached faster-whisper tiny.en]
ruff check + ruff format --check      :  clean
```

Combined run with the ml test deselected: 108 passed, 1 deselected.

Coverage by module:
- `tests/test_transcriber.py`: 9 tests (faster-whisper mocked + diarizer overlay)
- `tests/test_speaker_resolver.py`: 16 tests (cosine, pgvector roundtrip, all
  threshold paths, type checks, integration enroll-self idempotency,
  enroll_from_session)
- `tests/test_calendar_sync.py`: 16 tests (mocked gcsa + keyring; integration
  upsert, attendee linking, idempotency, overlap heuristic, tie-break)
- `tests/test_recorder_phase2.py`: 2 integration tests (full happy path with
  enrolled person + calendar event; diarizer failure fallback)

---

## Process notes

**Both sub-agents stalled on stream watchdog.** Agent C (diarization +
speaker resolver) stalled while still in the discovery phase — produced no
commits, no working changes. Agent D (calendar sync) produced substantial
working code but did so in the parent worktree by mistake, then stalled
before committing. Recovery:

- Agent D's work was recovered by branching `phase2/calendar` off `main` and
  committing the working-tree diff. One blocking finding fixed during
  recovery: an integration test asserted a global count on `event_attendees`,
  which leaked across tests because `postgres_url` is session-scoped. Tightened
  the assertion to scope by event_id.
- Agent C's missing work was driven in-process by the orchestrator (the
  contracts were locked in pre-flight, the codebase isn't large, and the
  orchestrator already had the PRD context). Total time was less than waiting
  on a re-spawn.
- Stale worktrees were force-removed and pruned per Phase 1's pattern.

**Lessons for Phase 3+ overnight runs:**
- Sub-agents tend to stall during discursive "let me read everything" phases.
  Tighter prompts that point at specific file:line locations for context (and
  link to existing tests as the contract) work better than open-ended briefs.
- Sub-agents misuse worktrees if the prompt doesn't pin them to the
  worktree. The Phase 1 plan specified `branch / worktree` paths explicitly;
  Phase 2 prompts described the worktree only via the `isolation: worktree`
  parameter, which the agents didn't internalize. Future briefs should
  include the absolute worktree path and an explicit "all writes go here".

---

## Code review carry-forwards (deferred, not blocking)

These are minor and consciously deferred. None block the L5 smoke or the merge.

- **Pyannote `use_auth_token` vs `token` kwarg drift.** speaker_resolver's
  `_load_embedding_model` tries `use_auth_token=` first, falls back to a
  separate `Model.from_pretrained(token=...)` path. Works on current
  pyannote.audio 3.x, but the API has churned. If a future pyannote release
  removes both surfaces, swap to `huggingface_hub.login(token=...)` once at
  startup.
- **Diarizer fallback silently downgrades.** When pyannote fails to load
  (e.g. HF_TOKEN expired), the recorder logs a warning and proceeds with
  single-speaker mode. The user only learns from the log line. Consider
  surfacing this as a `RecorderResult.diarization_skipped` flag in Phase 6
  polish.
- **Empty `speakers.get(...)` dict access in persister.** The `speakers` map
  uses `Turn.speaker_raw` keys; if the resolver returned a key the transcript
  doesn't reference (or vice versa), we silently NULL the person_id. This is
  the right runtime behavior but worth a unit test in Phase 3.
- **enroll_self requires ≥ 2s, but PRD recommends 30s.** The 2s minimum is
  a hard floor; a quality warning between 2s and 30s would be a small Phase 6
  polish.
- **calendar_sync's gcsa client kwarg `save_token=False` is gcsa-version
  specific.** If gcsa removes that kwarg, we'd need to drop it. Add a
  `try / except TypeError` around the constructor in Phase 6.

---

## Owner morning checklist

### 1. Skim the diff (~5 min)
```bash
git -C /Users/gupta.amit2/claude-sessions/Jarvis log --oneline main..phase2/integration
git -C /Users/gupta.amit2/claude-sessions/Jarvis diff --stat main..phase2/integration
```

### 2. Run the L5 manual smoke (~15 min)
This is what the agents could not run — real pyannote weights load, real
calendar OAuth, real mic.

```bash
cd /Users/gupta.amit2/claude-sessions/Jarvis
set -a; source .env; set +a
export JARVIS_DB_URL='postgresql://localhost/jarvis'
psql "$JARVIS_DB_URL" -f migrations/0002_phase2.sql   # one-time on the local DB

# 2a. Pre-enroll yourself (≥ 30s of clean reference speech).
uv run jarvis enroll-self path/to/30s_of_amit_speech.wav --name "Amit Gupta"

# 2b. Authorize calendar (browser opens).
uv run jarvis calendar authorize

# 2c. Sync calendar (default ±14 days).
uv run jarvis calendar sync

# 2d. Record during a real meeting on the calendar.
uv run jarvis record --source mic
# (let it run, then in another terminal:)
uv run jarvis stop
# wait ~30s for diarization + persist to finish.

# 2e. Verify.
psql "$JARVIS_DB_URL" -c "
  SELECT r.id, r.event_id, e.title
    FROM recordings r LEFT JOIN events e ON e.id = r.event_id
   ORDER BY r.id DESC LIMIT 3;"
psql "$JARVIS_DB_URL" -c "
  SELECT t.speaker_raw, p.display_name, t.speaker_confidence, t.needs_review,
         left(t.text, 60) AS text
    FROM turns t LEFT JOIN people p ON p.id = t.person_id
   WHERE t.recording_id = (SELECT MAX(id) FROM recordings)
   ORDER BY t.t_start LIMIT 20;"
```

Acceptance: at least one row in `recordings` with non-NULL `event_id` (if a
matching event existed in the sync window), turns carry `speaker_raw`
values like `SPEAKER_00`, `SPEAKER_01`, …, your turns resolve to "Amit
Gupta" with `speaker_confidence ≥ 0.75`, and other attendees either match
their enrolled embeddings or carry `unknown_<session>_<n>` labels with
`needs_review = true`.

### 3. Merge to main + tag
```bash
git checkout main
git merge --no-ff phase2/integration
git tag phase2
git push origin main phase2
```

---

## What's left for Phase 3

Per the PRD §7:
- `summarizer` (fire-and-forget Ollama summarization)
- `search` (hybrid: FTS + pgvector + structured filter, RRF fusion)
- Resolve PRD §8 q1 (embedding model + dim) before any chunk/embedding
  writes — schema currently fixes `chunks.embedding VECTOR(768)`, so picking
  bge-large or nomic-embed-text-v1.5 is straightforward.

Phase 2 carry-forwards above can land alongside Phase 3 or as Phase 2.5
housekeeping — none gate Phase 3.
