# Jarvis — current status & roadmap

**As of:** 2026-05-15 (end of Phase 2; tag `phase2` on `main`)

This file is the user-facing answer to "what can I actually do with this
thing right now, and what's left?" For the engineering source of truth
see [`PRD.md`](./PRD.md) §7. For the per-phase build reports see
[`docs/phase1-overnight-report.md`](./docs/phase1-overnight-report.md)
and [`docs/phase2-overnight-report.md`](./docs/phase2-overnight-report.md).

---

## What you can do right now

Everything below is on `main`. Run `uv run jarvis --help` for the live CLI.

### 1. Record a meeting and get a labeled transcript

```bash
# from a saved WAV (deterministic, fast):
uv run jarvis record --source wav:path/to/meeting.wav

# live mic recording:
uv run jarvis record --source mic    # macOS will prompt for mic permission once
uv run jarvis stop                   # in another terminal, when done
```

The post-stop pipeline runs **VAD → faster-whisper → pyannote diarization →
speaker resolution → Postgres**. Result: one `recordings` row plus per-speaker
`turns` rows with `(speaker_raw, person_id, speaker_confidence, t_start,
t_end, text, needs_review)`.

### 2. Pre-enroll voices

```bash
uv run jarvis enroll-self ~/me_30s.wav --name "Amit Gupta"
uv run jarvis enroll <session_uuid> SPEAKER_01 "Priya Singh" --email priya@example.com
uv run jarvis people list
uv run jarvis people add  "Bob"
uv run jarvis people remove <id>
```

After enrollment, future recordings auto-tag turns with `person_id` when
the cosine similarity exceeds the high threshold (0.75). Between low (0.55)
and high marks `needs_review=true`. Below low → `display_name="unknown_<sess>_<n>"`,
`person_id=NULL`.

### 3. Pull in Google Calendar

```bash
uv run jarvis calendar authorize     # one-time browser OAuth flow
uv run jarvis calendar sync --since 2026-05-01 --until 2026-05-30
```

Refresh tokens persist in macOS Keychain (`jarvis-google-calendar`).
Recordings made during a calendar event auto-link to it via
`recordings.event_id`, and the event's attendee count becomes the
`num_speakers_hint` for diarization.

### 4. Re-run the pipeline on a stored WAV

```bash
# If `jarvis record` captured audio but the post-stop pipeline failed
# (e.g. transient DB outage), the WAV is preserved and can be reprocessed:
uv run jarvis process <session_uuid>
```

Idempotent: running on the same `session_uuid` updates the existing
`recordings` row and re-inserts turns within the same transaction.

### 5. Query the data — raw SQL today

The local store is plain Postgres + pgvector, so any psql / DBeaver / SQL
client works:

```sql
-- last meeting's turns, with resolved speaker names:
SELECT t.t_start, p.display_name, t.text
FROM turns t LEFT JOIN people p ON p.id = t.person_id
WHERE t.recording_id = (SELECT MAX(id) FROM recordings)
ORDER BY t.t_start;

-- everything I (is_self=true) said in the last 7 days:
SELECT r.id AS rec, e.title, t.t_start, t.text
FROM turns t
JOIN recordings r ON r.id = t.recording_id
JOIN people     p ON p.id = t.person_id AND p.is_self
LEFT JOIN events e ON e.id = r.event_id
WHERE r.started_at > NOW() - INTERVAL '7 days'
ORDER BY r.started_at, t.t_start;
```

### What you cannot do yet

| Capability | Phase that builds it |
|---|---|
| `jarvis search "<natural language query>"` | Phase 3 |
| Auto-generated meeting summaries on recordings | Phase 3 |
| Use Jarvis as an MCP tool from Claude Code / Cursor | Phase 4 |
| `jarvis chat` — local conversational agent | Phase 5 |
| Cross-source queries (meetings + Slack + Gmail) | Phase 6 |

So today Jarvis is a **structured local meeting database** with strong
diarization and calendar enrichment. Phases 3–6 layer the search and
conversational surface on top.

---

## Remaining phases (per PRD §7)

### Phase 3 — search & summarization *(next; single agent)*

**Scope:**
- `jarvis/summarizer.py` — fire-and-forget Ollama summarization writing
  `recordings.summary_abstract / summary_action_items / summary_topics /
  summary_embedding`. Failure must not block persist.
- `jarvis/search.py` — hybrid query: Postgres FTS over `turns.text_tsv` +
  pgvector cosine over `chunks.embedding` + structured filters
  (`speaker`, `attendees`, date range). RRF (reciprocal rank fusion) on the
  ranked lists. Small Ollama call extracts the structured filters.
