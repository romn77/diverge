# Diverge/graph/setup.py

from __future__ import annotations

from typing import Any, Optional

from diverge.runtime import AdkWorkflowRunner


class GraphSetup:
    """Compatibility shim for callers that still import the old setup helper."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: dict[str, Any],
        bull_memory: Any,
        bear_memory: Any,
        trader_memory: Any,
        invest_judge_memory: Any,
        portfolio_manager_memory: Any,
        conditional_logic: Any = None,
    ) -> None:
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.portfolio_manager_memory = portfolio_manager_memory
        self.conditional_logic = conditional_logic

    def setup_graph(self, selected_analysts: Optional[list[str]] = None) -> AdkWorkflowRunner:
        selected = selected_analysts or ["market", "social", "news", "fundamentals"]
        max_debate_rounds = getattr(self.conditional_logic, "max_debate_rounds", 1)
        max_risk_discuss_rounds = getattr(
            self.conditional_logic,
            "max_risk_discuss_rounds",
            1,
        )
        return AdkWorkflowRunner(
            selected_analysts=selected,
            quick_llm=self.quick_thinking_llm,
            deep_llm=self.deep_thinking_llm,
            tool_nodes=self.tool_nodes,
            bull_memory=self.bull_memory,
            bear_memory=self.bear_memory,
            trader_memory=self.trader_memory,
            invest_judge_memory=self.invest_judge_memory,
            portfolio_manager_memory=self.portfolio_manager_memory,
            max_debate_rounds=max_debate_rounds,
            max_risk_discuss_rounds=max_risk_discuss_rounds,
        )
