from __future__ import annotations

import inspect
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentCallSpec:
    """Prompt, tools, and scratch metadata for one model-backed agent turn."""

    prompt: Any
    tools: tuple[Any, ...] = ()
    output_schema: Any | None = None
    output_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
        spec = self.build_call(state)
        try:
            with self.call_context(state, spec):
                response = self.execute_call(spec)
        except Exception as exc:
            handled = self.handle_call_error(state, spec, exc)
            if handled is None:
                raise
            return handled
        return self.apply_response(state, spec, response)

    def build_call(self, state: dict[str, Any]) -> AgentCallSpec:
        raise NotImplementedError

    def apply_response(
        self,
        state: dict[str, Any],
        spec: AgentCallSpec,
        response: Any,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def call_context(self, state: dict[str, Any], spec: AgentCallSpec):
        return nullcontext()

    def execute_call(self, spec: AgentCallSpec) -> Any:
        output_schema = spec.output_schema
        if spec.tools:
            if output_schema and _accepts_keyword(self.llm.invoke, "tools"):
                kwargs = {"tools": spec.tools}
                if _accepts_keyword(self.llm.invoke, "output_schema"):
                    kwargs["output_schema"] = output_schema
                return self.llm.invoke(spec.prompt, **kwargs)
            return self.llm.bind_tools(spec.tools).invoke(spec.prompt)
        if output_schema and _accepts_keyword(self.llm.invoke, "output_schema"):
            return self.llm.invoke(spec.prompt, output_schema=output_schema)
        return self.llm.invoke(spec.prompt)

    def handle_call_error(
        self,
        state: dict[str, Any],
        spec: AgentCallSpec,
        error: Exception,
    ) -> dict[str, Any] | None:
        return None


def _accepts_keyword(callable_obj: Any, keyword: str) -> bool:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        or (
            name == keyword
            and parameter.kind
            in {
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        )
        for name, parameter in signature.parameters.items()
    )
