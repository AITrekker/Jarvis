"""Per-OS data, config, and runtime directories.

Use these helpers everywhere a path is constructed instead of writing
`~/.local/share/...` or `~/.config/...` literals. Those are XDG conventions
that only fit Linux; macOS and Windows have their own.

Override any of them at runtime by setting `JARVIS_DATA_DIR`,
`JARVIS_CONFIG_DIR`, or `JARVIS_RUNTIME_DIR`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "jarvis"


def _from_env(var: str) -> Path | None:
    val = os.environ.get(var)
    return Path(os.path.expanduser(val)) if val else None


def data_dir() -> Path:
    """Long-lived data: audio files, model caches, the local DB if SQLite."""
    if (p := _from_env("JARVIS_DATA_DIR")) is not None:
        return p
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return Path(base) / APP
    if sys.platform == "darwin":
        return Path(os.path.expanduser(f"~/Library/Application Support/{APP}"))
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / APP


def config_dir() -> Path:
    """User-edited config: oauth secrets, host overrides."""
    if (p := _from_env("JARVIS_CONFIG_DIR")) is not None:
        return p
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return Path(base) / APP
    if sys.platform == "darwin":
        return Path(os.path.expanduser(f"~/Library/Application Support/{APP}"))
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / APP


def runtime_dir() -> Path:
    """Ephemeral process state: pidfiles, sockets."""
    if (p := _from_env("JARVIS_RUNTIME_DIR")) is not None:
        return p
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return Path(base) / APP / "run"
    if sys.platform == "darwin":
        return Path(os.path.expanduser(f"~/Library/Application Support/{APP}/run"))
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.local/share")
    return Path(base) / APP / "run"
