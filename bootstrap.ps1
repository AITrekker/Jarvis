# One-shot bootstrap for Windows (PowerShell). Idempotent — safe to re-run.
# Usage: .\bootstrap.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "✓ $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "! $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "✗ $msg" -ForegroundColor Red }

Step "1/4 Install uv (if missing)"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    irm https://astral.sh/uv/install.ps1 | iex
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "uv did not land on PATH. Open a new PowerShell and re-run."
        exit 1
    }
}
Ok "uv: $((Get-Command uv).Source)"

Step "2/4 Sync Python deps"
uv sync --extra dev --quiet
Ok "deps synced"

Step "3/4 Setup checks (auto-fix where possible)"
uv run jarvis setup --fix
$setupExit = $LASTEXITCODE

Step "4/4 Smoke check"
uv run nox -s test_unit

Write-Host ""
if ($setupExit -eq 0) {
    Ok "Bootstrap complete. Everything is ready."
    Write-Host "  Try: uv run jarvis --help"
} else {
    Warn "Bootstrap finished, but some checks above are still failing."
    Write-Host "  Follow the -> fix hints above, then re-run .\bootstrap.ps1."
    Write-Host "  Common cases:"
    Write-Host "    - Postgres needs to be installed and the service started"
    Write-Host "    - pgvector needs to be installed via Stack Builder"
    Write-Host "    - Ollama needs to be running"
}
exit $setupExit