- Persister gains `chunks` writes (still single transaction). 30–90s
  rolling windows.

**Gate:** *"what did I say to `<name>` last week"* on seeded test data
returns the correct turns via direct hybrid search (no LLM planner yet —
that's Phase 5).

**Prereqs the owner must lock first** (PRD §8):
1. **Embedding model + dim.** Schema fixes `chunks.embedding VECTOR(768)`.
   Recommendation: `nomic-embed-text` via Ollama (768d, no extra Python dep).
2. **Query-parser failure mode.** When Ollama is down, fall back to pure
   semantic search or fail loudly? Default proposal: fall back, log warning.
3. **Audio retention.** Keep WAVs forever (default; reprocessing is the
   recovery path) or auto-delete after N days?

### Phase 4 — tool registry + MCP server *(single agent; first usable end-to-end milestone)*

**Scope:**
- `jarvis/tools/` registry: `local_search`, `calendar_query`,
  `enroll_speaker_lookup` (the planner-side surfaces of what's already
  built).
- `jarvis/mcp_server.py` — stdio MCP exposing the registry.
- `jarvis mcp serve` and `jarvis mcp print-config` CLI commands.

**Gate:** Register Jarvis as an MCP server in Claude Code; the compound
query *"what did I say to Priya last week about pricing?"* produces a
correct answer with citations sourced from Jarvis tools. **System is fully
usable end-to-end at the end of this phase** — Claude Code is the loaner
reasoner during Phase 4 → 5.

### Phase 5 — local agent *(single agent)*

**Scope:**
- `jarvis/agent.py` — primary planner/reasoner over the tools registry.
  Conversation state, query decomposition, self-correction, citations.
- `LLMClient` over OpenAI-compatible HTTP, default Ollama
  (`qwen2.5:14b` if RAM permits, else `:7b`).
- `jarvis chat` CLI REPL becomes the day-to-day query surface. Borrow the
  model→tool→model loop pattern from `jonigl/mcp-client-for-ollama`
  (see `docs/references.md`).

**Gate:** The same compound query that worked via Claude Code in Phase 4
also works via `jarvis chat` against the local Ollama agent — correct
answer, multi-turn follow-up (*"…and what about with Raj?"*) inherits
filters, citations preserved. After this lands, MCP demotes from primary
to convenience surface.

### Phase 6 — Slack/Gmail MCP, sub-agents, tray polish, setup *(single agent; v1 ship)*

**Scope:**
- `slack_search` and `gmail_search` MCP tools, registered with both the
  local agent and the Jarvis MCP server.
- Cross-source query *"what's blocking project X across last week's
  meetings and Slack"* — synthesized answer with citations from both
  Postgres and Slack MCP.
- Sub-agent for meeting summarization (replaces the direct `summarizer`
  call from Phase 3).
- Tray polish: state polling, *Open last transcript*, recovery from stale
  pidfile, Windows tray-visibility docs.
- `jarvis setup` health check (Ollama daemon + models, Postgres, mic +
  accessibility permissions on macOS).
- End-to-end docs covering install, `jarvis setup`, registering the MCP
  server in Claude Code, recording from the tray, querying from
  `jarvis chat` and from the MCP host.

**Gate:** Fresh-clone → `bootstrap.sh && jarvis setup && jarvis record
--source wav:fixtures/four_speaker.wav` succeeds; querying the result
both from `jarvis chat` and from Claude Code returns the expected answer
with citations.

---

## Explicitly out of scope (per PRD §9)

These are not on the roadmap. Listed so future-you doesn't try to
re-propose them:

- Real-time / streaming transcription UI
- Bespoke chat UI (web or desktop) — the chat surface is the LLM host or
  `jarvis chat`
- HTTP / FastAPI server and remote MCP transport — local stdio only
- Multi-device sync
- Encryption at rest beyond filesystem defaults
- Sharing / export beyond raw SQL access
- Non-English language tuning

---

## Open carry-forwards (low priority, none blocking)

These are tracked in [`docs/phase2-overnight-report.md`](./docs/phase2-overnight-report.md):

- Diarizer fallback silently downgrades; expose a
  `RecorderResult.diarization_skipped` flag in Phase 6 polish.
- `enroll_self` accepts ≥ 2s but PRD recommends 30s; add a quality
  warning between those bounds.
- `gcsa` `save_token=False` kwarg is version-specific; wrap construction
  in `try/except TypeError`.
- Pyannote `use_auth_token` vs `token` kwarg drift; fall back to
  `huggingface_hub.login(...)` once at startup if both surfaces ever
  disappear.
