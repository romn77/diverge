from __future__ import annotations

import copy
import json
import os
import uuid
from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import BaseNode, FunctionNode, Workflow
from google.genai import types

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
    PortfolioManagerStructuredOutput,
    build_portfolio_manager_prompt,
    build_portfolio_manager_result_from_structured,
    is_transient_portfolio_llm_error,
    portfolio_structured_output_warning,
    portfolio_transient_llm_warning,
    structured_fallback_from_invalid_response,
    structured_fallback_from_transient_error,
)
from diverge.agents.report_output import (
    AggressiveRiskStructuredOutput,
    BearCaseStructuredOutput,
    BullCaseStructuredOutput,
    ConservativeRiskStructuredOutput,
    FundamentalsReportStructuredOutput,
    MarketReportStructuredOutput,
    NeutralRiskStructuredOutput,
    NewsReportStructuredOutput,
    ResearchDecisionStructuredOutput,
    SentimentReportStructuredOutput,
    TraderStructuredOutput,
)
from diverge.agents.managers.research_manager import (
    build_research_manager_prompt,
    build_research_manager_result,
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
from diverge.agents.risk_mgmt.debate_phase import get_total_risk_turn_limit
from diverge.agents.risk_mgmt.neutral_debator import (
    build_neutral_risk_prompt,
    build_neutral_risk_result,
)
from diverge.agents.trader.trader import build_trader_prompt, build_trader_result
from diverge.agents.utils.agent_utils import build_instrument_context
from diverge.analysis.options import ANALYST_ORDER
from diverge.agents.utils.memory import FinancialSituationMemory
from diverge.dataflows.config import set_config
from diverge.default_config import DEFAULT_CONFIG
from diverge.research.search.session import current_search_context
from diverge.runtime.model_factory import (
    create_adk_generation_config,
    create_adk_model,
)
from diverge.runtime.adk_native.agents import append_runtime_progress_event
from diverge.runtime.adk_native.progress_adapter import state_delta_from_event
from diverge.runtime.adk_native.state_adapter import merge_state_delta, snapshot_state
from diverge.runtime.adk_native.workflow import build_analysis_workflow
from diverge.runtime.analysis_schema import HISTORICAL_TRADE_FEEDBACK_KEY
from diverge.runtime.tool_loop import contextual_tool_args, normalize_tool_args
from diverge.runtime.tools import create_adk_tool_collections


ADK_NATIVE_RUNTIME_NAME = "adk_native"
_APP_NAME = "diverge_adk_native_analysis"
_USER_ID = "analysis"
_NATIVE_ANALYST_SPECS = {
    "market": {
        "display_name": "Market Analyst",
        "output_schema": MarketReportStructuredOutput,
        "output_key": "market_report_structured",
        "build_prompt": build_market_analyst_prompt,
        "build_result": build_market_analyst_result,
    },
    "social": {
        "display_name": "Social Analyst",
        "output_schema": SentimentReportStructuredOutput,
        "output_key": "sentiment_report_structured",
        "build_prompt": build_social_media_analyst_prompt,
        "build_result": build_social_media_analyst_result,
    },
    "news": {
        "display_name": "News Analyst",
        "output_schema": NewsReportStructuredOutput,
        "output_key": "news_report_structured",
        "build_prompt": build_news_analyst_prompt,
        "build_result": build_news_analyst_result,
    },
    "fundamentals": {
        "display_name": "Fundamentals Analyst",
        "output_schema": FundamentalsReportStructuredOutput,
        "output_key": "fundamentals_report_structured",
        "build_prompt": build_fundamentals_analyst_prompt,
        "build_result": build_fundamentals_analyst_result,
    },
}
_NATIVE_SEARCH_CONTEXT_TOKENS: dict[str, Any] = {}


@dataclass
class _NativeRuntimeResources:
    tool_nodes: dict[str, Any]
    bull_memory: Any
    bear_memory: Any
    trader_memory: Any
    invest_judge_memory: Any
    portfolio_manager_memory: Any
    quick_model: Any | None = None
    deep_model: Any | None = None
    generation_config: Any | None = None


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
        native_nodes.extend(_build_native_analyst_nodes(analyst, resources))
        native_nodes.extend(
            [
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
    native_analysts = [analyst for analyst in selected if analyst in _NATIVE_ANALYST_SPECS]
    remaining_analysts = [
        analyst for analyst in selected if analyst not in _NATIVE_ANALYST_SPECS
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


def _build_native_analyst_nodes(
    analyst: str,
    resources: _NativeRuntimeResources,
) -> list[BaseNode]:
    spec = _NATIVE_ANALYST_SPECS[analyst]
    model = _native_model(resources.quick_model, f"{spec['display_name']}")
    output_schema = spec["output_schema"]
    output_key = str(spec["output_key"])
    display_name = str(spec["display_name"])
    build_prompt = spec["build_prompt"]
    build_result = spec["build_result"]
    return [
        FunctionNode(
            func=_start_native_state_llm_turn(display_name),
            name=f"{_native_agent_name(analyst)}_start",
        ),
        LlmAgent(
            name=_native_agent_name(analyst),
            model=model,
            instruction=_native_prompt_instruction(build_prompt),
            tools=list(resources.tool_nodes[analyst].tools),
            output_schema=output_schema,
            output_key=output_key,
            generate_content_config=resources.generation_config,
            include_contents="none",
            before_tool_callback=_native_analyst_before_tool_callback(
                build_prompt=build_prompt,
                display_name=display_name,
            ),
            after_tool_callback=_native_analyst_after_tool_callback(display_name),
            on_tool_error_callback=_native_analyst_tool_error_callback(display_name),
            after_model_callback=_native_structured_after_model_callback(
                output_schema,
                display_name,
            ),
        ),
        FunctionNode(
            func=_finalize_native_state_llm_turn(
                build_prompt=build_prompt,
                build_result=build_result,
                output_key=output_key,
                display_name=display_name,
            ),
            name=f"{_native_agent_name(analyst)}_finalize",
        ),
    ]


def _build_native_decision_nodes(
    resources: _NativeRuntimeResources,
    config: Mapping[str, Any],
) -> list[BaseNode]:
    max_debate_rounds = int(config.get("max_debate_rounds", 1) or 1)
    max_risk_discuss_rounds = int(config.get("max_risk_discuss_rounds", 1) or 1)

    nodes: list[BaseNode] = []
    quick_model = _native_model(
        resources.quick_model,
        "quick-thinking decision agents",
    )
    deep_model = _native_model(
        resources.deep_model,
        "deep-thinking decision agents",
    )
    for round_index in range(max_debate_rounds):
        turn = round_index + 1
        nodes.extend(
            _build_native_state_llm_nodes(
                name=f"bull_researcher_{turn}",
                display_name="Bull Researcher",
                build_prompt=_with_memory(
                    build_bull_researcher_prompt,
                    resources.bull_memory,
                ),
                build_result=build_bull_researcher_result,
                model=quick_model,
                output_schema=BullCaseStructuredOutput,
                output_key="bull_case_structured",
                generation_config=resources.generation_config,
            )
        )
        nodes.extend(
            _build_native_state_llm_nodes(
                name=f"bear_researcher_{turn}",
                display_name="Bear Researcher",
                build_prompt=_with_memory(
                    build_bear_researcher_prompt,
                    resources.bear_memory,
                ),
                build_result=build_bear_researcher_result,
                model=quick_model,
                output_schema=BearCaseStructuredOutput,
                output_key="bear_case_structured",
                generation_config=resources.generation_config,
            )
        )

    nodes.extend(
        [
            *_build_native_state_llm_nodes(
                name="research_manager",
                display_name="Research Manager",
                build_prompt=_with_memory(
                    build_research_manager_prompt,
                    resources.invest_judge_memory,
                ),
                build_result=build_research_manager_result,
                model=deep_model,
                output_schema=ResearchDecisionStructuredOutput,
                output_key="research_decision_structured",
                generation_config=resources.generation_config,
            ),
            *_build_native_state_llm_nodes(
                name="trader",
                display_name="Trader",
                build_prompt=_with_memory(
                    build_trader_prompt,
                    resources.trader_memory,
                ),
                build_result=build_trader_result,
                model=quick_model,
                output_schema=TraderStructuredOutput,
                output_key="trader_structured",
                generation_config=resources.generation_config,
            ),
        ]
    )

    risk_specs = [
        (
            "aggressive_analyst",
            "Aggressive Analyst",
            AggressiveRiskStructuredOutput,
            "risk_aggressive_structured",
            build_aggressive_risk_prompt,
            build_aggressive_risk_result,
        ),
        (
            "conservative_analyst",
            "Conservative Analyst",
            ConservativeRiskStructuredOutput,
            "risk_conservative_structured",
            build_conservative_risk_prompt,
            build_conservative_risk_result,
        ),
        (
            "neutral_analyst",
            "Neutral Analyst",
            NeutralRiskStructuredOutput,
            "risk_neutral_structured",
            build_neutral_risk_prompt,
            build_neutral_risk_result,
        ),
    ]
    total_risk_turns = get_total_risk_turn_limit(max_risk_discuss_rounds)
    for turn_index in range(total_risk_turns):
        (
            agent_name,
            display_name,
            output_schema,
            output_key,
            build_prompt,
            build_result,
        ) = risk_specs[turn_index % len(risk_specs)]
        nodes.extend(
            _build_native_state_llm_nodes(
                name=f"{agent_name}_{turn_index + 1}",
                display_name=display_name,
                build_prompt=build_prompt,
                build_result=build_result,
                model=quick_model,
                output_schema=output_schema,
                output_key=output_key,
                generation_config=resources.generation_config,
            )
        )

    nodes.extend(_build_native_portfolio_manager_nodes(resources))
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
        quick_model=quick_model,
        deep_model=deep_model,
        generation_config=generation_config,
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


def _native_model(model: Any | None, label: str) -> Any:
    if model is not None:
        return model
    raise RuntimeError(f"ADK-native {label} requires a native ADK model")


def _with_memory(build_prompt: Any, memory: Any):
    def prompt(state):
        return build_prompt(state, memory)

    return prompt


def _build_native_state_llm_nodes(
    *,
    name: str,
    display_name: str,
    build_prompt: Any,
    build_result: Any,
    model: Any,
    output_schema: Any,
    output_key: str,
    generation_config: Any | None,
) -> list[BaseNode]:
    return [
        FunctionNode(
            func=_start_native_state_llm_turn(display_name),
            name=f"{name}_start",
        ),
        LlmAgent(
            name=name,
            model=model,
            instruction=_native_prompt_instruction(build_prompt),
            output_schema=output_schema,
            output_key=output_key,
            generate_content_config=generation_config,
            include_contents="none",
            after_model_callback=_native_structured_after_model_callback(
                output_schema,
                display_name,
            ),
        ),
        FunctionNode(
            func=_finalize_native_state_llm_turn(
                build_prompt=build_prompt,
                build_result=build_result,
                output_key=output_key,
                display_name=display_name,
            ),
            name=f"{name}_finalize",
        ),
    ]


def _start_native_state_llm_turn(display_name: str):
    def start(ctx: Context):
        append_runtime_progress_event(
            ctx.state,
            current_agent=display_name,
            message=f"{display_name} started.",
        )
        return None

    return start


def _native_prompt_instruction(build_prompt: Any):
    def instruction(ctx) -> str:
        prompt, _tools, _metadata = build_prompt(snapshot_state(ctx.state))
        if getattr(prompt, "messages", None):
            return prompt.to_string()
        return str(getattr(prompt, "system_message", prompt))

    return instruction


def _finalize_native_state_llm_turn(
    *,
    build_prompt: Any | None = None,
    build_result: Any | None = None,
    output_key: str,
    display_name: str,
):
    def finalize(ctx: Context):
        structured_payload = ctx.state.get(output_key)
        if not structured_payload:
            raise RuntimeError(f"{display_name} did not produce structured state")

        state = snapshot_state(ctx.state)
        if build_prompt is None or build_result is None:
            raise RuntimeError(f"{display_name} has no finalize handler")
        _prompt, _tools, metadata = build_prompt(state)
        result = build_result(
            state,
            response_content=structured_payload,
            tool_calls=[],
            **metadata,
        )
        _merge_result_into_context_state(ctx.state, result or {})
        append_runtime_progress_event(
            ctx.state,
            current_agent=display_name,
            message=f"{display_name} completed.",
        )
        return None

    return finalize


def _merge_result_into_context_state(state: dict[str, Any], result: dict[str, Any]):
    for key, value in result.items():
        if key == "messages":
            continue
        else:
            state[key] = value


def _native_analyst_before_tool_callback(
    *,
    build_prompt: Any,
    display_name: str,
):
    def callback(tool, args: dict[str, Any], tool_context):
        state = snapshot_state(tool_context.state)
        tool_name = str(getattr(tool, "name", "") or "")
        normalized = contextual_tool_args(
            state,
            tool_name,
            normalize_tool_args(args),
        )
        args.clear()
        args.update(normalized)
        append_runtime_progress_event(
            tool_context.state,
            current_agent=display_name,
            message=f"{display_name} requested tool: {tool_name or 'unknown tool'}.",
        )

        if tool_name == "web_search_evidence":
            parent_context = current_search_context.get()
            if parent_context is not None:
                _prompt, _tools, metadata = build_prompt(state)
                metadata = dict(metadata or {})
                metadata.pop("earnings_report_section", None)
                token = current_search_context.set(
                    parent_context.model_copy(update=metadata)
                )
                _NATIVE_SEARCH_CONTEXT_TOKENS[
                    _tool_context_token_key(tool_context, tool_name)
                ] = token
        return None

    return callback


def _native_analyst_after_tool_callback(display_name: str):
    def callback(tool, args: dict[str, Any], tool_context, tool_response):
        del args
        tool_name = str(getattr(tool, "name", "") or "")
        _reset_search_context_token(tool_context, tool_name)
        response_length = len(str(tool_response))
        append_runtime_progress_event(
            tool_context.state,
            current_agent=display_name,
            message=(
                f"{display_name} tool result ready: "
                f"{tool_name or 'unknown tool'} returned {response_length} chars."
            ),
        )
        return None

    return callback


def _native_analyst_tool_error_callback(display_name: str):
    def callback(tool, args: dict[str, Any], tool_context, error: Exception):
        del args
        tool_name = str(getattr(tool, "name", "") or "")
        _reset_search_context_token(tool_context, tool_name)
        append_runtime_progress_event(
            tool_context.state,
            current_agent=display_name,
            message=f"{display_name} tool failed: {tool_name or 'unknown tool'}.",
        )
        return {"error": f"Tool `{tool_name or 'unknown tool'}` failed: {error}"}

    return callback


def _reset_search_context_token(tool_context, tool_name: str) -> None:
    key = _tool_context_token_key(tool_context, tool_name)
    token = _NATIVE_SEARCH_CONTEXT_TOKENS.pop(key, None)
    if token is None:
        return
    try:
        current_search_context.reset(token)
    except ValueError:
        pass


def _tool_context_token_key(tool_context, tool_name: str) -> str:
    return str(
        getattr(tool_context, "function_call_id", "")
        or f"{getattr(tool_context, 'invocation_id', '')}:{tool_name}"
    )


def _native_structured_after_model_callback(output_schema: Any, display_name: str):
    def callback(callback_context, llm_response):
        if getattr(llm_response, "partial", False):
            return None
        if _llm_response_has_function_call(llm_response):
            return None

        raw_response = _llm_response_text(llm_response)
        try:
            output_schema.model_validate_json(raw_response)
        except Exception as exc:
            _append_runtime_warning(
                callback_context.state,
                _structured_output_warning(display_name, exc),
            )
            structured = _fallback_structured_output(
                output_schema,
                raw_response,
                display_name,
            )
            return _llm_response_from_structured(structured)
        return None

    return callback


def _structured_output_warning(stage: str, error: BaseException) -> dict[str, str]:
    error_note = str(error).strip()[:500] or error.__class__.__name__
    return {
        "stage": stage,
        "kind": "structured_output_validation_failed",
        "message": (
            f"{stage} response did not match the ADK output schema; "
            "using a conservative schema-valid fallback. "
            f"Error type: {error.__class__.__name__}; detail: {error_note}"
        ),
    }


def _fallback_structured_output(output_schema: Any, raw_response: str, stage: str):
    report = (raw_response or "").strip()
    if not report:
        report = (
            f"## {stage} Fallback\n\n"
            "The model response was empty or invalid, so Diverge generated a "
            "conservative schema-validation fallback."
        )
    summary = (
        f"{stage} returned a response that could not be validated against the "
        "structured output schema."
    )
    common = {
        "signal": "HOLD",
        "signal_confidence": "low",
        "summary": summary,
        "evidence_blocks": [],
        "unknowns": ["Original model response failed structured validation."],
    }
    if output_schema is MarketReportStructuredOutput:
        highlights = {
            **common,
            "category": "market",
            "stance": "neutral",
            "trend_direction": "neutral",
            "key_levels": {"support": [], "resistance": []},
            "indicators": [],
            "volatility": None,
        }
    elif output_schema is FundamentalsReportStructuredOutput:
        highlights = {
            **common,
            "category": "fundamentals",
            "stance": "neutral",
            "metrics": [],
            "financial_health": None,
        }
    elif output_schema is SentimentReportStructuredOutput:
        highlights = {
            **common,
            "category": "sentiment",
            "stance": "neutral",
            "overall_sentiment": "neutral",
            "sentiment_score": None,
            "key_topics": [],
            "social_buzz": None,
        }
    elif output_schema is NewsReportStructuredOutput:
        highlights = {
            **common,
            "category": "news",
            "stance": "neutral",
            "market_impact": "neutral",
            "key_events": [],
            "macro_outlook": None,
        }
    elif output_schema is BullCaseStructuredOutput:
        highlights = {
            **common,
            "category": "bull_case",
            "stance": "bullish",
            "contrary_evidence": [],
            "key_arguments": [],
            "counterpoints": [],
        }
    elif output_schema is BearCaseStructuredOutput:
        highlights = {
            **common,
            "category": "bear_case",
            "stance": "bearish",
            "contrary_evidence": [],
            "key_arguments": [],
            "counterpoints": [],
        }
    elif output_schema is ResearchDecisionStructuredOutput:
        highlights = {
            **common,
            "category": "research_decision",
            "stance": "neutral",
            "decision": "HOLD",
            "aligned_with": "bull",
            "rationale": "Structured validation failed, so no directional research edge is reliable.",
            "action_items": ["Regenerate a schema-valid research decision."],
        }
    elif output_schema is TraderStructuredOutput:
        highlights = {
            **common,
            "category": "trader",
            "stance": "neutral",
            "entry_exit": {
                "action": "Wait for a schema-valid trading plan.",
                "entry_condition": None,
                "exit_target": None,
                "stop_loss": None,
                "invalidation": "A regenerated response validates against the trading schema.",
                "re_entry": None,
            },
            "position_sizing": "No sizing until the trading plan validates.",
            "risk_budget": "No new risk budget from fallback output.",
            "risk_factors": ["Trading plan structured validation failed."],
        }
    elif output_schema is AggressiveRiskStructuredOutput:
        highlights = _fallback_risk_highlights(
            common,
            category="risk_aggressive",
            stance_label="Aggressive",
            risk_assessment="high",
        )
    elif output_schema is ConservativeRiskStructuredOutput:
        highlights = _fallback_risk_highlights(
            common,
            category="risk_conservative",
            stance_label="Conservative",
            risk_assessment="low",
        )
    elif output_schema is NeutralRiskStructuredOutput:
        highlights = _fallback_risk_highlights(
            common,
            category="risk_neutral",
            stance_label="Neutral",
            risk_assessment="moderate",
        )
    else:
        raise TypeError(f"Unsupported structured output schema: {output_schema!r}")

    return output_schema.model_validate(
        {
            "report_markdown": report,
            "highlights": highlights,
        }
    )


def _fallback_risk_highlights(
    common: dict[str, Any],
    *,
    category: str,
    stance_label: str,
    risk_assessment: str,
) -> dict[str, Any]:
    return {
        **common,
        "category": category,
        "stance": "neutral",
        "stance_label": stance_label,
        "core_argument": "Structured validation failed, so risk posture should stay conservative until regenerated.",
        "risk_assessment": risk_assessment,
        "key_recommendations": ["Regenerate a schema-valid risk debate response."],
        "risk_budget": None,
    }


def _build_native_portfolio_manager_nodes(
    resources: _NativeRuntimeResources,
) -> list[BaseNode]:
    model = _native_model(resources.deep_model, "Portfolio Manager")

    return [
        FunctionNode(
            func=_start_portfolio_manager,
            name="portfolio_manager_start",
        ),
        LlmAgent(
            name="portfolio_manager",
            model=model,
            instruction=_portfolio_manager_instruction(
                resources.portfolio_manager_memory
            ),
            output_schema=PortfolioManagerStructuredOutput,
            output_key="portfolio_decision_structured",
            generate_content_config=resources.generation_config,
            include_contents="none",
            after_model_callback=_portfolio_after_model_callback,
            on_model_error_callback=_portfolio_model_error_callback,
        ),
        FunctionNode(
            func=_finalize_portfolio_manager,
            name="portfolio_manager_finalize",
        ),
    ]


def _portfolio_manager_instruction(memory: Any):
    def instruction(ctx) -> str:
        prompt, _metadata = build_portfolio_manager_prompt(dict(ctx.state), memory)
        return prompt

    return instruction


def _start_portfolio_manager(ctx: Context):
    append_runtime_progress_event(
        ctx.state,
        current_agent="Portfolio Manager",
        message="Portfolio Manager started.",
    )
    return None


def _finalize_portfolio_manager(ctx: Context):
    structured_payload = ctx.state.get("portfolio_decision_structured")
    if not structured_payload:
        raise RuntimeError("Portfolio Manager did not produce structured state")

    result = build_portfolio_manager_result_from_structured(
        state=snapshot_state(ctx.state),
        structured_payload=structured_payload,
    )
    for key, value in result.items():
        ctx.state[key] = value
    append_runtime_progress_event(
        ctx.state,
        current_agent="Portfolio Manager",
        message="Portfolio Manager completed with portfolio decision.",
    )
    return None


def _portfolio_after_model_callback(callback_context, llm_response):
    if getattr(llm_response, "partial", False):
        return None

    raw_response = _llm_response_text(llm_response)

    try:
        PortfolioManagerStructuredOutput.model_validate_json(raw_response)
    except Exception as exc:
        _append_runtime_warning(
            callback_context.state,
            portfolio_structured_output_warning(exc),
        )
        structured = structured_fallback_from_invalid_response(raw_response, exc)
        return _llm_response_from_structured(structured)
    return None


def _portfolio_model_error_callback(callback_context, llm_request, error: Exception):
    del llm_request
    if not is_transient_portfolio_llm_error(error):
        return None

    _append_runtime_warning(
        callback_context.state,
        portfolio_transient_llm_warning(error),
    )
    instrument_context = build_instrument_context(
        callback_context.state["company_of_interest"]
    )
    structured = structured_fallback_from_transient_error(
        instrument_context=instrument_context,
        error=error,
    )
    return _llm_response_from_structured(structured)


def _append_runtime_warning(state: dict[str, Any], warning: dict[str, str]) -> None:
    runtime_warnings = list(state.get("runtime_warnings") or [])
    runtime_warnings.append(warning)
    state["runtime_warnings"] = runtime_warnings


def _llm_response_text(response) -> str:
    content = getattr(response, "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(str(part.text) for part in parts if getattr(part, "text", None))


def _llm_response_has_function_call(response) -> bool:
    content = getattr(response, "content", None)
    parts = getattr(content, "parts", None) or []
    return any(getattr(part, "function_call", None) for part in parts)


def _llm_response_from_structured(structured: Any):
    from google.adk.models.llm_response import LlmResponse

    payload = json.dumps(structured.model_dump(mode="json"), ensure_ascii=False)
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=payload)],
        )
    )


def _clear_messages(ctx):
    messages: list[Any] = []
    trade_feedback = str(ctx.state.get(HISTORICAL_TRADE_FEEDBACK_KEY) or "").strip()
    if trade_feedback:
        messages.append(("human", trade_feedback))
    messages.append(("human", "Continue"))
    ctx.state["messages"] = messages
    return None
