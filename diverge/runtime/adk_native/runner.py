from __future__ import annotations

import copy
import os
import uuid
from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import BaseNode, FunctionNode, Workflow
from google.genai import types

from diverge.agents.analysts.fundamentals_analyst import FundamentalsAnalyst
from diverge.agents.analysts.market_analyst import MarketAnalyst
from diverge.agents.analysts.news_analyst import NewsAnalyst
from diverge.agents.analysts.social_media_analyst import SocialMediaAnalyst
from diverge.agents.managers.portfolio_manager import PortfolioManager
from diverge.agents.managers.research_manager import ResearchManager
from diverge.agents.researchers.bear_researcher import BearResearcher
from diverge.agents.researchers.bull_researcher import BullResearcher
from diverge.agents.risk_mgmt.aggressive_debator import AggressiveDebator
from diverge.agents.risk_mgmt.conservative_debator import ConservativeDebator
from diverge.agents.risk_mgmt.debate_phase import get_total_risk_turn_limit
from diverge.agents.risk_mgmt.neutral_debator import NeutralDebator
from diverge.agents.trader.trader import Trader
from diverge.analysis.options import ANALYST_ORDER
from diverge.agents.utils.memory import FinancialSituationMemory
from diverge.dataflows.config import set_config
from diverge.default_config import DEFAULT_CONFIG
from diverge.runtime.model_factory import (
    AdkChatModel,
    create_adk_generation_config,
    create_adk_model,
)
from diverge.runtime.adk_native.agents import NativeAnalystAgent, NativeStateAgent
from diverge.runtime.adk_native.progress_adapter import state_delta_from_event
from diverge.runtime.adk_native.state_adapter import merge_state_delta, snapshot_state
from diverge.runtime.adk_native.workflow import build_analysis_workflow
from diverge.runtime.analysis_schema import HISTORICAL_TRADE_FEEDBACK_KEY
from diverge.runtime.tools import create_adk_tool_collections


ADK_NATIVE_RUNTIME_NAME = "adk_native"
_APP_NAME = "diverge_adk_native_analysis"
_USER_ID = "analysis"
_NATIVE_ANALYST_CLASSES = {
    "market": MarketAnalyst,
    "social": SocialMediaAnalyst,
    "news": NewsAnalyst,
    "fundamentals": FundamentalsAnalyst,
}


@dataclass
class _NativeRuntimeResources:
    quick_thinking_llm: Any
    deep_thinking_llm: Any
    tool_nodes: dict[str, Any]
    bull_memory: Any
    bear_memory: Any
    trader_memory: Any
    invest_judge_memory: Any
    portfolio_manager_memory: Any


def stream_analysis_state_chunks(
    *,
    selected_analysts: list[str],
    config: Mapping[str, Any],
    init_agent_state: Mapping[str, Any],
    graph_args: Mapping[str, Any] | None = None,
) -> Generator[dict[str, Any], None, dict[str, Any]]:
    """Stream analysis state through an ADK Runner-managed workflow.

    ADK owns the runner/session/event boundary here. The analysis sequence is
    built from ADK BaseAgent nodes while reusing the existing prompt/tool
    implementations behind those nodes.
    """
    session_id = uuid.uuid4().hex
    initial_snapshot = snapshot_state(init_agent_state)
    session_service = InMemorySessionService()
    session_service.create_session_sync(
        app_name=_APP_NAME,
        user_id=_USER_ID,
        session_id=session_id,
        state=initial_snapshot,
    )

    workflow = build_native_analysis_workflow(
        selected_analysts=selected_analysts,
        config=config,
    )
    runner = Runner(
        app_name=_APP_NAME,
        node=workflow,
        session_service=session_service,
    )
    message = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text=str(initial_snapshot.get("company_of_interest") or "analysis")
            )
        ],
    )

    state = initial_snapshot
    for event in runner.run(
        user_id=_USER_ID,
        session_id=session_id,
        new_message=message,
    ):
        delta = state_delta_from_event(event)
        if not delta:
            continue
        state = merge_state_delta(state, delta)
        yield snapshot_state(state)

    session = session_service.get_session_sync(
        app_name=_APP_NAME,
        user_id=_USER_ID,
        session_id=session_id,
    )
    return snapshot_state(session.state if session is not None else state)


def build_native_analysis_workflow(
    *,
    selected_analysts: Sequence[str],
    config: Mapping[str, Any],
    name: str = _APP_NAME,
    prefix_nodes: Sequence[BaseNode] = (),
) -> Workflow:
    """Build the ADK-native Diverge analysis workflow.

    This is the shared construction boundary used by the Web Workbench runner
    and the standard ADK Web app entrypoint. Keeping it separate from Runner
    setup lets ADK own the app/session surface without duplicating analysis
    orchestration logic.
    """
    native_nodes = build_native_analysis_nodes(
        selected_analysts=selected_analysts,
        config=config,
    )
    return build_analysis_workflow(
        [*prefix_nodes, *native_nodes],
        name=name,
    )


def build_native_analysis_nodes(
    *,
    selected_analysts: Sequence[str],
    config: Mapping[str, Any],
) -> list[BaseNode]:
    """Build ordered ADK workflow nodes for a Diverge analysis run."""
    native_analysts = _ordered_native_analysts(selected_analysts)
    resources = _create_runtime_resources(config)
    native_nodes: list[BaseNode] = []
    for analyst in native_analysts:
        native_nodes.extend(
            [
                NativeAnalystAgent(
                    name=_native_agent_name(analyst),
                    analyst_key=analyst,
                    node=_NATIVE_ANALYST_CLASSES[analyst](resources.quick_thinking_llm),
                    tool_collection=resources.tool_nodes[analyst],
                ),
                FunctionNode(
                    func=_clear_messages,
                    name=f"clear_messages_after_{analyst}",
                ),
            ]
        )

    native_nodes.extend(_build_native_decision_nodes(resources, config))
    return native_nodes


