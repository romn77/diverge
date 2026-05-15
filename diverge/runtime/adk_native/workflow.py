from __future__ import annotations

from typing import Any

from google.adk.workflow import START, Workflow
from google.adk.workflow import BaseNode


def build_analysis_workflow(
    nodes: list[BaseNode],
    *,
    name: str = "diverge_adk_native_analysis",
) -> Workflow:
    """Build a sequential ADK workflow from native analysis nodes."""
    edges: list[tuple[Any, Any]] = []
    previous: Any = START
    for node in nodes:
        edges.append((previous, node))
        previous = node
    return Workflow(
        name=name,
        edges=edges,
        max_concurrency=1,
    )
