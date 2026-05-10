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

        # Silence psycopg's chatty multi-host error before we render our own.
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return Check("Postgres reachable", True, url)
    except Exception as e:
        s = str(e)
        if "does not exist" in s:
            db_name = url.rsplit("/", 1)[-1].split("?")[0]
            return Check(
                "Postgres reachable",
                False,
                f"database '{db_name}' does not exist",
                fix_hint=f"createdb {db_name}  (or re-run with --fix)",
            )
        if "Connection refused" in s or "could not connect" in s:
            hint = (
                "open Postgres.app and click Start (or `open -a Postgres`)"
                if IS_MAC
                else "start the Postgres service"
            )
            return Check(
                "Postgres reachable",
                False,
                "server not running on localhost:5432",
                fix_hint=hint,
                fixers=[_start_postgres_app] if IS_MAC else [],
            )
        msg = s.strip().split("\n")[0][:80]
        return Check("Postgres reachable", False, msg, fix_hint="check Postgres status")


def check_db_extensions(url: str | None, *, skip: bool = False) -> Check:
    if skip:
        return Check("pgvector + pg_trgm", False, "(skipped — Postgres not reachable)")
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


def check_db_schema(url: str | None, *, skip: bool = False) -> Check:
    if skip:
        return Check("schema applied", False, "(skipped — Postgres not reachable)")
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
        # Cask installs the menu-bar app (which boots the daemon on launch).
        # The plain `brew install ollama` formula gives you only the CLI, which
        # means you have to run `ollama serve` in a separate terminal forever.
        fix = "brew install --cask ollama"
        fixers = [lambda: _brew_install_cask("ollama")]
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
        hint = (
            "`open -a Ollama` (or `ollama serve` in another terminal)" if IS_MAC else "start Ollama"
        )
        return Check(
            "Ollama daemon",
            False,
            "not running on localhost:11434",
            fix_hint=hint,
            fixers=[_start_ollama] if IS_MAC else [],
        )


def check_ollama_models(host: str = "http://localhost:11434", *, skip: bool = False) -> Check:
    if skip:
        return Check("Ollama models", False, "(skipped — daemon not running)")
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


def _brew_install_cask(pkg: str) -> bool:
    if not _which("brew"):
        click.echo(f"  brew not installed; cannot auto-install --cask {pkg}", err=True)
        return False
    click.echo(f"  brew install --cask {pkg}...")
    return _run(["brew", "install", "--cask", pkg]).returncode == 0


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


def _start_postgres_app() -> bool:
    """Open Postgres.app on macOS. The app auto-starts the configured server."""
    if not IS_MAC:
        return False
    if not Path("/Applications/Postgres.app").exists():
        click.echo("  Postgres.app not installed at /Applications/Postgres.app", err=True)
        return False
    click.echo("  starting Postgres.app...")
    _run(["open", "-a", "Postgres"])
    # Give it a few seconds to bind the port.
    import time

    for _ in range(10):
        time.sleep(0.5)
        try:
            import psycopg

            with psycopg.connect(
                _default_db_url().rsplit("/", 1)[0] + "/postgres", connect_timeout=1
            ):
                return True
        except Exception:
            continue
    return False


def _start_ollama() -> bool:
    """Start the Ollama daemon. Tries the menu-bar app first, then `ollama serve`."""
    if not IS_MAC:
        return False
    click.echo("  starting Ollama...")
    # Try the cask app first; if not installed, fall back to spawning the CLI.
    app_started = _run(["open", "-a", "Ollama"]).returncode == 0
    if not app_started:
        if not _which("ollama"):
            return False
        click.echo("  Ollama app not found; spawning `ollama serve` in the background...")
        # Fully detach so it survives this Python process exiting.
        log_path = _paths_runtime_dir() / "ollama.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as logf:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=logf,
                stderr=logf,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
    import time

    for _ in range(20):  # up to 10s — daemon cold-start can be slow
        time.sleep(0.5)
        try:
            import httpx

            if httpx.get("http://localhost:11434/api/tags", timeout=1.0).status_code == 200:
                return True
        except Exception:
            continue
    return False


