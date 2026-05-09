# Diverge/graph/trading_graph.py

import os
from pathlib import Path
import json
from typing import Dict, Any, List, Optional

from diverge.default_config import DEFAULT_CONFIG
from diverge.agents.utils.memory import FinancialSituationMemory
from diverge.dataflows.config import set_config
from diverge.runtime import (
    AdkChatModel,
    AdkWorkflowRunner,
    Propagator,
    create_adk_generation_config,
    create_adk_model,
    create_adk_tool_collections,
)
from .reflection import Reflector
from .signal_processing import SignalProcessor


class DivergeGraph:
    """Main class that orchestrates the diverge framework."""

    def __init__(
        self,
        selected_analysts: Optional[List[str]] = None,
        debug=False,
        config: Optional[Dict[str, Any]] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the diverge graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        if selected_analysts is None:
            selected_analysts = ["market", "social", "news", "fundamentals"]
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []
        self.config["eval_results_dir"] = (
            self.config.get("eval_results_dir")
            or self.config.get("results_dir")
            or DEFAULT_CONFIG["eval_results_dir"]
        )

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["eval_results_dir"], exist_ok=True)

        # Initialize ADK 2.0 models with provider-specific configuration.
        llm_kwargs = self._get_provider_kwargs()
        deep_model = create_adk_model(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_model = create_adk_model(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        generation_config = create_adk_generation_config(
            provider=self.config["llm_provider"],
            **llm_kwargs,
        )

        self.deep_thinking_llm = AdkChatModel(
            deep_model,
            generation_config=generation_config,
        )
        self.quick_thinking_llm = AdkChatModel(
            quick_model,
            generation_config=generation_config,
        )

        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory(
            "invest_judge_memory", self.config
        )
        self.portfolio_manager_memory = FinancialSituationMemory(
            "portfolio_manager_memory", self.config
        )

        # Create ADK tool collections
        self.tool_nodes = self._create_tool_nodes()

        max_debate_rounds = self.config.get(
            "max_debate_rounds", DEFAULT_CONFIG["max_debate_rounds"]
        )
        max_risk_discuss_rounds = self.config.get(
            "max_risk_discuss_rounds",
            DEFAULT_CONFIG["max_risk_discuss_rounds"],
        )
        self.workflow_runner = AdkWorkflowRunner(
            selected_analysts=selected_analysts,
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

        self.propagator = Propagator(
            max_recur_limit=self.config.get(
                "max_recur_limit",
                DEFAULT_CONFIG["max_recur_limit"],
            )
        )
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for ADK model creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        return kwargs

    def _create_tool_nodes(self):
        """Create ADK tool collections for different data sources."""
        return create_adk_tool_collections()

    def stream(self, init_agent_state: Dict[str, Any], **args):
        """Stream Diverge state snapshots from the ADK workflow runtime."""
        yield from self.workflow_runner.stream(init_agent_state, **args)

    def invoke(self, init_agent_state: Dict[str, Any], **args) -> Dict[str, Any]:
        """Run the ADK workflow runtime and return the final state."""
        return self.workflow_runner.invoke(init_agent_state, **args)

    def propagate(self, company_name, trade_date, output_language="en"):
        """Run the diverge graph for a company on a specific date."""

        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            output_language,
        )
        args = self.propagator.get_graph_args()

        if self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.invoke(init_agent_state, **args)

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_plan": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"][
                    "aggressive_history"
                ],
                "conservative_history": final_state["risk_debate_state"][
                    "conservative_history"
                ],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
            "report_summary": final_state.get("report_summary", ""),
        }

        # Save to file
        directory = (
            Path(self.config["eval_results_dir"]) / self.ticker / "DivergeStrategy_logs"
        )
        directory.mkdir(parents=True, exist_ok=True)

        log_path = directory / f"full_states_log_{trade_date}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict[str(trade_date)], f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_portfolio_manager(
            self.curr_state, returns_losses, self.portfolio_manager_memory
        )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
