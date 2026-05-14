import os
from collections.abc import Generator
from typing import Any, overload

from diverge.default_config import DEFAULT_CONFIG
from diverge.agents.utils.memory import FinancialSituationMemory
from diverge.dataflows.config import set_config
from diverge.runtime.model_factory import (
    AdkChatModel,
    create_adk_generation_config,
    create_adk_model,
)
from diverge.runtime.state import Propagator
from diverge.runtime.tools import create_adk_tool_collections
from diverge.runtime.workflow_runner import AdkWorkflowRunner


class DivergeGraph:
    """Main class that orchestrates the diverge framework."""

    def __init__(
        self,
        selected_analysts: list[str] | None = None,
        debug=False,
        config: dict[str, Any] | None = None,
        callbacks: list[Any] | None = None,
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
            ),
        )

    def _get_provider_kwargs(self) -> dict[str, Any]:
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

    @overload
    def stream(
        self,
        init_agent_state: dict[str, Any],
        **args: Any,
    ) -> Generator[dict[str, Any], None, None]: ...

    @overload
    def stream(
        self,
        company_name: str,
        trade_date: str,
        output_language: str = "en",
        **args: Any,
    ) -> Generator[dict[str, Any], None, None]: ...

    def stream(
        self,
        init_agent_state_or_company: dict[str, Any] | str,
        trade_date: str | None = None,
        output_language: str = "en",
        **args: Any,
    ) -> Generator[dict[str, Any], None, None]:
        """Stream state snapshots from either an initial state or ticker/date input."""
        init_agent_state, graph_args = self._resolve_run_input(
            init_agent_state_or_company,
            trade_date,
            output_language,
            args,
        )
        yield from self.workflow_runner.stream(init_agent_state, **graph_args)

    @overload
    def invoke(
        self,
        init_agent_state: dict[str, Any],
        **args: Any,
    ) -> dict[str, Any]: ...

    @overload
    def invoke(
        self,
        company_name: str,
        trade_date: str,
        output_language: str = "en",
        **args: Any,
    ) -> dict[str, Any]: ...

    def invoke(
        self,
        init_agent_state_or_company: dict[str, Any] | str,
        trade_date: str | None = None,
        output_language: str = "en",
        **args: Any,
    ) -> dict[str, Any]:
        """Run the workflow from either an initial state or ticker/date input."""
        init_agent_state, graph_args = self._resolve_run_input(
            init_agent_state_or_company,
            trade_date,
            output_language,
            args,
        )
        return self.workflow_runner.invoke(init_agent_state, **graph_args)

    def _resolve_run_input(
        self,
        init_agent_state_or_company: dict[str, Any] | str,
        trade_date: str | None,
        output_language: str,
        args: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if isinstance(init_agent_state_or_company, dict):
            if trade_date is not None:
                raise TypeError(
                    "trade_date is only valid when the first argument is a ticker"
                )
            return init_agent_state_or_company, args

        if trade_date is None:
            raise TypeError(
                "trade_date is required when the first argument is a ticker"
            )

        graph_args = self.propagator.get_graph_args()
        graph_args.update(args)
        return (
            self.propagator.create_initial_state(
                init_agent_state_or_company,
                trade_date,
                output_language,
            ),
            graph_args,
        )
