from __future__ import annotations

import inspect

from diverge.agents.analysts.fundamentals_analyst import (
    build_fundamentals_analyst_prompt,
    build_fundamentals_analyst_result,
)
from diverge.agents.analysts.market_analyst import (
    build_market_analyst_prompt,
    build_market_analyst_result,
)
from diverge.agents.analysts.news_analyst import (
    build_news_analyst_prompt,
    build_news_analyst_result,
)
from diverge.agents.analysts.social_media_analyst import (
    build_social_media_analyst_prompt,
    build_social_media_analyst_result,
)
from diverge.agents.managers.portfolio_manager import (
    build_portfolio_manager_prompt,
    build_portfolio_manager_result,
)
from diverge.agents.managers.research_manager import (
    build_research_manager_prompt,
    build_research_manager_result,
)
from diverge.agents.managers.summary_agent import (
    build_summary_agent_prompt,
    build_summary_agent_result,
)
from diverge.agents.researchers.bear_researcher import (
    build_bear_researcher_prompt,
    build_bear_researcher_result,
)
from diverge.agents.researchers.bull_researcher import (
    build_bull_researcher_prompt,
    build_bull_researcher_result,
)
from diverge.agents.risk_mgmt.aggressive_debator import (
    build_aggressive_risk_prompt,
    build_aggressive_risk_result,
)
from diverge.agents.risk_mgmt.conservative_debator import (
    build_conservative_risk_prompt,
    build_conservative_risk_result,
)
from diverge.agents.risk_mgmt.neutral_debator import (
    build_neutral_risk_prompt,
    build_neutral_risk_result,
)
from diverge.agents.trader.trader import build_trader_prompt, build_trader_result


def test_prompt_agents_expose_direct_prompt_and_result_functions():
    functions = [
        build_market_analyst_prompt,
        build_market_analyst_result,
        build_social_media_analyst_prompt,
        build_social_media_analyst_result,
        build_news_analyst_prompt,
        build_news_analyst_result,
        build_fundamentals_analyst_prompt,
        build_fundamentals_analyst_result,
        build_bull_researcher_prompt,
        build_bull_researcher_result,
        build_bear_researcher_prompt,
        build_bear_researcher_result,
        build_research_manager_prompt,
        build_research_manager_result,
        build_trader_prompt,
        build_trader_result,
        build_aggressive_risk_prompt,
        build_aggressive_risk_result,
        build_conservative_risk_prompt,
        build_conservative_risk_result,
        build_neutral_risk_prompt,
        build_neutral_risk_result,
        build_portfolio_manager_prompt,
        build_portfolio_manager_result,
        build_summary_agent_prompt,
        build_summary_agent_result,
    ]

    names = [function.__name__ for function in functions]

    assert len(names) == len(set(names))
    for function in functions:
        assert inspect.isfunction(function)
        assert function.__closure__ is None