def _paths_runtime_dir() -> Path:
    from . import _paths

    return _paths.runtime_dir()


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
            # Don't dump the multi-line psycopg error here; the check above
            # already rendered a clean one-line message.
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


def render(checks: list[Check]) -> None:
    for c in checks:
        sym = click.style(OK, fg="green") if c.ok else click.style(FAIL, fg="red")
        click.echo(f"  {sym} {c.name:<22} {c.detail}")
        if not c.ok and c.fix_hint:
            click.echo(f"      → {c.fix_hint}")


def _run_fixers_for(checks: list[Check]) -> None:
    for c in checks:
        if c.ok:
            continue
        for fn in c.fixers:
            try:
                fn()
            except Exception as e:
                click.echo(f"  fixer failed: {e}", err=True)


def _collect_toolchain() -> list[Check]:
    return [check_python(), check_uv(), check_ffmpeg(), check_psql()]


def _collect_db(url: str) -> list[Check]:
    reach = check_db_reachable(url)
    # If the server isn't reachable, skip the dependent checks rather than
    # repeating the same long connection error three times.
    return [
        reach,
        check_db_extensions(url, skip=not reach.ok),
        check_db_schema(url, skip=not reach.ok),
    ]


def _collect_ollama() -> list[Check]:
    installed = check_ollama()
    daemon = (
        check_ollama_daemon()
        if installed.ok
        else Check("Ollama daemon", False, "(skipped — Ollama not installed)")
    )
    models = check_ollama_models(skip=not daemon.ok)
    return [installed, daemon, models]


def run(fix: bool = False) -> int:
    click.echo()
    click.secho("Jarvis setup", bold=True)
    click.echo()

    db_url = os.environ.get("JARVIS_DB_URL") or _default_db_url()

    # ---- 1. Toolchain (install missing CLIs) ----
    tool = _collect_toolchain()
    if fix:
        _run_fixers_for(tool)
        tool = _collect_toolchain()

    # ---- 2. Database (start server, then create db + extensions + schema) ----
    db = _collect_db(db_url)
    if fix:
        _run_fixers_for(db)  # may start Postgres.app on Mac
        db = _collect_db(db_url)
        if not all(c.ok for c in db) and _ensure_db(db_url):
            _write_env(db_url)
            db = _collect_db(db_url)

    # ---- 3. Ollama (start daemon, then pull models) ----
    o = _collect_ollama()
    if fix:
        if not o[0].ok:  # binary missing
            _run_fixers_for([o[0]])
            o = _collect_ollama()
        if o[0].ok and not o[1].ok:  # binary present but daemon down
            _run_fixers_for([o[1]])
            o = _collect_ollama()
        if o[1].ok and not o[2].ok:  # daemon up, models missing
            for m in DEFAULT_MODELS_SMALL:
                _ollama_pull(m)
            o = _collect_ollama()

    optional = [check_hf_token()]

    # ---- Render ----
    click.secho("Toolchain:", bold=True)
    render(tool)
    click.echo()
    click.secho("Database:", bold=True)
    render(db)
    click.echo()
    click.secho("Ollama:", bold=True)
    render(o)
    click.echo()
    click.secho("Optional:", bold=True)
    render(optional)

    required = tool + db + o
    # A check is "actionable" if it failed AND it's not just cascading from an
    # upstream failure. Skipped checks have a "(skipped" prefix in detail.
    actionable = [c for c in required if not c.ok and not c.detail.startswith("(skipped")]

    click.echo()
    if not actionable and all(c.ok for c in required):
        click.secho(
            f"  {OK} all required checks pass. Try: uv run jarvis --help", fg="green", bold=True
        )
        return 0

    click.secho(f"  {FAIL} {len(actionable)} thing(s) to fix:", fg="red", bold=True)
    for c in actionable:
        click.echo(f"      • {c.name}: {c.detail}")
        if c.fix_hint:
            click.echo(f"        → {c.fix_hint}")
    skipped = [c for c in required if c.detail.startswith("(skipped")]
    if skipped:
        click.echo()
        click.echo(f"  ({len(skipped)} dependent check(s) skipped — fix the items above first.)")
    if not fix:
        click.echo()
        click.echo("  Try: uv run jarvis setup --fix")
    return 1
