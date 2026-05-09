# PRD: Personal Meeting Recorder & Searchable Memory

**Status:** Draft v1
**Owner:** Amit Gupta
**Last updated:** 2026-05-09

---

## 1. Problem & goals

Build a personal tool that records meeting audio, transcribes it locally, enriches it with calendar context, stores transcripts in a searchable form, and answers natural-language questions like *"what did I say to Priya last week?"*.

This is a rebuild of a prior attempt that failed in four specific ways. Each failure maps to a non-negotiable design decision below.

| Prior failure | This time |
|---|---|
| Speaker identification was unreliable | WhisperX diarization + voice-embedding enrollment store, calendar-attendee count as prior |
| No calendar context | Calendar sync is a first-class pipeline stage, not an afterthought |
| Dual-write consistency between metadata DB and vector DB | Single store: Postgres + pgvector. No two-store coordination |
| Only summaries were searchable; turn-level queries failed | Multi-granularity storage (turn / chunk / meeting), hybrid search (FTS + vector + metadata filters) |

### Goals (v1)
- Record audio from a configurable source, transcribe with speaker labels, persist with calendar metadata
- Answer queries scoped by speaker, attendee, time range, and semantic content
- Run entirely locally (no cloud LLM calls, no cloud storage)
- Be testable end-to-end without a live meeting

### Non-goals (v1)
- Multi-user / shared deployment
- Real-time transcription UI (batch processing after recording stops is fine)
- Mobile capture
- Any cloud sync or remote backup
- Ambient/always-on capture (mic is gated to active recording sessions)

### Success criteria
- Given a recorded meeting WAV + a calendar event, the pipeline produces searchable turn-level data within 2× realtime on an M-series Mac
- The query *"what did I say to <attendee> last week"* returns turns where `speaker=me AND <attendee> in event.attendees AND ts within last 7 days`, ranked by semantic relevance
- Speaker labels are correct for ≥85% of turns on a 4-speaker test meeting once enrollment exists for all participants
- A full pipeline run is reproducible from a stored WAV file (no live-meeting dependency for tests)

---

## 2. Architecture overview

```
                                                                                
   AudioSource          AudioSegmenter           Transcriber         
   (mic|system|wav)  →   (VAD + chunking)    →   (WhisperX)              
                                                       │                    
                                                       ▼                    
   CalendarSync                                  Diarizer +                 
   (Google/EventKit)                             SpeakerResolver            
        │                                              │                    
        ▼                                              ▼                    
   events table                                  Enricher                   
        │                                        (joins calendar event)     
        └──────────────────────────────────────►       │                    
                                                       ▼                    
                                                  Persister                 
                                                  (Postgres + pgvector,     
                                                   single transaction)      
                                                       │                    
                                                       ▼                    
                                                  Summarizer (Ollama)       
                                                       │                    
                                                       ▼                    
                                                  SearchAPI                 
                                                  (hybrid: FTS+vec+filter)  
```

Every arrow is an in-process function call or a row in Postgres. There is no message bus, no second datastore, no network call outside Calendar sync and Ollama (localhost).

### 2.1 Concurrency model

Single *process*, not single *thread*. The pipeline has three stages with different concurrency needs:

- **Capture (live recording)** — runs on a dedicated thread driven by PortAudio's callback. Pushes PCM frames into a bounded ring buffer (default 60s of audio). On overflow, oldest frames are dropped with a logged warning. The capture thread never touches Postgres, never calls Whisper, never blocks on I/O beyond the queue push. This is the only stage with hard real-time requirements.
- **Pipeline (segment → transcribe → diarize → resolve → persist)** — synchronous, runs *after* `record` stops in v1. It's a batch job; "the CLI is busy for two minutes" is acceptable. No internal concurrency required.
- **Summarizer** — fire-and-forget after `persist` commits. Runs in a background thread or subprocess; its failure or slowness must not roll back or block the recording write.
- **Search** — independent CLI invocation. Talks only to Postgres. No shared state with capture or pipeline; safe to run while a recording is being processed.
- **Calendar sync** — runs on a schedule (cron / `jarvis calendar sync`), never inline with `record`. The orchestrator joins the recording to a calendar event after the fact during the pipeline stage.

