from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


PromptResult = tuple[Any, Sequence[Any], Mapping[str, Any]]
PromptBuilder = Callable[..., PromptResult]
OutputCommitter = Callable[[dict[str, Any], Any], dict[str, Any]]
InvalidResponseWarning = Callable[[BaseException], dict[str, str]]
InvalidResponseFallback = Callable[[str, BaseException], Any]
TransientErrorPredicate = Callable[[BaseException], bool]
TransientErrorWarning = Callable[[BaseException], dict[str, str]]
TransientErrorFallback = Callable[[Mapping[str, Any], BaseException], Any]


@dataclass(frozen=True, slots=True)
class AgentTurn:
    """Runtime-neutral contract for one state-producing agent turn."""

    agent_name: str
    display_name: str
    output_schema: Any
    output_key: str
    build_prompt: PromptBuilder
    commit_output: OutputCommitter
    analyst_key: str | None = None
    evidence_output_key: str | None = None
    report_key: str | None = None
    structured_agent_name: str | None = None
    tools: tuple[Any, ...] = ()
    memory_key: str | None = None
    invalid_response_warning: InvalidResponseWarning | None = None
    fallback_from_invalid_response: InvalidResponseFallback | None = None
    is_transient_error: TransientErrorPredicate | None = None
    transient_error_warning: TransientErrorWarning | None = None
    fallback_from_transient_error: TransientErrorFallback | None = None

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(
            str(getattr(tool, "name", None) or getattr(tool, "__name__", ""))
            for tool in self.tools
        )
