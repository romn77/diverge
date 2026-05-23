from __future__ import annotations

from typing import Any

from diverge.agents.debate_state import RiskSpeaker, append_risk_argument
from diverge.agents.structured_commit import (
    merge_structured_output,
    render_structured_report,
)


def commit_risk_debater_output(
    state: dict[str, Any],
    structured_payload: Any,
    *,
    schema: Any,
    agent_name: str,
    speaker_label: str,
    speaker: RiskSpeaker,
) -> dict[str, Any]:
    debate = state["risk_debate_state"]
    rendered = render_structured_report(structured_payload, schema)
    argument = f"{speaker_label}: {rendered}"
    result = {
        "risk_debate_state": append_risk_argument(
            debate,
            speaker=speaker,
            argument=argument,
        )
    }
    merge_structured_output(
        result,
        state,
        agent_name=agent_name,
        schema=schema,
        structured_payload=structured_payload,
    )
    return result
