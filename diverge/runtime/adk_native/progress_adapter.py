from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def state_delta_from_event(event: Any) -> dict[str, Any]:
    """Extract ADK Event state deltas without coupling callers to ADK internals."""
    actions = getattr(event, "actions", None)
    state_delta = getattr(actions, "state_delta", None)
    if isinstance(state_delta, Mapping):
        return dict(state_delta)

    direct_delta = getattr(event, "state_delta", None)
    if isinstance(direct_delta, Mapping):
        return dict(direct_delta)

    return {}