Hang-risk checklist (must hold):
- Capture thread does no DB I/O and no model inference
- Bounded queue between capture and downstream stages, with documented overflow behavior
- Sub-agent and Ollama failures are caught and logged; they never propagate to persist
- Search has no dependency on Whisper, pyannote, or Ollama model load

### 2.2 System layers

The system has four distinct layers with different programming models. Conflating them is a common pitfall — name them up front.

| Layer | Programming model | Examples in this project |
|---|---|---|
| **Pipeline** | Deterministic dataflow, no LLM in the loop | Record → segment → transcribe → diarize → resolve → persist |
| **Tool** | Pure function or MCP endpoint, callable by an agent | Local hybrid search, calendar lookup, Slack MCP, Gmail MCP |
| **Agent** | LLM loop with tools and conversation state | The conversational entry point; decides what to call and when |
| **Sub-agent** | LLM spawned for a bounded task with its own context window | Meeting summarization; citation drafting from many hits |

**Rules:**
- The recording pipeline stays deterministic. No LLM in the capture path — it adds latency, cost, and non-determinism for no benefit.
- The conversational layer is **one primary agent** in v1, plus tools, plus on-demand sub-agents.
- Multi-agent decomposition (specialists with an orchestrator) is **explicitly out of scope for v1**. Revisit only if a concrete need surfaces — premature decomposition wastes time on inter-agent protocol design.

### 2.3 User-facing surfaces

Jarvis exposes the same backend through three surfaces with different jobs. **We do not build a bespoke chat UI.** In 2026 the chat surface is the LLM host (Claude Desktop, Cursor, ChatGPT Desktop) — rebuilding it loses to what those apps already ship.

| Surface | Purpose | Built in phase |
|---|---|---|
| **CLI** (`jarvis ...`) | Dev loop, scripting, cron jobs, headless servers. Every other surface is a thin adapter over the same Python functions the CLI calls. | 0 → ongoing |
| **MCP server** (`jarvis mcp serve`) | Production query path. Users point Claude Desktop / Cursor / ChatGPT Desktop at it and query their meeting memory from the chat app they already use. Stdio transport (local-only); remote MCP / HTTP is out of scope for v1. | 4 |
| **Tray app** (`jarvis tray`) | Recording-control surface only. Runs as a separate process from the recorder; provides a visible 🔴 in the OS menu bar / system tray with a one-click stop. Cross-platform via `pystray`. **Not** a UI for search or chat. | 1 (basic) → 2 (polish) |

**Architecture:**
```
        ┌─── jarvis.cli (Click) ────────┐
        │                                │
        ├─── jarvis.mcp_server (MCP) ──┐ │
core ◄──┤                                │
        ├─── jarvis.tray (pystray) ────┐ │
        │                                │
        └─── (future: jarvis.http) ────┘ │
                                          ▼
                              jarvis.tools registry
                              jarvis.search / calendar / persister / ...
```

**Rules:**
- All three surfaces are **adapters**, not implementations. Business logic lives in modules under `jarvis/` and the `tools` registry. A surface adds zero behavior the CLI doesn't already have.
- The tray app talks to the recorder via OS-level signals (SIGTERM on Unix, `taskkill` on Windows) and a pidfile in `~/.local/share/jarvis/run/recorder.pid`. It does not embed Python recorder logic.
- HTTP / FastAPI is not in v1. Add it the day a custom non-chat UI (timeline, enrollment wizard, needs-review queue) is justified — not before.

### 2.4 LLM runtime

**Default: Ollama**, daemon at `http://localhost:11434`. Same install on macOS, Windows, Linux; OpenAI-compatible API; native tool-calling on `qwen2.5` / `llama3.x`. The `jarvis setup` command verifies Ollama is on `PATH`, the daemon is reachable, and required models are pulled (pulls them if missing).

**Pluggable.** All LLM calls go through a single `LLMClient` over the OpenAI-compatible HTTP shape, so any runtime that speaks it (LM Studio, llama.cpp `server`, vLLM, even a remote API) is a config change in `[ollama] host`, not a code change.

