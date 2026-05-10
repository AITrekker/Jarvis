"""End-to-end environment setup. Idempotent — safe to re-run.

Two modes:
- `jarvis setup` — check and report; never modifies anything.
- `jarvis setup --fix` — install missing prereqs (brew on macOS, winget on
  Windows), create the local DB, apply the schema, pull required Ollama
  models, write .env with JARVIS_DB_URL.

Anything that requires a UI click (granting macOS mic permission, opening
Postgres.app the first time, downloading Docker Desktop) is reported with a
specific fix hint and left to the user.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION = REPO_ROOT / "migrations" / "0001_init.sql"
ENV_FILE = REPO_ROOT / ".env"

# Default models. Small one is mandatory; large is optional and gated on RAM.
DEFAULT_MODELS_SMALL = ["qwen2.5:7b"]

OK = "✓"  # ✓
FAIL = "✗"  # ✗
WARN = "!"

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    fix_hint: str | None = None
    fixers: list = field(default_factory=list)  # callables that try to remediate


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---- Toolchain checks ----------------------------------------------------


def check_python() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 11)
    return Check(
        f"Python {v.major}.{v.minor}",
        ok,
        sys.executable,
        fix_hint=None if ok else "uv python install 3.12",
    )


def check_uv() -> Check:
    p = _which("uv")
    return Check(
        "uv",
        p is not None,
        p or "not found",
        fix_hint="curl -LsSf https://astral.sh/uv/install.sh | sh",
    )


def check_ffmpeg() -> Check:
    p = _which("ffmpeg")
    if IS_MAC:
        fix, fixers = "brew install ffmpeg", [lambda: _brew_install("ffmpeg")]
    elif IS_WIN:
        fix, fixers = "winget install Gyan.FFmpeg", [lambda: _winget_install("Gyan.FFmpeg")]
    else:
        fix, fixers = "apt install ffmpeg", []
    return Check("ffmpeg", p is not None, p or "not found", fix_hint=fix, fixers=fixers)


def check_psql() -> Check:
    p = _which("psql")
    if IS_MAC:
        hint = "install Postgres.app from https://postgresapp.com (recommended)"
    elif IS_WIN:
        hint = "winget install PostgreSQL.PostgreSQL.16  (then install pgvector via Stack Builder)"
    else:
        hint = "apt install postgresql-16 postgresql-16-pgvector"
    return Check("psql client", p is not None, p or "not found", fix_hint=hint)


# ---- Database checks -----------------------------------------------------


def _default_db_url() -> str:
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "postgres"
    return f"postgresql://{user}@localhost:5432/jarvis"


def check_db_reachable(url: str | None) -> Check:
    if not url:
        return Check(
            "Postgres reachable",
            False,
            "JARVIS_DB_URL not set",
            fix_hint=f"export JARVIS_DB_URL='{_default_db_url()}'",
        )
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return Check("Postgres reachable", True, url)
    except Exception as e:
        msg = str(e).strip().split("\n")[0][:100]
        # Try to give a useful hint.
        hint = "ensure Postgres is running"
        if "does not exist" in str(e):
            hint = f"createdb {url.rsplit('/', 1)[-1]}"
        return Check("Postgres reachable", False, msg, fix_hint=hint)


def check_db_extensions(url: str | None) -> Check:
    if not url:
        return Check("pgvector + pg_trgm", False, "no DB url")
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension")
            exts = {r[0] for r in cur.fetchall()}
        missing = {"vector", "pg_trgm"} - exts
        return Check(
            "pgvector + pg_trgm",
            not missing,
            "ok" if not missing else f"missing: {sorted(missing)}",
            fix_hint=(
                f'psql "{url}" -c "CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;"'
                if missing
                else None
            ),
        )
    except Exception as e:
        return Check("pgvector + pg_trgm", False, str(e)[:100])


def check_db_schema(url: str | None) -> Check:
    if not url:
        return Check("schema applied", False, "no DB url")
    expected = {
        "people",
        "events",
        "recordings",
        "turns",
        "chunks",
        "speaker_embeddings",
        "event_attendees",
    }
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )
            tables = {r[0] for r in cur.fetchall()}
        missing = expected - tables
        return Check(
            "schema applied",
            not missing,
            f"{len(expected & tables)}/{len(expected)} tables",
            fix_hint=f'psql "{url}" -f migrations/0001_init.sql' if missing else None,
        )
    except Exception as e:
        return Check("schema applied", False, str(e)[:100])


# ---- Ollama checks -------------------------------------------------------


def check_ollama() -> Check:
    p = _which("ollama")
    if IS_MAC:
        fix, fixers = "brew install ollama", [lambda: _brew_install("ollama")]
    elif IS_WIN:
        fix, fixers = "winget install Ollama.Ollama", [lambda: _winget_install("Ollama.Ollama")]
    else:
        fix, fixers = "https://ollama.com/download", []
    return Check("Ollama installed", p is not None, p or "not found", fix_hint=fix, fixers=fixers)


def check_ollama_daemon(host: str = "http://localhost:11434") -> Check:
    try:
        import httpx

        r = httpx.get(f"{host}/api/tags", timeout=2.0)
        return Check("Ollama daemon", r.status_code == 200, host)
    except Exception:
        return Check(
            "Ollama daemon", False, "not reachable", fix_hint="run `ollama serve` (or the app)"
        )


def check_ollama_models(host: str = "http://localhost:11434") -> Check:
    try:
        import httpx

        r = httpx.get(f"{host}/api/tags", timeout=2.0)
        names = {m["name"].split(":")[0] for m in r.json().get("models", [])}
        missing = [m for m in DEFAULT_MODELS_SMALL if m.split(":")[0] not in names]
        return Check(
            "Ollama models",
            not missing,
            f"have: {sorted(names) or 'none'}",
            fix_hint=f"ollama pull {missing[0]}" if missing else None,
        )
    except Exception as e:
        return Check("Ollama models", False, str(e)[:100])


# ---- Optional --------------------------------------------------------------


def check_hf_token() -> Check:
    return Check(
        "HF_TOKEN",
        bool(os.environ.get("HF_TOKEN")),
        "set" if os.environ.get("HF_TOKEN") else "not set",
        fix_hint="needed for pyannote diarization (Phase 2). https://huggingface.co/settings/tokens",
    )


# ---- Fixers --------------------------------------------------------------


def _brew_install(pkg: str) -> bool:
    if not _which("brew"):
        click.echo(f"  brew not installed; cannot auto-install {pkg}", err=True)
        return False
    click.echo(f"  brew install {pkg}...")
    return _run(["brew", "install", pkg]).returncode == 0


def _winget_install(pkg_id: str) -> bool:
    if not _which("winget"):
        click.echo(f"  winget not installed; cannot auto-install {pkg_id}", err=True)
        return False
    click.echo(f"  winget install {pkg_id}...")
    return (
        _run(
            [
                "winget",
                "install",
                "--id",
                pkg_id,
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        ).returncode
        == 0
    )


def _ensure_db(url: str) -> bool:
    """Create DB if missing, install extensions, apply schema. Idempotent."""
    import psycopg

    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    server_url = url.rsplit("/", 1)[0] + "/postgres"

    # Create DB if needed.
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.close()
    except psycopg.OperationalError as e:
        if "does not exist" not in str(e):
            click.echo(f"  Postgres unreachable: {e}", err=True)
            return False
        click.echo(f"  creating database {db_name}...")
        try:
            with (
                psycopg.connect(server_url, connect_timeout=3, autocommit=True) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(f'CREATE DATABASE "{db_name}"')
        except Exception as ex:
            click.echo(f"  createdb failed: {ex}", err=True)
            return False

    # Extensions + schema.
    try:
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            # Apply migration only if schema isn't already there.
            cur.execute("SELECT to_regclass('public.recordings')")
            already = cur.fetchone()[0] is not None
            if not already and MIGRATION.exists():
                click.echo("  applying migrations/0001_init.sql...")
                cur.execute(MIGRATION.read_text())
        return True
    except Exception as e:
        click.echo(f"  schema apply failed: {e}", err=True)
        return False


def _ollama_pull(model: str) -> bool:
    if not _which("ollama"):
        return False
    click.echo(f"  ollama pull {model} (this can take several minutes)...")
    return subprocess.run(["ollama", "pull", model]).returncode == 0


def _write_env(url: str) -> None:
    lines = []
    if ENV_FILE.exists():
        lines = [
            ln for ln in ENV_FILE.read_text().splitlines() if not ln.startswith("JARVIS_DB_URL=")
        ]
    lines.append(f"JARVIS_DB_URL={url}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    click.echo(f"  wrote {ENV_FILE.relative_to(REPO_ROOT)}")


# ---- Public entry point --------------------------------------------------


def render(checks: list[Check]) -> bool:
    all_ok = True
    for c in checks:
        sym = OK if c.ok else FAIL
        click.echo(f"  {sym} {c.name:<22} {c.detail}")
        if not c.ok and c.fix_hint:
            click.echo(f"      → {c.fix_hint}")
        if not c.ok:
            all_ok = False
    return all_ok


def run(fix: bool = False) -> int:
    click.echo("\nJarvis setup\n")

    click.echo("Toolchain:")
    tool_checks = [check_python(), check_uv(), check_ffmpeg(), check_psql()]
    if fix:
        for c in tool_checks:
            if not c.ok:
                for fn in c.fixers:
                    fn()
        tool_checks = [check_python(), check_uv(), check_ffmpeg(), check_psql()]
    render(tool_checks)

    # Auto-pick a DB URL if none set.
    db_url = os.environ.get("JARVIS_DB_URL") or _default_db_url()

    click.echo("\nDatabase:")
    db_checks = [check_db_reachable(db_url), check_db_extensions(db_url), check_db_schema(db_url)]
    if fix and not all(c.ok for c in db_checks) and _ensure_db(db_url):
        _write_env(db_url)
        db_checks = [
            check_db_reachable(db_url),
            check_db_extensions(db_url),
            check_db_schema(db_url),
        ]
    render(db_checks)

    click.echo("\nOllama:")
    o_checks = [check_ollama(), check_ollama_daemon(), check_ollama_models()]
    if fix:
        if not o_checks[0].ok:
            for fn in o_checks[0].fixers:
                fn()
            o_checks = [check_ollama(), check_ollama_daemon(), check_ollama_models()]
        if o_checks[1].ok and not o_checks[2].ok:
            for m in DEFAULT_MODELS_SMALL:
                _ollama_pull(m)
            o_checks[2] = check_ollama_models()
    render(o_checks)

    click.echo("\nOptional:")
    render([check_hf_token()])

    all_ok = all(c.ok for c in tool_checks + db_checks + o_checks)
    click.echo()
    if all_ok:
        click.echo(f"  {OK} ready. Try: uv run jarvis --help")
    else:
        click.echo(
            f"  {WARN} some checks failed. Re-run with `--fix` to auto-remediate where possible."
        )
    return 0 if all_ok else 1
