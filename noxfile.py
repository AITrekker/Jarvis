"""Cross-platform task runner. Works identically on macOS, Linux, Windows.

Run a task:
    uv run nox -s <task>          # or: nox -s <task> if nox is on PATH
List tasks:
    uv run nox --list

Tasks here mirror what the Makefile used to do but run natively on Windows
(where `make` is not installed by default).
"""

from __future__ import annotations

import nox

nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ["lint", "test_unit"]


@nox.session
def lint(session: nox.Session) -> None:
    """Ruff check + format check."""
    session.install("-e", ".[dev,tray]")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session
def fmt(session: nox.Session) -> None:
    """Auto-format and auto-fix lints."""
    session.install("-e", ".[dev,tray]")
    session.run("ruff", "check", "--fix", ".")
    session.run("ruff", "format", ".")


@nox.session(name="test")
def test_all(session: nox.Session) -> None:
    """Unit + integration tests. Integration needs Docker."""
    session.install("-e", ".[dev,tray,audio,ml]")
    session.run("pytest")


@nox.session(name="test_unit")
def test_unit(session: nox.Session) -> None:
    """Fast unit tests, no Docker needed."""
    session.install("-e", ".[dev,tray,audio,ml]")
    session.run("pytest", "-m", "not integration and not ml")


@nox.session(name="test_integration")
def test_integration(session: nox.Session) -> None:
    """Integration tests against a pgvector testcontainer (requires Docker)."""
    session.install("-e", ".[dev,tray,audio,ml]")
    session.run("pytest", "-m", "integration")


@nox.session
def smoke(session: nox.Session) -> None:
    """Quick CLI smoke check: --help and --version respond."""
    session.install("-e", ".[dev]")
    session.run("jarvis", "--help")
    session.run("jarvis", "--version")
