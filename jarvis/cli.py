"""CLI entry point. PRD §3.11.

Commands land as their underlying modules are built. Each subcommand is a
thin wrapper around a module function — no business logic here.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import click

from . import __version__, _logging, _paths, _proc


@click.group()
@click.version_option(__version__)
@click.option("--debug", is_flag=True, help="Verbose logging.")
def main(debug: bool) -> None:
    """Jarvis: personal meeting recorder & searchable memory."""
    _logging.configure(level=logging.DEBUG if debug else logging.INFO)


@main.command()
@click.option("--fix", is_flag=True, help="Try to install missing prereqs and create the DB.")
def setup(fix: bool) -> None:
    """Check (and optionally install) all prerequisites for Jarvis."""
    from . import setup as _setup

    raise SystemExit(_setup.run(fix=fix))


@main.command()
@click.option("--source", default="mic", help="mic | system | wav:<path>")
@click.option("--event-id", default=None, type=int)
def record(source: str, event_id: int | None) -> None:
    """Record audio and run the pipeline."""
    del event_id  # Phase 2 (calendar enrichment).
    from . import recorder
    from .audio_source import MicSource, WavFileSource

    session_uuid = str(uuid.uuid4())

    if source.startswith("wav:"):
        wav_path = Path(source[4:]).expanduser()
        if not wav_path.exists():
            raise click.ClickException(f"WAV file not found: {wav_path}")
        audio_source = WavFileSource(wav_path)
    elif source == "mic":
        audio_dir = _paths.data_dir() / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav_out_path = audio_dir / f"{session_uuid}.wav"
        audio_source = MicSource(wav_out_path=wav_out_path)
    elif source == "system":
        raise click.ClickException("system audio source: deferred to a later phase.")
    else:
        raise click.ClickException(
            f"unknown source: {source!r}; expected 'mic', 'system', or 'wav:<path>'"
        )

    try:
        result = recorder.run(audio_source, session_uuid=session_uuid)
    except recorder.RecorderAlreadyRunning as e:
        raise click.ClickException(str(e)) from e

    if result.recording_id is None:
        # Capture succeeded (WAV is on disk) but the post-stop pipeline failed.
        # Surface this as a non-zero exit so wrapping scripts notice; the WAV
        # is preserved per PRD §3.14 and a re-run is possible.
        raise click.ClickException(
            f"recording captured but pipeline failed; WAV preserved at {result.audio_path}. "
            f"re-run with `jarvis process {result.session_uuid}`"
        )
    click.echo(
        f"recorded session={result.session_uuid} "
        f"recording_id={result.recording_id} turns={result.turns_written}"
    )


@main.command()
@click.option("--force", is_flag=True, help="SIGKILL instead of SIGTERM.")
def stop(force: bool) -> None:
    """Signal an in-progress `jarvis record` to finalize and exit."""
    pid = _proc.read_pidfile()
    if pid is None:
        click.echo("no recorder running.", err=True)
        raise SystemExit(1)
    _proc.stop_pid(pid, force=force)
    click.echo(f"signaled recorder pid={pid} ({'KILL' if force else 'TERM'}).")


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


@main.command()
def tray() -> None:
    """Launch the menu-bar / system-tray app."""
    from . import tray as _tray

    _tray.run()
