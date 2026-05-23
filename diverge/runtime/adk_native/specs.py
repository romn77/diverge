from __future__ import annotations

from collections.abc import Mapping, Sequence

from diverge.agents.analyst_turn import AnalystTurn
from diverge.agents.analysts.fundamentals_analyst import FUNDAMENTALS_ANALYST_AGENT
from diverge.agents.analysts.market_analyst import MARKET_ANALYST_AGENT
from diverge.agents.analysts.news_analyst import NEWS_ANALYST_AGENT
from diverge.agents.analysts.social_media_analyst import (
    SOCIAL_MEDIA_ANALYST_AGENT,
)
from diverge.analysis.options import ANALYST_ORDER


NATIVE_ANALYST_AGENTS: Mapping[str, AnalystTurn] = {
    MARKET_ANALYST_AGENT.analyst_key: MARKET_ANALYST_AGENT,
    SOCIAL_MEDIA_ANALYST_AGENT.analyst_key: SOCIAL_MEDIA_ANALYST_AGENT,
    NEWS_ANALYST_AGENT.analyst_key: NEWS_ANALYST_AGENT,
    FUNDAMENTALS_ANALYST_AGENT.analyst_key: FUNDAMENTALS_ANALYST_AGENT,
}


def ordered_native_analysts(selected_analysts: Sequence[str]) -> list[str]:
    selected = [analyst for analyst in ANALYST_ORDER if analyst in selected_analysts]
    native_analysts = [
        analyst for analyst in selected if analyst in NATIVE_ANALYST_AGENTS
    ]
    remaining_analysts = [
        analyst for analyst in selected if analyst not in NATIVE_ANALYST_AGENTS
    ]
    if remaining_analysts:
        raise ValueError(
            f"Unsupported analysts for ADK-native runtime: {remaining_analysts}"
        )
    return native_analysts
