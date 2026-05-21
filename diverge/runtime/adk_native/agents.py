from __future__ import annotations

from typing import Any


def append_runtime_progress_event(
    state: dict[str, Any],
    *,
    current_agent: str,
    message: str,
) -> None:
    events = state.setdefault("runtime_progress_events", [])
    if not isinstance(events, list):
        events = []
        state["runtime_progress_events"] = events
    events.append(
        {
            "id": f"runtime-progress-{len(events) + 1}",
            "current_agent": current_agent,
            "message": message,
        }
    )


def _append_runtime_progress_event(
    state: dict[str, Any],
    *,
    current_agent: str,
    message: str,
) -> None:
    append_runtime_progress_event(
        state,
        current_agent=current_agent,
        message=message,
    )
