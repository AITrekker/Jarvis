"""Primary conversational agent. PRD §3.10.

Single agent in v1. Sub-agents are spawned for bounded heavy reasoning only.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tools import Tool
from .types import Citation


@dataclass
class ToolCall:
    name: str
    args: dict
    ok: bool


@dataclass
class AgentResponse:
    text: str
    citations: list[Citation]
    tool_trace: list[ToolCall]


class Agent:
    def __init__(self, tools: list[Tool], model: str) -> None:
        self.tools = tools
        self.model = model

    def chat(self, message: str, session_id: str) -> AgentResponse:
        raise NotImplementedError("Agent.chat: implemented in Phase 4")
