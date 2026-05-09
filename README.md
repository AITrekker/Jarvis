    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║         ██╗  █████╗  ██████╗  ██╗   ██╗ ██╗ ███████╗       ║
    ║         ██║ ██╔══██╗ ██╔══██╗ ██║   ██║ ██║ ██╔════╝       ║
    ║         ██║ ███████║ ██████╔╝ ██║   ██║ ██║ ███████╗       ║
    ║         ██║ ██╔══██║ ██╔══██╗ ╚██╗ ██╔╝ ██║ ╚════██║       ║
    ║      █████║ ██║  ██║ ██║  ██║  ╚████╔╝  ██║ ███████║       ║
    ║      ╚════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝   ╚═══╝   ╚═╝ ╚══════╝       ║
    ║                                                            ║
    ║   Your AI assistant that listens, remembers, and recalls   ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝

# Jarvis — personal meeting recorder & searchable memory

Records meetings locally, transcribes them with speaker labels, joins them to your calendar, and lets you ask questions like *"what did I say to Priya last week?"*. Everything runs on your machine — no cloud LLMs, no cloud storage.

This is a rebuild. The previous version (preserved at tag [`v1-2025`](https://github.com/AITrekker/Jarvis/releases/tag/v1-2025)) shipped real-time transcription and a Gradio UI but failed in four specific ways: unreliable speaker identification, no calendar context, dual-store consistency bugs between the metadata DB and the vector DB, and only summaries (not turn-level transcripts) were searchable. The full design that addresses each of these is in [`PRD.md`](./PRD.md).

## Status

🚧 **Pre-alpha — Phase 0 scaffolding.** No working pipeline yet. See `PRD.md` §7 for the build plan.

## Architecture in one paragraph

A single Python process. Audio is captured by a configurable source (mic, system audio, or WAV file), segmented by VAD, transcribed by **WhisperX** with **pyannote** diarization, and resolved against a stored voice-embedding enrollment table. Calendar events from **Google Calendar** are mirrored locally and joined to recordings by time overlap; the attendee count feeds back as a hint to diarization. Everything — transcripts, embeddings, summaries, calendar events — lives in **one Postgres database with pgvector**, written in a single transaction. Search is hybrid: Postgres full-text search + pgvector cosine similarity + structured filters, fused with reciprocal rank. A primary agent (local LLM via **Ollama**) sits in front of a tool registry; MCP servers (Slack, Gmail) plug in as additional tools.

## Stack

- **Audio capture**: `sounddevice` / PortAudio
- **VAD + segmentation**: Silero VAD
- **Transcription + diarization**: WhisperX (faster-whisper backend) + pyannote.audio
- **Storage**: Postgres + pgvector + pg_trgm (single store, no separate vector DB)
- **LLMs**: Ollama, locally (`qwen2.5:14b` default for summarization and the agent)
- **Calendar**: Google Calendar API (OAuth, refresh token in macOS Keychain)
- **Test harness**: WAV fixtures + Postgres testcontainer

## Getting started

```bash
# requirements: uv, ffmpeg, Postgres 16 with pgvector, Ollama
uv sync
make db.up        # boots local Postgres + pgvector via docker
make migrate
jarvis --help
```

Detailed setup will land as Phase 0 completes.

## Development

```bash
make test         # unit + integration (testcontainers Postgres)
make lint
make migrate.new name=<short-description>
```

## Documentation

- [`PRD.md`](./PRD.md) — full design spec; the source of truth for the rebuild
- [`docs/v1-reference/`](./docs/v1-reference/) — frozen v1 setup/start scripts kept for the cross-platform patterns they encode (venv detection, banner, MCP subprocess lifecycle). Do not import from this directory.

## License

Personal project; no license declared yet.