**RAM-aware defaults.** `qwen2.5:14b` is ~10–14 GB resident at runtime; on a 16 GB machine it will swap when Whisper + pyannote are also loaded. Setup detects RAM and picks:
- ≤16 GB → `qwen2.5:7b` for everything; summarization runs serially after persist commits
- ≥32 GB → `qwen2.5:14b` for agent + summarizer, `qwen2.5:7b` for query parsing, summarization fire-and-forget per §2.1

Summarization being fire-and-forget after persist is what makes the small-RAM mode safe — the recording write is never blocked by a model that doesn't fit.

---

## 3. Module specifications

Each module below is independently buildable. Modules expose typed Python interfaces; downstream modules depend only on the interface, not the implementation. Agents may implement modules in parallel as long as they conform to the contract.

### 3.1 `audio_source` — capture abstraction

**Purpose:** Yield PCM audio chunks from a configurable source. The pipeline must not know which source it's reading from.

**Interface:**
```python
class AudioSource(Protocol):
    sample_rate: int  # always 16000 for v1
    channels: int     # always 1 (mono) for v1
    source_label: str # "mic" | "system" | "wav:<filename>"

    def __iter__(self) -> Iterator[AudioChunk]: ...
    def close(self) -> None: ...

@dataclass
class AudioChunk:
    pcm: np.ndarray  # int16, shape (n_samples,)
    t_start: float   # seconds since session start
    t_end: float
```

**Implementations (v1):**
- `MicSource` — `sounddevice` InputStream, default input device
- `WavFileSource` — reads a WAV file, emits chunks at real-time pacing OR as fast as possible (configurable; tests use fast mode)
- `SystemAudioSource` — reads from a named device (e.g. `BlackHole 2ch`); listed in v1 scope but **lowest priority**, build last

**Acceptance:**
- All three implementations produce identical downstream behavior when fed equivalent audio
- `WavFileSource` in fast mode processes 10 minutes of audio in <30s
- Switching sources is a single config value; no other module changes

---

### 3.2 `segmenter` — VAD + chunking

**Purpose:** Convert continuous audio into utterance-bounded segments suitable for Whisper.

**Implementation:** Silero VAD or `webrtcvad`. Merge adjacent voiced regions; cap segment length at 30s; minimum segment 0.5s.

**Interface:**
```python
def segment(source: AudioSource) -> Iterator[AudioSegment]: ...

@dataclass
class AudioSegment:
    pcm: np.ndarray
    t_start: float
    t_end: float
```

**Acceptance:** On a test WAV with known speech regions, segment boundaries match ground truth within ±200ms.

---

### 3.3 `transcriber` — WhisperX wrapper

**Purpose:** Produce word-level transcripts with timestamps and per-word speaker tags via diarization.

**Implementation:** WhisperX (faster-whisper backend + pyannote diarization). Run diarization once over the full session, not per-segment, so speaker labels are consistent.

**Interface:**
```python
def transcribe(
    segments: Iterable[AudioSegment],
    num_speakers_hint: int | None = None,
) -> Transcript: ...

@dataclass
class Word:
    text: str
    t_start: float
    t_end: float
    speaker_raw: str  # "SPEAKER_00", "SPEAKER_01", ...
    confidence: float

@dataclass
class Turn:
    speaker_raw: str
    t_start: float
    t_end: float
    text: str
    words: list[Word]

@dataclass
class Transcript:
    turns: list[Turn]
    language: str
```

**Notes:**
- `num_speakers_hint` comes from the calendar event's attendee count (passed in by the orchestrator). This is the single biggest lever for diarization quality.
- Models are loaded once and cached.

**Acceptance:**
- Word error rate ≤15% on a clean English test recording
- On a 4-speaker test recording with `num_speakers_hint=4`, diarization produces exactly 4 speaker labels

---

### 3.4 `speaker_resolver` — voice enrollment & identity assignment

**Purpose:** Map `SPEAKER_00` → `"Priya Singh"` using stored voice embeddings.

**Storage:** `speaker_embeddings` table — one or more embedding vectors per known person, plus a `person_id` referencing the `people` table.

**Algorithm:**
1. For each `speaker_raw` in the transcript, compute a centroid embedding from a sample of that speaker's audio (pyannote embedding model).
2. Nearest-neighbor lookup against `speaker_embeddings` (cosine similarity).
3. If best match similarity > `threshold_high` (e.g. 0.75): assign that person.
4. If between `threshold_low` and `threshold_high`: assign + flag `needs_review`.
5. If below `threshold_low`: assign synthetic label `unknown_<session>_<n>` and queue for manual labeling.
6. The user (me) is always pre-enrolled.

