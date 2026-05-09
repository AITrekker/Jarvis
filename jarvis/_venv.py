"""Venv detection for entry points launched outside `uv run`.

Three checks because none alone is reliable across macOS, Linux, and Windows:
- `sys.real_prefix` (legacy virtualenv)
- `sys.base_prefix != sys.prefix` (stdlib venv)
- `VIRTUAL_ENV` env var (set by activate scripts but not always)
"""

from __future__ import annotations

import os
import sys


def in_venv() -> bool:
    return (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        or os.environ.get("VIRTUAL_ENV") is not None
    )


def require_venv() -> None:
    """Exit with a helpful message if not running inside a venv.

    Use this on entry points that users may launch outside `uv run` (the tray
    app, double-clicked launchers). Skip on `jarvis mcp serve` — the chat host
    launches it correctly via stdio and any stdout writes corrupt the protocol.
    """
    if in_venv():
        return
    activate = r".venv\Scripts\activate.bat" if os.name == "nt" else "source .venv/bin/activate"
    sys.stderr.write(
        "\nJarvis must run inside a virtual environment.\n"
        f"  Activate it:    {activate}\n"
        "  Or use uv:      uv run jarvis ...\n\n"
    )
    sys.exit(1)
