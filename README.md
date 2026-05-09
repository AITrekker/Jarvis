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

Jarvis runs identically on macOS and Windows (and Linux). The Python code is portable; only the install commands differ. CI exercises `ubuntu-latest`, `macos-latest`, and `windows-latest` on every push.

### Prerequisites (both OSes)

- **Python 3.12** — `uv` will install it for you if missing
- **`uv`** — `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or `winget install astral-sh.uv` (Windows)
- **Postgres 16 + pgvector** — pick one path below
- **Ollama** — `brew install ollama` (Mac) or download from [ollama.com](https://ollama.com) (Windows)
- **ffmpeg** — `brew install ffmpeg` (Mac) or `winget install ffmpeg` (Windows)

### Postgres — pick one

| Path | Mac | Windows | Notes |
|---|---|---|---|
| **Docker Desktop** | ✓ | ✓ | One command on both: `make db.up` (or `docker compose up -d db`). Best if you already have Docker. |
| **Postgres.app** | ✓ | ✗ | Click installer, ships with pgvector, no daemon to babysit. Best on Mac if you don't want Docker. |
| **EDB installer** | ✓ | ✓ | [enterprisedb.com/downloads](https://www.enterprisedb.com/downloads). Add pgvector via Stack Builder. Best on Windows if you don't want Docker. |
| **brew** | ✓ | ✗ | `brew install postgresql@16 pgvector && brew services start postgresql@16` |

After install, in any path:
```bash
createdb jarvis
psql jarvis -c "CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;"
psql jarvis -f migrations/0001_init.sql
export JARVIS_DB_URL="postgresql://$USER@localhost:5432/jarvis"   # adjust per your install
```

### Setup + smoke check

**macOS / Linux:**
```bash
git clone https://github.com/AITrekker/Jarvis && cd Jarvis
uv sync --extra dev
uv run jarvis --help
make test.unit
```

**Windows (PowerShell or Git Bash):**
```powershell
git clone https://github.com/AITrekker/Jarvis
cd Jarvis
uv sync --extra dev
uv run jarvis --help
uv run nox -s test_unit
```

Windows note: `make` is not installed by default. Use `uv run nox -s <task>` directly, or install `winget install GnuWin32.Make` to use the Makefile shim. The `noxfile.py` is the canonical task list — see `uv run nox --list`.

## Development

Tasks (run on either OS via `uv run nox -s <name>`):

| Task | What it does |
|---|---|
| `lint` | ruff check + format check |
| `fmt` | ruff fix + format |
| `test_unit` | unit tests, no Docker needed |
| `test_integration` | integration tests, requires Docker (testcontainers spins up its own pgvector) |
| `test` | unit + integration |
| `smoke` | CLI smoke check |

Mac/Linux convenience: `make lint` / `make test.unit` / etc. delegate to nox.

## Running on both Mac and Windows

The recording pipeline (microphone, Whisper, pyannote) is the part with the most platform-specific friction — first-time install of `whisperx` + CUDA wheels on Windows, BlackHole vs WASAPI loopback for system audio. Designate one machine as your **recording host** and put the heavy ML extras (`uv sync --extra ml --extra audio`) there. Any other machine can be a **query host** with just `uv sync --extra dev` and a connection string pointed at the same Postgres — the single-store design means search, agent, and MCP server work from anywhere with DB access.

User memory (recordings, transcripts) is **not** designed to be portable across stacks. Code and instances are.

## Documentation

- [`PRD.md`](./PRD.md) — full design spec; the source of truth for the rebuild
- [`docs/v1-reference/`](./docs/v1-reference/) — frozen v1 setup/start scripts kept for the cross-platform patterns they encode (venv detection, banner, MCP subprocess lifecycle). Do not import from this directory.

## License

Personal project; no license declared yet.
