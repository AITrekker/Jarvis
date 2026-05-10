# One-shot bootstrap for Windows (PowerShell). Idempotent — safe to re-run.
# Usage:
#   .\bootstrap.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

Step "1/5 Check uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Step "Installing uv"
    irm https://astral.sh/uv/install.ps1 | iex
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "uv did not land on PATH. Open a new PowerShell and re-run."
    }
}

Step "2/5 Sync Python deps"
uv sync --extra dev

Step "3/5 Run setup checks (auto-fix where possible)"
uv run jarvis setup --fix

Step "4/5 Re-check"
uv run jarvis setup

Step "5/5 Smoke check"
uv run jarvis --help | Out-Null
uv run nox -s test_unit

Write-Host @"

Bootstrap complete. Next:
  - If `jarvis setup` showed any ✗, follow the → fix hint and re-run.
  - Try: uv run jarvis --help

"@
