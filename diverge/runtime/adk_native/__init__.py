"""ADK-native analysis runtime boundary.

This package is the migration target for moving Diverge's analysis execution
from the compatibility graph runner to ADK-managed workflows, sessions, and
events.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "ADK_NATIVE_RUNTIME_NAME": (
        "diverge.runtime.adk_native.runner",
        "ADK_NATIVE_RUNTIME_NAME",
    ),
    "build_analysis_workflow": (
        "diverge.runtime.adk_native.workflow",
        "build_analysis_workflow",
    ),
    "build_adk_web_app": (
        "diverge.runtime.adk_native.web_app",
        "build_adk_web_app",
    ),
    "build_native_analysis_workflow": (
        "diverge.runtime.adk_native.runner",
        "build_native_analysis_workflow",
    ),
    "NativeAnalystAgent": (
        "diverge.runtime.adk_native.agents",
        "NativeAnalystAgent",
    ),
    "merge_state_delta": (
        "diverge.runtime.adk_native.state_adapter",
        "merge_state_delta",
    ),
    "state_delta_from_event": (
        "diverge.runtime.adk_native.progress_adapter",
        "state_delta_from_event",
    ),
    "stream_analysis_state_chunks": (
        "diverge.runtime.adk_native.runner",
        "stream_analysis_state_chunks",
    ),
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
