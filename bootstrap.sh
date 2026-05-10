#!/usr/bin/env bash
# One-shot bootstrap for macOS / Linux. Idempotent — safe to re-run.
# On Windows, use bootstrap.ps1.

set -uo pipefail
cd "$(dirname "$0")"

step() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; }

step "1/4 Install uv (if missing)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1090
  source "$HOME/.local/bin/env" 2>/dev/null || true
  if ! command -v uv >/dev/null 2>&1; then
    fail "uv install did not land on PATH. Open a new shell and re-run."
    exit 1
  fi
fi
ok "uv: $(command -v uv)"

step "2/4 Sync Python deps"
uv sync --extra dev --quiet
ok "deps synced"

step "3/4 Setup checks (auto-fix where possible)"
uv run jarvis setup --fix
SETUP_EXIT=$?

step "4/4 Smoke check"
uv run nox -s test_unit

echo
if [ "$SETUP_EXIT" -eq 0 ]; then
  ok "Bootstrap complete. Everything is ready."
  echo "  Try: uv run jarvis --help"
else
  warn "Bootstrap finished, but some checks above are still failing."
  echo "  Follow the → fix hints above, then re-run ./bootstrap.sh."
  echo "  Common cases:"
  echo "    • Postgres.app needs to be opened once and click 'Initialize' / 'Start'"
  echo "    • Ollama app needs to be opened once so its daemon is running"
  echo "    • macOS will prompt for mic permission the first time you record"
fi
exit "$SETUP_EXIT"
