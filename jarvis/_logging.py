"""Logging setup that survives library imports.

`logging.basicConfig` is a silent no-op once any handler is attached to the
root logger. sounddevice, pyannote, and others attach handlers at import time,
so we must clear the root logger's handlers before reconfiguring.

Also reconfigures stdout/stderr to UTF-8 on Windows so banner emoji and
box-drawing characters do not crash `cp1252` consoles.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path


def configure(level: int = logging.INFO, log_file: Path | None = None) -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            # Some embedded terminals do not support reconfigure; tolerate it.
            with contextlib.suppress(AttributeError, TypeError):
                stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)
