from __future__ import annotations

from typing import Any


class DivergeAgentNode:
    """Explicit callable agent node used by the ADK workflow facade."""

    name = "diverge_agent"

    def __init__(
        self,
        llm: Any,
        memory: Any = None,
        *,
        name: str | None = None,
        tools: tuple[Any, ...] | list[Any] | None = None,
    ) -> None:
        self.name = name or self.name
        self.llm = llm
        self.memory = memory
        self.tools = tuple(tools or ())

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.run(state)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