**Enrollment loop:**
- A CLI command `enroll-from-meeting <session_id> <speaker_raw> <person_id>` adds that session's embedding for that raw speaker to `speaker_embeddings`.
- Over time, attendees who appear repeatedly accumulate embeddings; resolution accuracy improves automatically.

**Interface:**
```python
def resolve_speakers(
    transcript: Transcript,
    audio: np.ndarray,
    sample_rate: int,
    candidate_person_ids: list[int] | None = None,  # from calendar attendees
) -> dict[str, ResolvedSpeaker]: ...

@dataclass
class ResolvedSpeaker:
    person_id: int | None
    display_name: str  # real name or "unknown_<session>_<n>"
    confidence: float
    needs_review: bool
```

**Notes:**
- `candidate_person_ids` restricts the search space to calendar attendees when available — major precision boost.

**Acceptance:**
- Given enrollment data for 3 of 4 speakers, the 3 enrolled are correctly resolved with confidence > `threshold_high`; the 4th gets an `unknown_*` label.

---

### 3.5 `calendar_sync` — Google Calendar / EventKit ingest

**Purpose:** Maintain a local mirror of calendar events so recordings can be joined to event metadata.

**Implementation:** Google Calendar API via OAuth (refresh token stored in macOS Keychain). EventKit is a stretch goal; not required for v1.

**Sync frequency:** On-demand via CLI, plus before each pipeline run.

**Schema (events table):** see §4.

**Interface:**
```python
def sync_calendar(since: datetime, until: datetime) -> int: ...  # returns # events upserted

def find_event_for_recording(
    started_at: datetime, ended_at: datetime
) -> CalendarEvent | None: ...
```

**Match heuristic:** event whose time range overlaps the recording by ≥50% of the recording duration. Ties broken by smallest time delta.

**Acceptance:**
- Sync is idempotent (re-running produces no duplicate rows)
- A recording started during a known event resolves to that event

---

### 3.6 `persister` — single-transaction write to Postgres

**Purpose:** Persist a fully-enriched transcript atomically. **No dual-store writes.**

**Operation:** Open one transaction; insert `recording`, `turns`, `chunks`, `embeddings`. Commit or rollback as a unit. Embeddings are stored in pgvector columns on the same rows — there is no separate vector store to coordinate with.

**Interface:**
```python
def persist_recording(
    audio_path: Path,
    transcript: Transcript,
    speakers: dict[str, ResolvedSpeaker],
    calendar_event: CalendarEvent | None,
    session_meta: SessionMeta,
) -> int:  # returns recording_id
    ...
```

**Idempotency:** `recording.session_uuid` is unique. Re-running the pipeline on the same session updates rather than duplicates (delete-and-reinsert children within the same transaction is acceptable for v1).

**Acceptance:**
- A failure mid-write leaves the database in its prior state (verified by a fault-injection test)
- Re-running the pipeline on the same WAV produces the same row count

---

### 3.7 `summarizer` — local LLM via Ollama

**Purpose:** Generate a meeting-level summary, action items, and topic tags. Stored alongside the transcript, not in place of it.

**Model:** Configurable; default `qwen2.5:14b` or `llama3.3` via Ollama at `http://localhost:11434`.

**Interface:**
```python
def summarize(recording_id: int) -> Summary: ...

@dataclass
class Summary:
    abstract: str       # 3-5 sentences
    action_items: list[str]
    topics: list[str]   # short tags
```

**Acceptance:** Summary is stored on the `recording` row; failures do not block the rest of the pipeline (summary is best-effort).

---

### 3.8 `search` — hybrid query API

**Purpose:** Answer natural-language queries with structured filters + semantic ranking.

**Query decomposition:** A small LLM call (Ollama) extracts structured filters from the natural-language query, then runs hybrid search.

