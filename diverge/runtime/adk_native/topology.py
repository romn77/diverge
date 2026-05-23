from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from diverge.agents.analyst_turn import AnalystTurn
from diverge.agents.managers.portfolio_manager import PORTFOLIO_MANAGER_AGENT
from diverge.agents.managers.research_manager import RESEARCH_MANAGER_AGENT
from diverge.agents.researchers.bear_researcher import BEAR_RESEARCHER_AGENT
from diverge.agents.researchers.bull_researcher import BULL_RESEARCHER_AGENT
from diverge.agents.risk_mgmt.aggressive_debator import AGGRESSIVE_RISK_AGENT
from diverge.agents.risk_mgmt.conservative_debator import CONSERVATIVE_RISK_AGENT
from diverge.agents.risk_mgmt.debate_phase import get_total_risk_turn_limit
from diverge.agents.risk_mgmt.neutral_debator import NEUTRAL_RISK_AGENT
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.agents.trader.trader import TRADER_AGENT
from diverge.runtime.adk_native.specs import (
    NATIVE_ANALYST_AGENTS,
    ordered_native_analysts,
)


ModelTier = Literal["quick", "deep"]


@dataclass(frozen=True, slots=True)
class DecisionTurnSpec:
    turn: StructuredAgentTurn
    model_tier: ModelTier
    node_name: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisTopology:
    analyst_turns: tuple[AnalystTurn, ...]
    decision_turns: tuple[DecisionTurnSpec, ...]


def build_analysis_topology(
    *,
    selected_analysts: Sequence[str],
    config: Mapping[str, object],
) -> AnalysisTopology:
    """Resolve selected analysts and decision-agent ordering for one run."""

    return AnalysisTopology(
        analyst_turns=tuple(
            NATIVE_ANALYST_AGENTS[analyst]
            for analyst in ordered_native_analysts(selected_analysts)
        ),
        decision_turns=build_decision_turn_specs(config),
    )


def build_decision_turn_specs(
    config: Mapping[str, object],
) -> tuple[DecisionTurnSpec, ...]:
    max_debate_rounds = int(config.get("max_debate_rounds", 1) or 1)
    max_risk_discuss_rounds = int(config.get("max_risk_discuss_rounds", 1) or 1)

    specs: list[DecisionTurnSpec] = []
    for round_index in range(max_debate_rounds):
        turn_number = round_index + 1
        for agent_turn in (BULL_RESEARCHER_AGENT, BEAR_RESEARCHER_AGENT):
            specs.append(
                DecisionTurnSpec(
                    turn=agent_turn,
                    model_tier="quick",
                    node_name=f"{agent_turn.agent_name}_{turn_number}",
                )
            )

    specs.extend(
        [
            DecisionTurnSpec(RESEARCH_MANAGER_AGENT, "deep"),
            DecisionTurnSpec(TRADER_AGENT, "quick"),
        ]
    )

    risk_turns = (AGGRESSIVE_RISK_AGENT, CONSERVATIVE_RISK_AGENT, NEUTRAL_RISK_AGENT)
    total_risk_turns = get_total_risk_turn_limit(max_risk_discuss_rounds)
    for turn_index in range(total_risk_turns):
        agent_turn = risk_turns[turn_index % len(risk_turns)]
        specs.append(
            DecisionTurnSpec(
                turn=agent_turn,
                model_tier="quick",
                node_name=f"{agent_turn.agent_name}_{turn_index + 1}",
            )
        )

    specs.append(DecisionTurnSpec(PORTFOLIO_MANAGER_AGENT, "deep"))
    return tuple(specs)
