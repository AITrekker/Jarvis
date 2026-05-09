"""Phase 0 gate tests.

Lightweight checks that the scaffold imports cleanly, the CLI is wired,
and the module stubs match the PRD interfaces.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from jarvis import (
    agent,
    audio_source,
    calendar_sync,
    cli,
    config,
    persister,
    search,
    segmenter,
    speaker_resolver,
    summarizer,
    transcriber,
    types,
)
from jarvis.tools import REGISTRY, all_tools


def test_all_modules_import() -> None:
    """Every module named in PRD §3 imports without side effects."""
    for mod in (
        agent,
        audio_source,
        calendar_sync,
        cli,
        config,
        persister,
        search,
        segmenter,
        speaker_resolver,
        summarizer,
        transcriber,
        types,
    ):
        assert mod is not None


def test_cli_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "record" in result.output
    assert "search" in result.output


def test_unimplemented_commands_fail_cleanly() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["search", "anything"])
    assert result.exit_code != 0
    assert "not implemented" in result.output.lower()


def test_tool_registry_starts_empty() -> None:
    assert REGISTRY == {}
    assert all_tools() == []


def test_module_stubs_raise_not_implemented() -> None:
    """Stubs must fail loudly, not silently return None."""
    with pytest.raises(NotImplementedError):
        search.search("anything")
    with pytest.raises(NotImplementedError):
        summarizer.summarize(1)
