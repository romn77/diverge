from __future__ import annotations

from typing import Any

from diverge.agents.report_output import (
    merge_structured_agent_output,
    render_markdown_with_highlights,
)
from diverge.runtime.structured_output import parse_structured_output


def render_structured_report(structured_payload: Any, schema: Any) -> str:
    structured = parse_structured_output(structured_payload, schema)
    return render_markdown_with_highlights(
        structured.report_markdown,
        structured.highlights,
    )


def merge_structured_output(
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    agent_name: str,
    schema: Any,
    structured_payload: Any,
) -> None:
    structured = parse_structured_output(structured_payload, schema)
    result["structured_agent_outputs"] = merge_structured_agent_output(
        state,
        agent_name=agent_name,
        payload=structured.model_dump(mode="json"),
    )
