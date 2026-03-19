from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolInput:
    query: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolOutput:
    data: Any
    summary: str


@dataclass(frozen=True)
class ToolExecution:
    name: str
    input: ToolInput
    output: ToolOutput | None
    error: str | None = None


class Tool(Protocol):
    name: str

    def run(self, tool_input: ToolInput) -> ToolExecution:
        ...