```python
def search(query: str, k: int = 20) -> list[SearchHit]: ...

@dataclass
class StructuredQuery:
    speaker: str | None       # "me" or person name
    attendees: list[str]      # required attendees on the meeting
    date_from: datetime | None
    date_to: datetime | None
    semantic_query: str       # leftover free text for embedding search

@dataclass
class SearchHit:
    recording_id: int
    turn_id: int | None
    chunk_id: int | None
    score: float
    speaker: str
    text: str
    t_start: float
    event_title: str | None
    started_at: datetime
```

**Ranking:** RRF (reciprocal rank fusion) over (a) BM25/Postgres FTS on turn text, (b) pgvector cosine similarity on chunk embeddings, both filtered by structured criteria.

**Acceptance:**
- *"what did I say to Priya last week"* on seeded test data returns only turns where `speaker=me` and the meeting attendees include Priya, within the last 7 days, ranked by semantic relevance to any remaining free-text portion
- Empty structured filters fall back to pure semantic search

---

### 3.9 `tools` — tool registry & MCP layer

**Purpose:** Drop-in capability layer. New tools are added by registering a handler; no core code changes, no restarts of the conversational agent process where possible.

**Design lifted from the Jarvis MCP pattern** — registry-driven, schema-described tools that the planner can discover and invoke.

**Built-in tools (v1):**
- `local_search` — wraps §3.8 `search`. Most queries hit this first.
- `calendar_query` — reads from the local Postgres mirror (§3.5). Filters: time range, attendees, title pattern.
- `enroll_speaker_lookup` — given a name, return person_id and recent recordings featuring them.

**MCP tools (v1):**
- `slack_search` — Slack MCP server, called on demand. No local mirror.
- `gmail_search` — Google MCP server, called on demand. No local mirror.
- `calendar_search` — Google MCP server, used **only by the calendar sync job** (§3.5), not by the planner. The planner uses the local `calendar_query` tool, which is faster and richer (joins to recordings).

**Interface:**
```python
class Tool(Protocol):
    name: str
    description: str
    schema: dict  # JSON schema for arguments

    def __call__(self, **kwargs) -> ToolResult: ...

@dataclass
class ToolResult:
    ok: bool
    data: Any           # serializable
    error: str | None
    citations: list[Citation]  # source IDs for traceability
```

**Acceptance:**
- Adding a new tool requires only: a new file in `tools/`, registration in `tools/__init__.py`, no other changes
- MCP tools are configured in `config.toml`, not code
- Every tool result carries citations the planner can surface to the user

---

### 3.10 `agent` — conversational planner/reasoner

**Purpose:** Single primary agent that owns conversation state and decides which tools to call. This is the layer Jarvis lacked.

**Capabilities:**
- **Query decomposition** — break compound queries ("what's blocking my project across last week's meetings and Slack") into a tool-call sequence.
- **Conversation state** — carry filters across turns ("…and what about with Priya?" inherits prior speaker/date filters).
- **Self-correction** — if a tool returns no results, retry with broadened filters before giving up.
- **Citation tracking** — every claim in the response cites the tool result that backs it.

**Implementation:** Local LLM via Ollama with structured tool-use. Default model `qwen2.5:14b` or whichever supports tool-calling well at the time of build.

**Interface:**
```python
class Agent:
    def __init__(self, tools: list[Tool], model: str): ...

    def chat(self, message: str, session_id: str) -> AgentResponse: ...

@dataclass
class AgentResponse:
    text: str
    citations: list[Citation]
    tool_trace: list[ToolCall]  # for debugging / UI display
```

**Sub-agents:** The primary agent may spawn a sub-agent for bounded heavy reasoning (e.g. summarizing a 90-minute transcript, drafting a final answer from 50+ search hits). Sub-agents have their own context window and return a single result; they do not call tools recursively in v1.

**Acceptance:**
- Compound query *"what's blocking project X across last week's meetings and Slack"* produces a multi-step tool trace and a synthesized answer with citations from both sources
- Follow-up *"…and what about with Priya?"* applies prior filters
- A failing tool call does not crash the agent — it surfaces as a graceful degradation in the response

---

### 3.11 `cli` / `orchestrator`

**Purpose:** Single entry point that wires modules together.

