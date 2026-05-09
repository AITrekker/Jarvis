"""Tool registry. PRD §3.9.

Adding a new tool requires a new file in this package and registration here.
No core-code changes elsewhere.
"""

from __future__ import annotations

from typing import Protocol

from ..types import ToolResult


class Tool(Protocol):
    name: str
    description: str
    schema: dict

    def __call__(self, **kwargs) -> ToolResult: ...


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    if tool.name in REGISTRY:
        raise ValueError(f"tool already registered: {tool.name}")
    REGISTRY[tool.name] = tool


def get(name: str) -> Tool:
    return REGISTRY[name]


def all_tools() -> list[Tool]:
    return list(REGISTRY.values())
