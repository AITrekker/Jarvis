"""Tests for the small cross-platform helpers under jarvis/_*.py."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import pytest

from jarvis import _logging, _proc, _progress, _venv


def test_in_venv_detects_test_runner_venv() -> None:
    # pytest is invoked via uv run, so we are always in a venv here.
    assert _venv.in_venv() is True


def test_require_venv_passes_in_venv() -> None:
    _venv.require_venv()  # must not raise / exit


def test_require_venv_exits_when_not_in_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_venv, "in_venv", lambda: False)
    with pytest.raises(SystemExit) as excinfo:
        _venv.require_venv()
    assert excinfo.value.code == 1


def test_logging_configure_clears_existing_handlers(tmp_path: Path) -> None:
    root = logging.getLogger()
    junk = logging.NullHandler()
    root.addHandler(junk)
    assert junk in root.handlers

    log_file = tmp_path / "jarvis.log"
    _logging.configure(level=logging.DEBUG, log_file=log_file)

    assert junk not in root.handlers
    logging.getLogger("jarvis.test").info("hello")
    for h in root.handlers:
        h.flush()
    assert log_file.exists()
    assert "hello" in log_file.read_text()


def test_progress_spinner_non_tty_prints_message_once(capsys: pytest.CaptureFixture[str]) -> None:
    # sys.stderr in pytest is captured and not a TTY, so spinner should fall
    # through to a single message print without animating.
    with _progress.spinner("loading models"):
        time.sleep(0.05)
    err = capsys.readouterr().err
    assert "loading models" in err


def test_pidfile_roundtrip(tmp_path: Path) -> None:
    pidfile = tmp_path / "recorder.pid"
    written = _proc.write_pidfile(pidfile)
    assert written == pidfile
    assert pidfile.read_text().strip() == str(os.getpid())

    pid = _proc.read_pidfile(pidfile)
    assert pid == os.getpid()

    _proc.clear_pidfile(pidfile)
    assert not pidfile.exists()
    assert _proc.read_pidfile(pidfile) is None


def test_pidfile_stale_pid_returns_none_and_cleans_up(tmp_path: Path) -> None:
    """A stale pidfile (file present, process dead) is unlinked on read.

    Critical because PIDs get recycled — without cleanup, the next live
    process to receive that PID will be mis-identified as the recorder
    and `jarvis record` will refuse to start with `RecorderAlreadyRunning`.
    """
    pidfile = tmp_path / "recorder.pid"
    pidfile.write_text("999999")  # very unlikely to be a live pid
    assert _proc.read_pidfile(pidfile) is None
    assert not pidfile.exists()


def test_pidfile_malformed_is_cleaned_up(tmp_path: Path) -> None:
    pidfile = tmp_path / "recorder.pid"
    pidfile.write_text("not-a-pid")
    assert _proc.read_pidfile(pidfile) is None
    assert not pidfile.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="signal semantics differ on Windows")
def test_managed_process_terminates_child() -> None:
    # Spawn a Python process that sleeps; ensure the context manager cleans it up.
    cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
    with _proc.ManagedProcess(cmd, grace_seconds=2.0) as mp:
        assert mp.proc is not None
        time.sleep(0.1)
        assert mp.proc.poll() is None  # still running

    # After exit, the process should be gone.
    assert mp.proc is not None
    assert mp.proc.poll() is not None


@pytest.mark.skipif(sys.platform == "win32", reason="signal semantics differ on Windows")
def test_managed_process_force_kills_on_grace_timeout() -> None:
    # Trap SIGTERM in the child so terminate() is ignored; ensure SIGKILL fires.
    script = "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(60)\n"
    cmd = [sys.executable, "-c", script]
    start = time.monotonic()
    with _proc.ManagedProcess(cmd, grace_seconds=1.0) as mp:
        time.sleep(0.1)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0  # should not have waited the full sleep(60)
    assert mp.proc is not None
    assert mp.proc.poll() is not None


def test_managed_process_no_op_if_already_exited() -> None:
    cmd = [sys.executable, "-c", "pass"]
    with _proc.ManagedProcess(cmd) as mp:
        assert mp.proc is not None
        mp.proc.wait()
    # No exception on exit even though the process already finished.
    assert mp.proc.poll() == 0


def test_default_pidfile_under_user_dir() -> None:
    p = _proc.default_pidfile()
    assert p.name == "recorder.pid"
    assert "jarvis" in str(p).lower() or "XDG_RUNTIME_DIR" in os.environ
