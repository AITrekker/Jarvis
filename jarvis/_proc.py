"""Managed subprocess + pidfile helpers.

The tray spawns the recorder as a subprocess and signals it to stop. The
recorder writes its pid to a file so the tray (or `jarvis stop`) can find it
across process boundaries.

Keep platform branching here, not in callers: SIGTERM on Unix, taskkill on
Windows. Force-kill is exposed but should be a last resort — the recorder
needs a graceful shutdown to flush the transcript.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def runtime_dir() -> Path:
    """Per-user runtime directory. Follows OS conventions.

    - Linux: $XDG_RUNTIME_DIR or ~/.local/share/jarvis/run
    - macOS: ~/Library/Application Support/jarvis/run
    - Windows: %LOCALAPPDATA%\\jarvis\\run
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return Path(base) / "jarvis" / "run"
    if sys.platform == "darwin":
        return Path(os.path.expanduser("~/Library/Application Support/jarvis/run"))
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.local/share/jarvis/run")
    return Path(base)


def default_pidfile() -> Path:
    return runtime_dir() / "recorder.pid"


def write_pidfile(path: Path | None = None) -> Path:
    path = path or default_pidfile()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()))
    return path


def read_pidfile(path: Path | None = None) -> int | None:
    path = path or default_pidfile()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
    except ValueError:
        return None
    return pid if _pid_alive(pid) else None


def clear_pidfile(path: Path | None = None) -> None:
    path = path or default_pidfile()
    path.unlink(missing_ok=True)


def stop_pid(pid: int, *, force: bool = False) -> None:
    if sys.platform == "win32":
        flag = "/F" if force else ""
        cmd = ["taskkill", "/PID", str(pid)] + ([flag] if flag else [])
        subprocess.run(cmd, check=False)
    else:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


class ManagedProcess:
    """Spawn + clean up a child process with `terminate-then-wait` semantics.

    Use as a context manager: `with ManagedProcess([...]) as p: ...`
    On exit, terminates the child and waits up to `grace_seconds` before SIGKILL.
    """

    def __init__(self, cmd: Sequence[str], grace_seconds: float = 5.0) -> None:
        self.cmd = list(cmd)
        self.grace_seconds = grace_seconds
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> ManagedProcess:
        self.proc = subprocess.Popen(self.cmd)
        return self

    def __exit__(self, *exc) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=self.grace_seconds)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
