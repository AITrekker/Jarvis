#!/usr/bin/env bash
# One-shot bootstrap for macOS / Linux. Idempotent — safe to re-run.
# On Windows, use bootstrap.ps1.

set -euo pipefail

cd "$(dirname "$0")"

step() { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

step "1/5 Check uv"
if ! command -v uv >/dev/null 2>&1; then
  step "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1090
  source "$HOME/.local/bin/env" 2>/dev/null || true
  command -v uv >/dev/null 2>&1 || fail "uv install did not land on PATH; open a new shell and re-run."
fi

step "2/5 Sync Python deps"
uv sync --extra dev

step "3/5 Run setup checks (auto-fix where possible)"
# This handles ffmpeg, psql client, Postgres DB + extensions + schema, Ollama, models.
# Anything that needs a UI click (Postgres.app first launch, mic permission) is reported
# as a fix hint, not silently skipped.
uv run jarvis setup --fix || true

step "4/5 Re-check (no fix) so you can see the final state"
uv run jarvis setup || true

step "5/5 Smoke check"
uv run jarvis --help >/dev/null
uv run nox -s test_unit

cat <<'EOF'

Bootstrap complete. Next:
  - If `jarvis setup` showed any ✗, follow the → fix hint and re-run.
  - Reload your shell so JARVIS_DB_URL (written to .env) is picked up:
      source .env  (or open a new terminal — uv loads .env automatically inside `uv run`)
  - Try: uv run jarvis --help

EOF