def _ordered_native_analysts(selected_analysts: Sequence[str]) -> list[str]:
    selected = [analyst for analyst in ANALYST_ORDER if analyst in selected_analysts]
    native_analysts = [
        analyst for analyst in selected if analyst in _NATIVE_ANALYST_CLASSES
    ]
    remaining_analysts = [
        analyst for analyst in selected if analyst not in _NATIVE_ANALYST_CLASSES
    ]
    if remaining_analysts:
        raise ValueError(
            f"Unsupported analysts for ADK-native runtime: {remaining_analysts}"
        )
    return native_analysts


def _native_agent_name(analyst: str) -> str:
    if analyst == "social":
        return "social_media_analyst"
    return f"{analyst}_analyst"


def _build_native_decision_nodes(
    resources: _NativeRuntimeResources,
    config: Mapping[str, Any],
) -> list[NativeStateAgent]:
    max_debate_rounds = int(config.get("max_debate_rounds", 1) or 1)
    max_risk_discuss_rounds = int(config.get("max_risk_discuss_rounds", 1) or 1)

    nodes: list[NativeStateAgent] = []
    for round_index in range(max_debate_rounds):
        turn = round_index + 1
        nodes.append(
            _state_agent(
                f"bull_researcher_{turn}",
                BullResearcher(resources.quick_thinking_llm, resources.bull_memory),
            )
        )
        nodes.append(
            _state_agent(
                f"bear_researcher_{turn}",
                BearResearcher(resources.quick_thinking_llm, resources.bear_memory),
            )
        )

    nodes.extend(
        [
            _state_agent(
                "research_manager",
                ResearchManager(
                    resources.deep_thinking_llm,
                    resources.invest_judge_memory,
                ),
            ),
            _state_agent(
                "trader",
                Trader(resources.quick_thinking_llm, resources.trader_memory),
            ),
        ]
    )

    risk_classes = [AggressiveDebator, ConservativeDebator, NeutralDebator]
    total_risk_turns = get_total_risk_turn_limit(max_risk_discuss_rounds)
    for turn_index in range(total_risk_turns):
        risk_cls = risk_classes[turn_index % len(risk_classes)]
        nodes.append(
            _state_agent(
                f"{risk_cls.name}_{turn_index + 1}",
                risk_cls(resources.quick_thinking_llm),
            )
        )

    nodes.extend(
        [
            _state_agent(
                "portfolio_manager",
                PortfolioManager(
                    resources.deep_thinking_llm,
                    resources.portfolio_manager_memory,
                ),
            ),
        ]
    )
    return nodes


def _create_runtime_resources(config: Mapping[str, Any]) -> _NativeRuntimeResources:
    resolved_config = copy.deepcopy(dict(config))
    resolved_config["eval_results_dir"] = (
        resolved_config.get("eval_results_dir")
        or resolved_config.get("results_dir")
        or DEFAULT_CONFIG["eval_results_dir"]
    )
    set_config(resolved_config)
    os.makedirs(resolved_config["data_cache_dir"], exist_ok=True)
    os.makedirs(resolved_config["eval_results_dir"], exist_ok=True)

    llm_kwargs = _provider_kwargs(resolved_config)
    deep_model = create_adk_model(
        provider=resolved_config["llm_provider"],
        model=resolved_config["deep_think_llm"],
        base_url=resolved_config.get("backend_url"),
        **llm_kwargs,
    )
    quick_model = create_adk_model(
        provider=resolved_config["llm_provider"],
        model=resolved_config["quick_think_llm"],
        base_url=resolved_config.get("backend_url"),
        **llm_kwargs,
    )
    generation_config = create_adk_generation_config(
        provider=resolved_config["llm_provider"],
        **llm_kwargs,
    )

    return _NativeRuntimeResources(
        quick_thinking_llm=AdkChatModel(
            quick_model,
            generation_config=generation_config,
        ),
        deep_thinking_llm=AdkChatModel(
            deep_model,
            generation_config=generation_config,
        ),
        tool_nodes=create_adk_tool_collections(),
        bull_memory=FinancialSituationMemory("bull_memory", resolved_config),
        bear_memory=FinancialSituationMemory("bear_memory", resolved_config),
        trader_memory=FinancialSituationMemory("trader_memory", resolved_config),
        invest_judge_memory=FinancialSituationMemory(
            "invest_judge_memory",
            resolved_config,
        ),
        portfolio_manager_memory=FinancialSituationMemory(
            "portfolio_manager_memory",
            resolved_config,
        ),
    )


def _provider_kwargs(config: Mapping[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    provider = str(config.get("llm_provider", "")).lower()

    if provider == "google":
        thinking_level = config.get("google_thinking_level")
        if thinking_level:
            kwargs["thinking_level"] = thinking_level
    elif provider == "openai":
        reasoning_effort = config.get("openai_reasoning_effort")
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
    elif provider == "anthropic":
        effort = config.get("anthropic_effort")
        if effort:
            kwargs["effort"] = effort

    return kwargs


def _state_agent(name: str, node: Any) -> NativeStateAgent:
    return NativeStateAgent(name=name, node=node)


def _clear_messages(ctx):
    messages: list[Any] = []
    trade_feedback = str(ctx.state.get(HISTORICAL_TRADE_FEEDBACK_KEY) or "").strip()
    if trade_feedback:
        messages.append(("human", trade_feedback))
    messages.append(("human", "Continue"))
    ctx.state["messages"] = messages
    return None
