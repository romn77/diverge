from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "AdkPrompt": ("diverge.runtime.messages", "AdkPrompt"),
    "AdkToolCollection": ("diverge.runtime.tools", "AdkToolCollection"),
    "create_adk_generation_config": (
        "diverge.runtime.model_factory",
        "create_adk_generation_config",
    ),
    "create_adk_model": ("diverge.runtime.model_factory", "create_adk_model"),
    "create_adk_tool_collections": (
        "diverge.runtime.tools",
        "create_adk_tool_collections",
    ),
    "create_adk_tool_registry": (
        "diverge.runtime.tools",
        "create_adk_tool_registry",
    ),
    "create_initial_state": ("diverge.runtime.state", "create_initial_state"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
