#!/usr/bin/env bash
# Pre-flight check before launching the Phase 2 overnight build.
# Prints ✓/✗ for each gate. Exits 0 only if everything is green.
#
# Usage:
#   ./scripts/preflight_phase2.sh

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

ok=true
say()  { printf "  ✓ %s\n" "$1"; }
fail() { printf "  ✗ %s\n" "$1"; ok=false; }
note() { printf "  - %s\n" "$1"; }

echo "Phase 2 pre-flight"
echo "------------------"

# 1. On main with phase1 tag present
branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" == "main" ]]; then
  say "on branch main"
else
  fail "expected branch 'main', got '$branch'"
fi
if git rev-parse phase1 >/dev/null 2>&1; then
  say "phase1 tag present"
else
  fail "phase1 tag missing — Phase 1 should be merged + tagged before Phase 2"
fi

# 2. Locked interface files exist (Phase 1 + Phase 2 stubs)
for f in jarvis/types.py jarvis/transcriber.py jarvis/speaker_resolver.py \
         jarvis/calendar_sync.py jarvis/recorder.py jarvis/cli.py; do
  [[ -f "$f" ]] && say "interface file $f present" || fail "missing $f"
done

# 3. Phase 2 stubs raise NotImplementedError (don't silently pass)
if grep -q "NotImplementedError" jarvis/speaker_resolver.py && \
   grep -q "NotImplementedError" jarvis/calendar_sync.py; then
  say "Phase 2 stubs raise NotImplementedError"
else
  fail "Phase 2 stubs should raise NotImplementedError until agents fill them in"
fi

# 4. .env contains HF_TOKEN (pyannote diarization needs it)
if [[ -f .env ]] && grep -q "^HF_TOKEN=hf_" .env; then
  say "HF_TOKEN present in .env"
else
  fail "HF_TOKEN missing — Agent C cannot run diarization without it"
fi

# 5. Pyannote model cached locally
PYANNOTE_CACHE="$HOME/.cache/huggingface/hub/models--pyannote--speaker-diarization-3.1"
if [[ -d "$PYANNOTE_CACHE" ]]; then
  say "pyannote/speaker-diarization-3.1 cached"
else
  fail "pyannote weights not cached — pre-download before overnight run"
fi

# 6. tiny.en model cached (transcriber tests still use it)
if [[ -d "$HOME/.cache/huggingface/hub/models--Systran--faster-whisper-tiny.en" ]]; then
  say "faster-whisper tiny.en cached"
else
  fail "tiny.en not cached — pre-download before overnight run"
fi

# 7. 4-speaker fixture (optional — finalizer falls back to TTS)
if [[ -f tests/fixtures/local/four_speaker.wav ]]; then
  say "4-speaker fixture present"
else
  note "4-speaker fixture absent — agents will use TTS fallback (structural only)"
fi

# 8. Docker reachable (testcontainers needs it)
if docker info >/dev/null 2>&1; then
  say "Docker daemon reachable"
else
  fail "Docker daemon not reachable — start Docker Desktop"
fi

# 9. Baseline unit + integration tests green
if uv run pytest -q -m "not integration and not ml" >/tmp/preflight2-unit.log 2>&1; then
  say "baseline unit tests pass ($(grep -oE '[0-9]+ passed' /tmp/preflight2-unit.log | head -1))"
else
  fail "baseline unit tests failed — see /tmp/preflight2-unit.log"
fi
if uv run pytest -q -m integration >/tmp/preflight2-int.log 2>&1; then
  say "baseline integration tests pass ($(grep -oE '[0-9]+ passed' /tmp/preflight2-int.log | head -1))"
else
  fail "baseline integration tests failed — see /tmp/preflight2-int.log"
fi

# 10. Postgres reachable (optional; testcontainer covers automated runs)
if [[ -n "${JARVIS_DB_URL:-}" ]] && command -v psql >/dev/null 2>&1; then
  if psql "$JARVIS_DB_URL" -tAc 'SELECT 1' >/dev/null 2>&1; then
    say "Postgres reachable at JARVIS_DB_URL"
  else
    note "JARVIS_DB_URL set but psql cannot connect (testcontainer will provide its own)"
  fi
else
  note "Postgres direct check skipped (testcontainer will provide its own)"
fi

echo "------------------"
if $ok; then
  echo "READY. Owner: say 'go' to launch the overnight run."
  exit 0
else
  echo "NOT READY. Fix the ✗ items above before launching."
  exit 1
fi