**Commands:**
```
jarvis record --source {mic|system|wav:<path>} [--event-id <id>]
jarvis stop                            # signals an in-progress `record` to finalize
jarvis process <session_uuid>          # re-run pipeline on stored audio
jarvis search "<query>"
jarvis chat                            # interactive REPL against the primary agent (dev)
jarvis enroll <session_uuid> <speaker_raw> <person_name>
jarvis calendar sync
jarvis people list | add | remove
jarvis tray                            # launch the menu-bar / system-tray app
jarvis mcp serve                       # MCP server over stdio (for Claude Desktop etc.)
jarvis mcp print-config                # emit a host-config snippet to paste into the chat host
jarvis setup                           # check Ollama, models, Postgres, mic perms; pull what's missing
```

**Acceptance:** Each command is independently testable; `record` + `process` + `search` covers the end-to-end happy path.

---

### 3.12 `mcp_server` — MCP adapter for chat hosts

**Purpose:** Expose the tool registry (§3.9) over MCP so Claude Desktop / Cursor / ChatGPT Desktop can call Jarvis tools as part of a conversation. This is the *primary* end-user surface for queries; the CLI `jarvis chat` is for dev only.

**Implementation:** Thin wrapper over the `mcp` Python SDK. Subscribes to the existing `tools` registry; every registered tool becomes an MCP tool with the same name, description, and JSON schema. No business logic lives here.

**Transport:** Stdio (the host launches `jarvis mcp serve` as a subprocess). Remote MCP / HTTP transport is out of scope for v1 — Jarvis is a local tool; tunneling its mic and DB to a public endpoint defeats the design.

**Configuration in the host:** the user adds an entry like
```json
{
  "mcpServers": {
    "jarvis": { "command": "jarvis", "args": ["mcp", "serve"] }
  }
}
```
to their host's MCP config. Jarvis ships a `jarvis mcp print-config` command that emits this snippet.

**Acceptance:**
- Every tool in the registry appears in the MCP host's tool list with its description and schema
- Calling a tool from the host produces the same result as calling it via the CLI
- Tool errors propagate as MCP errors, not as crashes of the server process
- `jarvis mcp serve` runs cleanly under stdio without spurious stdout writes (logs go to stderr or a file — stdout is reserved for the MCP protocol)

---

### 3.13 `tray` — recording-control surface

**Purpose:** Give the user a visible, always-accessible way to start/stop a recording without touching the terminal. Especially: a one-click emergency stop while a meeting is in progress.

**Scope (v1):**
- Menu-bar / system-tray icon, color-coded by state (idle = grey, recording = 🔴)
- Menu items: *Start recording*, *Stop recording*, *Open last transcript*, *Quit*
- Cross-platform: macOS, Windows, Linux (single codebase via `pystray` + `Pillow`)
- Talks to the recorder via pidfile + signal — no embedded recorder logic

**Out of scope (v1):**
- Floating overlay windows
- Global keyboard shortcuts (defer; messy across OSes)
- Any search / chat / transcript-browsing UI — that's the chat host's job

**Process model:**
```
[jarvis tray]  ──reads──►  ~/.local/share/jarvis/run/recorder.pid
       │                         ▲
       │  on "Start"             │ written by `jarvis record` on startup
       │  spawns `jarvis record` │
       ▼                         │
[jarvis record subprocess] ──────┘
       │  on "Stop"
       │  receives SIGTERM (Unix) / taskkill (Win)
       ▼
   pipeline finalizes, persists, exits
```

The tray and the recorder are intentionally separate processes so the tray stays responsive even when the recorder is mid-pipeline (Whisper, pyannote, persist) at shutdown.

**Permissions:** First run on macOS triggers Accessibility + Microphone prompts. `jarvis setup` verifies these and points the user at *System Settings → Privacy & Security* if they're missing.

**Acceptance:**
- Icon appears in tray on launch; reflects recorder state within 1s of state change
- Clicking *Stop recording* during a recording results in a clean transcript persisted within 30s
- Force-quitting the tray app does **not** kill an in-progress recording (the recorder is its own process)
- Force-killing the recorder while the tray is running results in the tray icon returning to idle within 5s (pidfile staleness check)

---

## 4. Data model (Postgres)

