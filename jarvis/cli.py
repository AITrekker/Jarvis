"""CLI entry point. PRD §3.11.

Commands land as their underlying modules are built. Each subcommand is a
thin wrapper around a module function — no business logic here.
"""

from __future__ import annotations

import logging

import click

from . import __version__, _logging


@click.group()
@click.version_option(__version__)
@click.option("--debug", is_flag=True, help="Verbose logging.")
def main(debug: bool) -> None:
    """Jarvis: personal meeting recorder & searchable memory."""
    _logging.configure(level=logging.DEBUG if debug else logging.INFO)


@main.command()
@click.option("--source", default="mic", help="mic | system | wav:<path>")
@click.option("--event-id", default=None, type=int)
def record(source: str, event_id: int | None) -> None:
    """Record audio and run the pipeline."""
    raise click.ClickException("record: not implemented yet (Phase 1)")


@main.command()
@click.argument("session_uuid")
def process(session_uuid: str) -> None:
    """Re-run the pipeline on a stored audio file."""
    raise click.ClickException("process: not implemented yet (Phase 1)")


@main.command("search")
@click.argument("query")
def search_cmd(query: str) -> None:
    """Hybrid search over your meeting memory."""
    raise click.ClickException("search: not implemented yet (Phase 3)")


@main.command()
@click.argument("session_uuid")
@click.argument("speaker_raw")
@click.argument("person_name")
def enroll(session_uuid: str, speaker_raw: str, person_name: str) -> None:
    """Enroll a speaker's voice from an existing recording."""
    raise click.ClickException("enroll: not implemented yet (Phase 2)")


@main.group()
def calendar() -> None:
    """Calendar sync commands."""


@calendar.command("sync")
def calendar_sync() -> None:
    raise click.ClickException("calendar sync: not implemented yet (Phase 2)")


@main.group()
def people() -> None:
    """Manage known people."""


@people.command("list")
def people_list() -> None:
    raise click.ClickException("people list: not implemented yet (Phase 2)")
