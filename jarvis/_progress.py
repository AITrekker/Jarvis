"""Loading spinner for slow imports / model loads.

WhisperX + pyannote take 5-15s to import and load weights. A spinner tells the
user the process is alive without coupling to any UI framework.
"""

from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager

_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


@contextmanager
def spinner(message: str, stream=None):
    stream = stream or sys.stderr
    if not stream.isatty():
        stream.write(f"{message}\n")
        stream.flush()
        yield
        return

    stop = threading.Event()

    def run() -> None:
        i = 0
        while not stop.is_set():
            stream.write(f"\r  {_FRAMES[i % len(_FRAMES)]} {message}")
            stream.flush()
            time.sleep(0.1)
            i += 1
        stream.write("\r" + " " * (len(message) + 6) + "\r")
        stream.flush()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=1.0)
