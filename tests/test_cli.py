"""CLI smoke tests for the Phase 1 record/stop commands.

We don't exercise the real audio + DB stack here — the recorder itself is
covered by tests/test_recorder.py and persister by tests/test_persister.py.
This file only checks the CLI plumbing: argument parsing, dispatch, and
error messaging.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from jarvis import _proc, cli, recorder
from jarvis.recorder import RecorderResult


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("JARVIS_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "data"))
    return tmp_path


def test_record_wav_calls_recorder_run(
    isolated_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wav_path = tmp_path / "in.wav"
    wav_path.write_bytes(b"FAKE")

    captured: dict[str, object] = {}

    class FakeWav:
        def __init__(self, path):
            captured["wav_path"] = Path(path)
            self.source_label = f"wav:{path}"
            self.path = Path(path)

    def fake_run(source, *, session_uuid=None):
        captured["source"] = source
        captured["session_uuid"] = session_uuid
        return RecorderResult(
            session_uuid=session_uuid or "deadbeef",
            recording_id=7,
            audio_path=Path(captured["wav_path"]),
            turns_written=3,
        )

    from jarvis import audio_source as audio_source_mod

    monkeypatch.setattr(audio_source_mod, "WavFileSource", FakeWav)
    monkeypatch.setattr(recorder, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["record", "--source", f"wav:{wav_path}"])

    assert result.exit_code == 0, result.output
    assert isinstance(captured["source"], FakeWav)
    assert captured["wav_path"] == wav_path
    assert "recording_id=7" in result.output
    assert "turns=3" in result.output


def test_record_wav_missing_file(isolated_runtime: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["record", "--source", f"wav:{tmp_path / 'nope.wav'}"])
    assert result.exit_code != 0
    assert "WAV file not found" in result.output


def test_record_unknown_source(isolated_runtime: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["record", "--source", "bogus"])
    assert result.exit_code != 0
    assert "unknown source" in result.output


def test_record_pipeline_failure_prints_recovery_hint(
    isolated_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wav_path = tmp_path / "in.wav"
    wav_path.write_bytes(b"FAKE")

    class FakeWav:
        def __init__(self, path):
            self.source_label = f"wav:{path}"
            self.path = Path(path)

    def fake_run(source, *, session_uuid=None):
        return RecorderResult(
            session_uuid=session_uuid or "abc",
            recording_id=None,
            audio_path=wav_path,
            turns_written=0,
        )

    from jarvis import audio_source as audio_source_mod

    monkeypatch.setattr(audio_source_mod, "WavFileSource", FakeWav)
    monkeypatch.setattr(recorder, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["record", "--source", f"wav:{wav_path}"])

    # Capture succeeded (WAV preserved) but pipeline failed -> exit non-zero so
    # wrapping scripts notice. Both stdout and stderr are captured by CliRunner;
    # ClickException writes to stderr ("Error:" prefix).
    assert result.exit_code != 0
    assert "pipeline failed" in result.output
    assert "jarvis process" in result.output


def test_record_already_running(
    isolated_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wav_path = tmp_path / "in.wav"
    wav_path.write_bytes(b"FAKE")

    class FakeWav:
        def __init__(self, path):
            self.source_label = f"wav:{path}"
            self.path = Path(path)

    def fake_run(source, *, session_uuid=None):
        raise recorder.RecorderAlreadyRunning("already running pid=123")

    from jarvis import audio_source as audio_source_mod

    monkeypatch.setattr(audio_source_mod, "WavFileSource", FakeWav)
    monkeypatch.setattr(recorder, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["record", "--source", f"wav:{wav_path}"])

    assert result.exit_code != 0
    assert "already running" in result.output


def test_stop_with_no_pidfile_exits_cleanly(isolated_runtime: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["stop"])
    assert result.exit_code == 1
    assert "no recorder running" in result.output


def test_stop_with_live_pidfile_signals(
    isolated_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pidfile = _proc.default_pidfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))

    sent: dict[str, object] = {}

    def fake_stop_pid(pid: int, *, force: bool = False) -> None:
        sent["pid"] = pid
        sent["force"] = force

    monkeypatch.setattr(_proc, "stop_pid", fake_stop_pid)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["stop"])
    assert result.exit_code == 0, result.output
    assert sent == {"pid": os.getpid(), "force": False}
    assert "TERM" in result.output


def test_stop_force(
    isolated_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pidfile = _proc.default_pidfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))

    sent: dict[str, object] = {}

    def fake_stop_pid(pid: int, *, force: bool = False) -> None:
        sent["pid"] = pid
        sent["force"] = force

    monkeypatch.setattr(_proc, "stop_pid", fake_stop_pid)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["stop", "--force"])
    assert result.exit_code == 0
    assert sent == {"pid": os.getpid(), "force": True}
    assert "KILL" in result.output


def test_help_lists_record_and_stop() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "record" in result.output
    assert "stop" in result.output
    assert "tray" in result.output
