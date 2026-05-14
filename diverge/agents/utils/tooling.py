from __future__ import annotations

import inspect
from functools import update_wrapper
from typing import Any, Callable


class SimpleTool:
    """Minimal callable tool wrapper used by the ADK runtime."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.name = func.__name__
        self.description = inspect.getdoc(func) or ""
        update_wrapper(self, func)

    @property
    def args(self) -> dict[str, Any]:
        signature = inspect.signature(self.func)
        return {
            name: parameter.annotation
            for name, parameter in signature.parameters.items()
        }

    def invoke(self, input: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        arguments = dict(input or {})
        arguments.update(kwargs)
        return self.func(**arguments)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)


def tool(func: Callable[..., Any]) -> SimpleTool:
    return SimpleTool(func)
