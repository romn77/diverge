from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


PromptResult = tuple[Any, Sequence[Any], Mapping[str, Any]]
PromptBuilder = Callable[[Mapping[str, Any]], PromptResult]
OutputCommitter = Callable[[dict[str, Any], Any], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class AnalystTurn:
    """Runtime-neutral contract for one analyst's evidence/report turn."""

    analyst_key: str
    agent_name: str
    display_name: str
    output_schema: Any
    output_key: str
    build_prompt: PromptBuilder
    evidence_output_key: str
    report_key: str
    structured_agent_name: str
    tools: tuple[Any, ...]
    commit_output: OutputCommitter

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(
            str(getattr(tool, "name", None) or getattr(tool, "__name__", ""))
            for tool in self.tools
        )
