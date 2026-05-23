from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable

from google.adk.tools import FunctionTool


def create_adk_tool_registry(
    tool_groups: Mapping[str, Any],
) -> dict[str, list[FunctionTool]]:
    """Adapt tool groups into ADK FunctionTool objects."""

    return {
        role: [_as_function_tool(tool) for tool in _group_tools(group)]
        for role, group in tool_groups.items()
    }


def create_adk_tool_collections(
    tool_groups: Mapping[str, Any],
) -> dict[str, AdkToolCollection]:
    """Adapt tool groups into named ADK tool collections."""

    return {
        role: AdkToolCollection(tuple(tools))
        for role, tools in create_adk_tool_registry(tool_groups).items()
    }


def _group_tools(group: Any) -> Sequence[Callable[..., Any]]:
    tools = getattr(group, "tools", group)
    if isinstance(tools, Sequence):
        return tools
    raise TypeError(f"Unsupported ADK tool group: {group!r}")


def _as_function_tool(tool: Callable[..., Any] | FunctionTool) -> FunctionTool:
    if isinstance(tool, FunctionTool):
        return tool
    return FunctionTool(tool)


@dataclass(frozen=True)
class AdkToolCollection:
    """Grouped ADK tools plus a name lookup surface."""

    tools: tuple[FunctionTool, ...]

    def __post_init__(self) -> None:
        names = [tool.name for tool in self.tools]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Duplicate ADK tool names: {duplicates}")

    @property
    def tools_by_name(self) -> dict[str, FunctionTool]:
        return {tool.name: tool for tool in self.tools}

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = self.tools_by_name[tool_name]
        return str(tool.func(**_filter_arguments(tool.func, arguments)))


def _filter_arguments(
    func: Callable[..., Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    signature = inspect.signature(func)
    return {
        key: value for key, value in arguments.items() if key in signature.parameters
    }