```sql
-- pgvector extension required
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE people (
    id SERIAL PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT UNIQUE,
    is_self BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE speaker_embeddings (
    id SERIAL PRIMARY KEY,
    person_id INT REFERENCES people(id) ON DELETE CASCADE,
    embedding VECTOR(192) NOT NULL,   -- pyannote ECAPA-TDNN dim
    source_recording_id INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON speaker_embeddings USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    google_event_id TEXT UNIQUE,
    title TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    description TEXT,
    raw_payload JSONB
);

CREATE TABLE event_attendees (
    event_id INT REFERENCES events(id) ON DELETE CASCADE,
    person_id INT REFERENCES people(id) ON DELETE CASCADE,
    response_status TEXT,
    PRIMARY KEY (event_id, person_id)
);

CREATE TABLE recordings (
    id SERIAL PRIMARY KEY,
    session_uuid UUID UNIQUE NOT NULL,
    audio_path TEXT NOT NULL,
    source_label TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    event_id INT REFERENCES events(id),
    summary_abstract TEXT,
    summary_action_items JSONB,
    summary_topics TEXT[],
    summary_embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE turns (
    id SERIAL PRIMARY KEY,
    recording_id INT REFERENCES recordings(id) ON DELETE CASCADE,
    speaker_raw TEXT NOT NULL,        -- "SPEAKER_00"
    person_id INT REFERENCES people(id),  -- resolved identity, nullable
    speaker_confidence REAL,
    needs_review BOOLEAN DEFAULT FALSE,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    text TEXT NOT NULL,
    text_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX ON turns USING GIN (text_tsv);
CREATE INDEX ON turns (recording_id, t_start);
CREATE INDEX ON turns (person_id);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    recording_id INT REFERENCES recordings(id) ON DELETE CASCADE,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    text TEXT NOT NULL,
    speakers INT[],                   -- person_ids participating in this chunk
    embedding VECTOR(768) NOT NULL    -- sentence-transformer or similar
);
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON chunks (recording_id);
```

**Multi-granularity rationale:** turns enable per-speaker queries and FTS; chunks (30–90s rolling windows) enable semantic search with enough context; recording-level summary embeddings enable "find that meeting about X" queries.

---

## 5. Configuration

Single `config.toml` at project root. Env-var overrides (`JARVIS_*`).

```toml
[audio]
source = "mic"               # mic | system | wav:<path>
sample_rate = 16000

[whisper]
model = "large-v3"
device = "mps"               # mps | cuda | cpu
compute_type = "float16"

[diarization]
hf_token_env = "HF_TOKEN"    # for pyannote model download

[speaker_resolver]
threshold_high = 0.75
threshold_low = 0.55

[db]
url_env = "JARVIS_DB_URL"  # postgres://...

[ollama]
host = "http://localhost:11434"
summary_model = "qwen2.5:14b"
query_parse_model = "qwen2.5:7b"

[calendar]
google_oauth_secret_path = "~/.config/jarvis/oauth.json"
sync_window_days = 14
```

---

## 6. Testing strategy

The test harness is the WavFileSource. Every pipeline test runs against checked-in WAV fixtures.

**Fixtures (`tests/fixtures/`):**
- `single_speaker_5min.wav` + ground truth transcript JSON
- `four_speaker_meeting.wav` + ground truth speaker labels + simulated calendar event JSON
- `noisy_meeting.wav` for VAD edge cases

**Test layers:**
1. **Unit** — each module against mocks of its dependencies
2. **Integration** — full pipeline against fixture WAV; assert DB state
3. **Search** — seed DB with known turns; assert query returns correct rows in correct order
4. **Fault injection** — kill the persister mid-transaction; assert no partial state

