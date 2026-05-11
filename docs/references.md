# External references

OSS repos worth studying or borrowing from as Jarvis is built. Curated 2026-05-11.
None of these are dependencies — they are reference material. Read before reaching
for a blank file in the relevant phase.

## Closest analog (study before Phase 2)

- **Zackriya-Solutions/meetily** — https://github.com/Zackriya-Solutions/meetily
  Local meeting note-taker (Mac+Win), Whisper + diarization + Ollama summary, Rust+Tauri.
  Different stack, but the surface choices overlap heavily. Study VAD chunking,
  system-audio capture on Win/Mac, and stop/start UX.

## WhisperX wrapper references (Phase 1 — `transcriber.py`)

- **pavelzbornik/whisperX-FastAPI** — https://github.com/pavelzbornik/whisperX-FastAPI
- **Nyralei/whisperx-api-server** — https://github.com/Nyralei/whisperx-api-server

  Both clean, maintained 2026. Borrow argument shapes and model-lifecycle handling
  (load once, reuse). Skip the FastAPI layer — Jarvis doesn't have one.

## Calendar (Phase 2 — `calendar_sync.py`)

- **kuzmoyev/google-calendar-simple-api (gcsa)** — https://github.com/kuzmoyev/google-calendar-simple-api
  Pythonic wrapper over Google Calendar API. Use as the client. Write the
  syncToken/upsert layer ourselves (~50 lines).

## Hybrid search (Phase 3 — `search.py`)

No canonical repo. Patterns to crib:

- Supabase hybrid-search guide (RRF over `tsvector` + `vector` in pure SQL)
- `pgvector/pgvector` examples folder — hybrid-search SQL example

  Verdict: write our own RRF in SQL, ~20 lines. Do **not** add ParadeDB or
  another extension — single-store simplicity is a hard rule.

## MCP server tool-surface conventions (Phase 4 — `mcp_server.py`)

- **cyanheads/obsidian-mcp-server** — https://github.com/cyanheads/obsidian-mcp-server
  Clean stdio MCP with split search / read / structured-filter tools. Mirror this
  shape for `search_meetings` / `get_turn` / `find_speaker`.
- **lharries/whatsapp-mcp** — https://github.com/lharries/whatsapp-mcp
  Local SQLite + MCP exposing personal chat search. Same tool surface we want.

## Ollama tool-call loop (Phase 4 — `agent.py`)

- **jonigl/mcp-client-for-ollama** — https://github.com/jonigl/mcp-client-for-ollama
  Borrow the model → tool → model loop. Ollama's OpenAI-compatible tool-calling
  has sharp edges and most projects get this wrong. Skip the TUI.

## Categories with no good prior art (just build it)

- Speaker diarization + enrollment beyond raw pyannote — nothing exists. Our
  "calendar attendees as a prior" trick is novel.
- Calendar ↔ Postgres mirror — no mature lib worth depending on.
- pystray + pidfile recorder control — pystray examples don't cover this; we
  already have `_proc.py`.

## Rejected (do not borrow)

The four browser-side repos surveyed 2026-05-11 (davidbmar/Browser-Text-to-Speech-TTS-Realtime,
browser-llm-local-ai-chat, browser-whisper-models-local-showcase,
browser-Speech-to-Text-realtime-ASR) are short-utterance browser demos with no
diarization, no durable storage, and one of them (the "ASR" repo) calls Google
servers via Web Speech API — incompatible with the no-cloud rule. Skip all four.
