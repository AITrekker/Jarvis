#!/usr/bin/env bash
# Pre-flight check before launching the Phase 1 overnight build.
# Prints ✓/✗ for each gate. Exits 0 only if everything is green.
#
# Usage:
#   ./scripts/preflight_phase1.sh

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

ok=true
say()  { printf "  ✓ %s\n" "$1"; }
fail() { printf "  ✗ %s\n" "$1"; ok=false; }

echo "Phase 1 pre-flight"
echo "------------------"

# 1. On main, clean working tree (warnings tolerable; failure intolerable)
branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" == "main" ]]; then
  say "on branch main"
else
  fail "expected branch 'main', got '$branch'"
fi

# 2. Locked interface files exist
for f in jarvis/types.py jarvis/audio_source.py jarvis/segmenter.py \
         jarvis/transcriber.py jarvis/persister.py jarvis/recorder.py; do
  [[ -f "$f" ]] && say "interface stub $f present" || fail "missing $f"
done

# 3. Fixture present
if [[ -f tests/fixtures/synthetic_5s.wav && -f tests/fixtures/synthetic_5s.json ]]; then
  say "synthetic fixture committed"
else
  fail "synthetic fixture missing — run scripts/gen_synthetic_fixture.py"
fi

# 4. tiny.en model cached
if [[ -d "$HOME/.cache/huggingface/hub/models--Systran--faster-whisper-tiny.en" ]]; then
  say "faster-whisper tiny.en cached"
else
  fail "tiny.en not cached — pre-download before overnight run"
fi

# 5. Docker reachable (testcontainers needs it)
if docker info >/dev/null 2>&1; then
  say "Docker daemon reachable"
else
  fail "Docker daemon not reachable — start Docker Desktop"
fi

# 6. Baseline unit tests green (skip schema test which needs Docker)
if uv run pytest -q --ignore=tests/test_schema.py >/tmp/preflight-pytest.log 2>&1; then
  say "baseline pytest passes ($(grep -oE '[0-9]+ passed' /tmp/preflight-pytest.log | head -1))"
else
  fail "baseline pytest failed — see /tmp/preflight-pytest.log"
fi

# 7. Postgres reachable for direct migration verification (optional)
if [[ -n "${JARVIS_DB_URL:-}" ]] && command -v psql >/dev/null 2>&1; then
  if psql "$JARVIS_DB_URL" -tAc 'SELECT 1' >/dev/null 2>&1; then
    say "Postgres reachable at JARVIS_DB_URL"
  else
    fail "JARVIS_DB_URL set but psql cannot connect"
  fi
else
  printf "  - Postgres direct check skipped (testcontainer will provide its own)\n"
fi

echo "------------------"
if $ok; then
  echo "READY. Owner: say 'go' to launch the overnight run."
  exit 0
else
  echo "NOT READY. Fix the ✗ items above before launching."
  exit 1
fi
