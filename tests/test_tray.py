"""Tray unit tests. Mocks pystray so no real icon is drawn.

The tray is intentionally a thin adapter (PRD §3.13). These tests verify:
- Menu items are wired to the right handlers.
- The poll loop flips the icon's recording state when the pidfile appears
  and clears the state when it disappears.
- "Quit" stops the icon but does not kill an active recorder.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

# The tray module needs Pillow to draw the icon. pystray itself is mocked
# below, so we don't require it at the test level — just Pillow.
pytest.importorskip("PIL")


@pytest.fixture
def fake_pystray(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Replace `pystray` with a fake so importing tray works headless."""

    class _MenuItem:
        def __init__(self, text, action, *, enabled=True):
            self.text = text
            self.action = action
            self.enabled = enabled

    class _Menu:
        def __init__(self, *items):
            self.items = items

    class _Icon:
        def __init__(self, name, icon=None, title=None, menu=None):
            self.name = name
            self.icon = icon
            self.title = title
            self.menu = menu
            self.running = False
            self.update_count = 0

        def run(self):
            self.running = True

        def stop(self):
            self.running = False

        def update_menu(self):
            self.update_count += 1

    fake = types.ModuleType("pystray")
    fake.Icon = _Icon  # type: ignore[attr-defined]
    fake.Menu = _Menu  # type: ignore[attr-defined]
    fake.MenuItem = _MenuItem  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pystray", fake)
    return types.SimpleNamespace(Icon=_Icon, Menu=_Menu, MenuItem=_MenuItem)


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("JARVIS_RUNTIME_DIR", str(tmp_path / "run"))
    return tmp_path


def _import_tray():
    # Re-import so the fake pystray fixture is picked up by `import pystray`
    # inside TrayApp.__init__.
    if "jarvis.tray" in sys.modules:
        del sys.modules["jarvis.tray"]
    from jarvis import tray  # noqa: WPS433 - intentional re-import

    return tray


def test_tray_app_has_three_menu_items(fake_pystray, isolated_runtime: Path) -> None:
    tray = _import_tray()
    app = tray.TrayApp()

    items = list(app.icon.menu.items)
    labels = [it.text for it in items]
    assert labels == ["Start recording", "Stop recording", "Quit"]


def test_tray_starts_idle(fake_pystray, isolated_runtime: Path) -> None:
    tray = _import_tray()
    app = tray.TrayApp()
    assert app._is_recording is False
    assert "idle" in app.icon.title


def test_poll_reflects_pidfile_state(
    fake_pystray, isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tray = _import_tray()
    app = tray.TrayApp()

    from jarvis import _proc

    pidfile = _proc.default_pidfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))

    app.poll_once()
    assert app._is_recording is True
    assert "recording" in app.icon.title

    pidfile.unlink()
    app.poll_once()
    assert app._is_recording is False
    assert "idle" in app.icon.title


def test_stop_handler_signals_pidfile(
    fake_pystray, isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tray = _import_tray()
    app = tray.TrayApp()

    from jarvis import _proc

    pidfile = _proc.default_pidfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))

    sent: dict[str, object] = {}

    def fake_stop_pid(pid: int, *, force: bool = False) -> None:
        sent["pid"] = pid
        sent["force"] = force

    monkeypatch.setattr(_proc, "stop_pid", fake_stop_pid)

    app._on_stop(app.icon, app.icon.menu.items[1])
    assert sent == {"pid": os.getpid(), "force": False}


def test_stop_handler_no_op_when_idle(
    fake_pystray, isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tray = _import_tray()
    app = tray.TrayApp()

    from jarvis import _proc

    called = {"count": 0}

    def fake_stop_pid(*args, **kwargs):
        called["count"] += 1

    monkeypatch.setattr(_proc, "stop_pid", fake_stop_pid)

    app._on_stop(app.icon, None)
    assert called["count"] == 0


def test_start_spawns_managed_process(
    fake_pystray, isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tray = _import_tray()

    spawned: dict[str, object] = {}

    class FakeManagedProcess:
        def __init__(self, cmd, grace_seconds: float = 5.0):
            spawned["cmd"] = list(cmd)
            self.proc = "FAKE"

        def __enter__(self):
            spawned["entered"] = True
            return self

        def __exit__(self, *exc):
            spawned["exited"] = True

    monkeypatch.setattr(tray._proc, "ManagedProcess", FakeManagedProcess)

    app = tray.TrayApp()
    app._on_start(app.icon, app.icon.menu.items[0])

    assert spawned.get("entered") is True
    assert "record" in spawned["cmd"]
    assert "--source" in spawned["cmd"]
    assert "mic" in spawned["cmd"]


def test_quit_does_not_kill_recorder(
    fake_pystray, isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tray = _import_tray()
    app = tray.TrayApp()

    # Pretend a recorder subprocess has been spawned.
    class FakeProc:
        def __init__(self):
            self.terminated = False
            self.proc = object()

        def __exit__(self, *exc):
            self.terminated = True

    fake = FakeProc()
    app._recorder_proc = fake  # type: ignore[assignment]

    app._on_quit(app.icon, None)

    # The tray should detach (set proc=None) so __exit__ doesn't terminate
    # the live recorder. We're a separate process by design.
    assert fake.proc is None
    assert app.icon.running is False  # icon.stop() was called
    assert app._poll_stop.is_set()


def test_make_icon_image_returns_image(fake_pystray) -> None:
    tray = _import_tray()
    img = tray._make_icon_image((10, 20, 30))
    assert img.size == (64, 64)
    assert img.mode == "RGBA"