**CI:** `pytest` runs unit + integration with a Postgres testcontainer. Whisper model is mocked at the unit level and run for real only in a nightly job (it's slow).

---

## 7. Build order & parallelization

Modules are arranged so multiple agents can work in parallel. **Phase boundaries are gates** — do not start phase N+1 until phase N's acceptance criteria are met.

### Phase 0 — foundation (1 agent)
- Repo scaffold, `config.toml`, Postgres schema migrations, testcontainer setup, fixture WAVs committed
- **Gate:** `pytest` runs against an empty schema; fixtures load

### Phase 1 — capture + transcribe (2 agents in parallel)
- **Agent A:** `audio_source` (all three implementations) + `segmenter`
- **Agent B:** `transcriber` (WhisperX wrapper, no diarization yet — single-speaker mode)
- Also in this phase: minimal `tray` (icon + Start/Stop only) and `jarvis stop` CLI command, so the recorder can be controlled without the terminal from day one
- **Gate:** WAV → transcript with word timestamps, no speakers, persisted as `turns` rows with `speaker_raw="SPEAKER_00"`. Tray's *Stop recording* yields the same persisted result as `jarvis stop`.

### Phase 2 — speakers + calendar (2 agents in parallel)
- **Agent C:** Add diarization to `transcriber`; build `speaker_resolver` + enrollment CLI
- **Agent D:** `calendar_sync` + event matching
- **Gate:** Pipeline produces resolved speaker names on the 4-speaker fixture, joined to a fixture calendar event

### Phase 3 — search & summarization (1 agent)
- `summarizer` + `search` (hybrid query, no agent yet — direct CLI)
- **Gate:** *"what did I say to <name> last week"* on seeded data returns correct results via direct hybrid search (no LLM planner)

### Phase 4 — tool registry + primary agent + MCP server (1 agent)
- `tools` registry with `local_search`, `calendar_query`, `enroll_speaker_lookup`
- `agent` primary planner/reasoner with conversation state, query decomposition, self-correction, citations
- `mcp_server` exposing the registry over stdio (§3.12); `jarvis mcp serve` and `jarvis mcp print-config` commands
- **Gate (CLI):** Compound query via `jarvis chat` that requires two local tool calls produces a correct answer with a visible tool trace and citations
- **Gate (MCP):** With Jarvis registered as an MCP server in Claude Desktop (or Cursor), the same compound query asked in the host produces a correct answer using Jarvis tools, with tool call results visible in the host's UI

### Phase 5 — MCP integrations (1 agent)
- `slack_search` and `gmail_search` MCP tools, registered with the agent
- **Gate:** Cross-source query *"what's blocking project X across last week's meetings and Slack"* returns synthesized answer with citations from both Postgres and Slack MCP

### Phase 6 — sub-agents, tray polish, setup (1 agent)
- Sub-agent for meeting summarization (replaces direct `summarizer` call from Phase 3)
- Tray polish: state polling, *Open last transcript*, recovery from stale pidfile, Windows tray-visibility documentation
- `jarvis setup` health check: Ollama daemon, models, Postgres reachability, mic + accessibility permissions on macOS
- End-to-end docs covering: install, `jarvis setup`, register the MCP server in Claude Desktop, run a recording from the tray, query from the host
- **Gate:** Fresh-clone → `make setup && jarvis setup && jarvis record --source wav:fixtures/four_speaker.wav` succeeds; querying the result from a registered chat host (Claude Desktop) returns the expected answer with citations

### Cross-phase rules for agents
- Implement against the interface in §3 first; do not change interfaces without updating this PRD
- Every module ships with its own tests in the same PR
- Postgres schema changes go through migrations, never ad-hoc SQL
- No module reaches across into another module's tables — go through the module's interface

---

## 8. Open questions (resolve before phase 2)

1. **Embedding model for chunks** — `bge-small-en` (384d) vs `nomic-embed-text` (768d) vs `all-mpnet-base-v2` (768d). Pick one and lock the vector dim in the schema before phase 2.
2. **Query parser failure mode** — if Ollama is down, does `search` fall back to pure semantic, or fail loudly? Default proposal: fall back, log warning.
3. **Audio retention** — do we keep raw WAVs forever or delete after N days once transcripts exist? Default proposal: keep, since reprocessing is the recovery path.
4. **Self-identification** — how does the system know which speaker is "me"? Default proposal: pre-enroll the user with 30–60s of reference audio at install time.

---

## 9. Out of scope explicitly

- Real-time/streaming transcription
- **Bespoke chat UI** (web or desktop) — the chat surface is the LLM host (Claude Desktop, Cursor, ChatGPT Desktop) via MCP; Jarvis ships only CLI, MCP server, and a recording-control tray
- HTTP / FastAPI server and remote MCP transport — local stdio only
- Multi-device sync
- Encryption at rest beyond filesystem defaults
- Sharing / export beyond raw SQL access
- Any non-English language support tuning (Whisper handles it; we don't optimize)
