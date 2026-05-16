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
@click.option(
    "--wav",
    "wav_path_opt",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Override WAV location (default: ~/.../audio/<session_uuid>.wav).",
)
def process(session_uuid: str, wav_path_opt: Path | None) -> None:
    """Re-run the segment+transcribe+persist pipeline on a stored WAV.

    Used as the recovery path when `jarvis record` captured audio but the
    post-stop pipeline failed (e.g. transient DB outage). Idempotent: the
    persister updates the existing recordings row and re-inserts turns.
    """
    from datetime import UTC, datetime

    from . import persister, segmenter, transcriber
    from .audio_source import WavFileSource
    from .types import SessionMeta

    if wav_path_opt is not None:
        wav_path = wav_path_opt
    else:
        wav_path = _paths.data_dir() / "audio" / f"{session_uuid}.wav"
        if not wav_path.exists():
            raise click.ClickException(
                f"Cannot find WAV for session {session_uuid} at {wav_path}. "
                "Pass --wav <path> if it's elsewhere."
            )

    src = WavFileSource(wav_path)
    try:
        segments = list(segmenter.segment(src))
    finally:
        src.close()

    transcript = transcriber.transcribe(segments)

    now = datetime.now(tz=UTC)
    meta = SessionMeta(
        session_uuid=session_uuid,
        source_label=f"wav:{wav_path.name}",
        started_at=now,
        ended_at=now,
    )
    recording_id = persister.persist_recording(
        audio_path=wav_path,
        transcript=transcript,
        speakers={},
        calendar_event=None,
        session_meta=meta,
    )
    click.echo(
        f"reprocessed session={session_uuid} "
        f"recording_id={recording_id} turns={len(transcript.turns)}"
    )


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


@main.command("enroll-self")
@click.argument(
    "reference_wav",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--name", default="me", help="Display name for the owner row.")
def enroll_self_cmd(reference_wav: Path, name: str) -> None:
    """Pre-enroll the owner from a reference WAV (≥ 30s recommended)."""
    raise click.ClickException("enroll-self: not implemented yet (Phase 2)")


@main.group()
def calendar() -> None:
    """Calendar sync commands."""


@calendar.command("authorize")
def calendar_authorize() -> None:
    """One-time OAuth flow; stores refresh token in macOS Keychain."""
    raise click.ClickException("calendar authorize: not implemented yet (Phase 2)")


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
