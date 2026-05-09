"""Tests for jarvis._paths cross-platform directory helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis import _paths


def test_data_dir_respects_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "data"))
    assert _paths.data_dir() == tmp_path / "data"


def test_config_dir_respects_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JARVIS_CONFIG_DIR", str(tmp_path / "cfg"))
    assert _paths.config_dir() == tmp_path / "cfg"


def test_runtime_dir_respects_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JARVIS_RUNTIME_DIR", str(tmp_path / "run"))
    assert _paths.runtime_dir() == tmp_path / "run"


def test_paths_have_jarvis_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without overrides, every default path includes the app name."""
    for var in ("JARVIS_DATA_DIR", "JARVIS_CONFIG_DIR", "JARVIS_RUNTIME_DIR"):
        monkeypatch.delenv(var, raising=False)
    for d in (_paths.data_dir(), _paths.config_dir(), _paths.runtime_dir()):
        assert "jarvis" in str(d).lower()


def test_paths_are_user_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults must not point at /tmp, /var, or anything system-wide."""
    for var in ("JARVIS_DATA_DIR", "JARVIS_CONFIG_DIR", "JARVIS_RUNTIME_DIR"):
        monkeypatch.delenv(var, raising=False)
    for d in (_paths.data_dir(), _paths.config_dir(), _paths.runtime_dir()):
        s = str(d)
        assert not s.startswith("/tmp"), s
        assert not s.startswith("/var"), s
