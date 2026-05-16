"""System-tray surface for the recorder. PRD §3.13.

The tray is a thin adapter over the same primitives the CLI uses:
- "Start recording" spawns `jarvis record --source mic` as a subprocess via
  `_proc.ManagedProcess`, so the tray stays responsive while the recorder
  loads Whisper, runs the pipeline, etc.
- "Stop recording" reads the pidfile and sends SIGTERM (same code path as
  `jarvis stop`).
- Quitting the tray does NOT kill an active recorder — they're separate
  processes by design (PRD §3.13).
- A background thread polls the pidfile every 1s to keep the icon color in
  sync with reality, including the case where the user runs `jarvis record`
  from the terminal while the tray is open.

`pystray` works on macOS, Windows, and Linux from one codebase. `Pillow`
generates the gray/red dot icons in code so we don't ship binary assets.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import TYPE_CHECKING

from . import _proc

if TYPE_CHECKING:  # pragma: no cover - type-only
    import pystray

log = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
IDLE_COLOR = (160, 160, 160)
RECORDING_COLOR = (220, 30, 30)


def _make_icon_image(color: tuple[int, int, int]):
    """Create a 64x64 RGBA image with a filled circle of the given color."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((6, 6, 58, 58), fill=(*color, 255))
    return img


class TrayApp:
    """Tray app state. One instance per process."""

    def __init__(self) -> None:
        import pystray

        self._pystray = pystray
        self._is_recording = False
        self._recorder_proc: _proc.ManagedProcess | None = None
        self._poll_stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self.icon: pystray.Icon = self._build_icon()

    def _build_icon(self) -> pystray.Icon:
        pystray = self._pystray
        menu = pystray.Menu(
            pystray.MenuItem("Start recording", self._on_start, enabled=self._can_start),
            pystray.MenuItem("Stop recording", self._on_stop, enabled=self._can_stop),
            pystray.MenuItem("Quit", self._on_quit),
        )
        return pystray.Icon(
            "jarvis",
            icon=_make_icon_image(IDLE_COLOR),
            title="Jarvis (idle)",
            menu=menu,
        )

    # --- Menu predicates ---------------------------------------------------

    def _can_start(self, _item) -> bool:
        return not self._is_recording

    def _can_stop(self, _item) -> bool:
        return self._is_recording

    # --- Menu handlers -----------------------------------------------------

    def _on_start(self, _icon, _item) -> None:
        if self._is_recording:
            return
        cmd = self._record_command()
        log.info("tray: starting recorder %s", cmd)
        proc = _proc.ManagedProcess(cmd)
        proc.__enter__()
        self._recorder_proc = proc
        # Don't flip _is_recording here — the poll loop will pick up the
        # pidfile that the recorder writes on startup.

    def _on_stop(self, _icon, _item) -> None:
        pid = _proc.read_pidfile()
        if pid is None:
            log.info("tray: stop requested but no live pidfile")
            return
        log.info("tray: stopping recorder pid=%s", pid)
        _proc.stop_pid(pid)

    def _on_quit(self, _icon, _item) -> None:
        log.info("tray: quitting (recorder, if any, is left running)")
        self._poll_stop.set()
        # Detach from the child without terminating it: leaving a recording
        # alive when the tray quits is the documented behavior (PRD §3.13).
        if self._recorder_proc is not None:
            self._recorder_proc.proc = None
        self.icon.stop()

    # --- State sync --------------------------------------------------------

    def _record_command(self) -> list[str]:
        # Run the same CLI the user would run: keeps the tray a true adapter.
        return [sys.executable, "-m", "jarvis", "record", "--source", "mic"]

    def _set_recording(self, recording: bool) -> None:
        if recording == self._is_recording:
            return
        self._is_recording = recording
        color = RECORDING_COLOR if recording else IDLE_COLOR
        self.icon.icon = _make_icon_image(color)
        self.icon.title = "Jarvis (recording)" if recording else "Jarvis (idle)"
        # update_menu re-evaluates the enabled predicates.
        try:
            self.icon.update_menu()
        except Exception:  # pragma: no cover - best effort
            log.debug("update_menu failed", exc_info=True)

    def poll_once(self) -> None:
        """Single iteration of the pidfile-polling loop. Exposed for tests."""
        pid = _proc.read_pidfile()
        self._set_recording(pid is not None)

    def _poll_loop(self) -> None:
        while not self._poll_stop.wait(POLL_INTERVAL_SECONDS):
            try:
                self.poll_once()
            except Exception:  # pragma: no cover - keep tray alive on glitches
                log.exception("tray poll loop iteration failed")

    def start_polling(self) -> threading.Thread:
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="jarvis-tray-poll", daemon=True
        )
        self._poll_thread.start()
        return self._poll_thread

    def run(self) -> None:
        # Initial sync before showing the icon, so the color matches reality
        # even if a recorder is already running.
        self.poll_once()
        self.start_polling()
        self.icon.run()


def run() -> None:
    """Entry point for `jarvis tray`."""
    TrayApp().run()
