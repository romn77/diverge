from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


def merge_state_delta(
    state: Mapping[str, Any],
    delta: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a full state snapshot after applying an ADK state delta."""
    merged = copy.deepcopy(dict(state))
    if not delta:
        return merged
    for key, value in delta.items():
        merged[str(key)] = value
    return merged


def snapshot_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Best-effort copy used before yielding state to legacy progress code."""
    raw_value = getattr(state, "_value", None)
    if isinstance(raw_value, Mapping):
        try:
            return copy.deepcopy(dict(raw_value))
        except Exception:
            return dict(raw_value)

    try:
        return copy.deepcopy(dict(state))
    except Exception:
        return dict(state)
