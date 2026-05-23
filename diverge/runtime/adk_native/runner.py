from __future__ import annotations

import copy
import os
import uuid
from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from google.adk.agents.context import Context
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import BaseNode, FunctionNode, Workflow
from google.genai import types

from diverge.agents.analyst_turn import AnalystTurn
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.agents.utils.memory import FinancialSituationMemory
from diverge.dataflows.config import set_config
from diverge.default_config import DEFAULT_CONFIG
from diverge.runtime.model_factory import (
    create_adk_generation_config,
    create_adk_model,
)
from diverge.runtime.adk_native.agents import append_runtime_progress_event
from diverge.runtime.adk_native.analyst_adapter import (
    NativeAnalystAdapterRuntime,
    build_adk_analyst_turn_nodes,
)
from diverge.runtime.adk_native.callbacks import (
    evidence_model_error_callback,
    structured_after_model_callback,
    structured_model_error_callback,
    turn_after_model_callback,
    turn_model_error_callback,
)
from diverge.runtime.adk_native.evidence import (
    analyst_after_tool_callback,
    analyst_before_tool_callback,
    analyst_tool_error_callback,
    evidence_tool_calls_state_key,
    finalize_evidence_turn,
)
from diverge.runtime.adk_native.specs import NATIVE_ANALYST_AGENTS
from diverge.runtime.adk_native.progress_adapter import state_delta_from_event
from diverge.runtime.adk_native.state_adapter import merge_state_delta, snapshot_state
from diverge.runtime.adk_native.structured_adapter import (
    NativeStructuredAgentAdapterRuntime,
    build_adk_structured_turn_nodes,
)
from diverge.runtime.adk_native.topology import (
    DecisionTurnSpec,
    build_analysis_topology,
)
from diverge.runtime.adk_native.workflow import build_analysis_workflow
from diverge.runtime.analysis_schema import HISTORICAL_TRADE_FEEDBACK_KEY
from diverge.runtime.tools import create_adk_tool_collections


ADK_NATIVE_RUNTIME_NAME = "adk_native"
_APP_NAME = "diverge_adk_native_analysis"
_USER_ID = "analysis"


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
    topology = build_analysis_topology(
        selected_analysts=selected_analysts,
        config=config,
    )
    resources = _create_runtime_resources(config)
    native_nodes: list[BaseNode] = []
    for analyst_turn in topology.analyst_turns:
        native_nodes.extend(_build_native_analyst_nodes(analyst_turn, resources))
        native_nodes.extend(
            [
                FunctionNode(
                    func=_clear_messages,
                    name=f"clear_messages_after_{analyst_turn.analyst_key}",
                ),
            ]
        )

    native_nodes.extend(_build_native_decision_nodes(resources, topology.decision_turns))
    return native_nodes


def _build_native_analyst_nodes(
    turn: AnalystTurn,
    resources: _NativeRuntimeResources,
) -> list[BaseNode]:
    model = _native_model(resources.quick_model, turn.display_name)
    return build_adk_analyst_turn_nodes(
        turn,
        NativeAnalystAdapterRuntime(
            model=model,
            generation_config=resources.generation_config,
            tool_nodes=resources.tool_nodes,
            start_turn=_start_native_state_llm_turn,
            evidence_instruction=_native_evidence_prompt_instruction,
            report_instruction=_native_report_prompt_instruction,
            before_tool_callback=analyst_before_tool_callback,
            after_tool_callback=analyst_after_tool_callback,
            tool_error_callback=analyst_tool_error_callback,
            evidence_model_error_callback=evidence_model_error_callback,
            structured_after_model_callback=structured_after_model_callback,
            model_error_callback=structured_model_error_callback,
            finalize_evidence_turn=finalize_evidence_turn,
            finalize_state_llm_turn=_finalize_native_state_llm_turn,
            evidence_tool_calls_state_key=evidence_tool_calls_state_key,
        ),
    )


def _build_native_decision_nodes(
    resources: _NativeRuntimeResources,
    decision_turns: Sequence[DecisionTurnSpec],
) -> list[BaseNode]:
    nodes: list[BaseNode] = []
    quick_model = _native_model(
        resources.quick_model,
        "quick-thinking decision agents",
    )
    deep_model = _native_model(
        resources.deep_model,
        "deep-thinking decision agents",
    )
    models = {"quick": quick_model, "deep": deep_model}
    for spec in decision_turns:
        nodes.extend(
            _build_native_structured_turn_nodes(
                spec.turn,
                resources,
                model=models[spec.model_tier],
                node_name=spec.node_name,
            )
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
        tool_nodes=create_adk_tool_collections(NATIVE_ANALYST_AGENTS),
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


def _build_native_structured_turn_nodes(
    turn: StructuredAgentTurn,
    resources: _NativeRuntimeResources,
    *,
    model: Any,
    node_name: str | None = None,
) -> list[BaseNode]:
    return build_adk_structured_turn_nodes(
        turn,
        NativeStructuredAgentAdapterRuntime(
            model=model,
            generation_config=resources.generation_config,
            build_prompt=_turn_prompt_builder(turn, resources),
            start_turn=_start_native_state_llm_turn,
            prompt_instruction=_native_prompt_instruction,
            structured_after_model_callback=turn_after_model_callback,
            model_error_callback=turn_model_error_callback,
            finalize_state_llm_turn=_finalize_native_state_llm_turn,
        ),
        node_name=node_name,
    )


def _turn_prompt_builder(turn: StructuredAgentTurn, resources: _NativeRuntimeResources):
    if not turn.memory_key:
        return turn.build_prompt
    return _with_memory(turn.build_prompt, getattr(resources, turn.memory_key))


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
        return _prompt_text(build_prompt, snapshot_state(ctx.state))

    return instruction


def _native_evidence_prompt_instruction(
    build_prompt: Any,
    *,
    evidence_output_key: str,
):
    def instruction(ctx) -> str:
        content = _prompt_text(build_prompt, snapshot_state(ctx.state))
        return (
            f"{content}\n\nEvidence phase contract:\n"
            "- This is the evidence-gathering phase, not the final report phase.\n"
            "- Use the available evidence tools before you write final notes.\n"
            "- Return concise evidence notes only: claims, source/tool names, dates, "
            "limitations, and unresolved unknowns.\n"
            "- Do not return JSON, `json-highlights`, or the final user-facing report.\n"
            f"- The runtime stores these notes in state key `{evidence_output_key}` "
            "for the report-only agent."
        )

    return instruction


def _native_report_prompt_instruction(
    build_prompt: Any,
    *,
    evidence_output_key: str,
):
    def instruction(ctx) -> str:
        state = snapshot_state(ctx.state)
        content = _prompt_text(build_prompt, state)
        evidence_notes = str(state.get(evidence_output_key) or "").strip()
        if not evidence_notes:
            evidence_notes = "No evidence notes were produced by the evidence phase."
        return (
            f"{content}\n\nReport phase contract:\n"
            "- This is the final report-formatting phase. You have no tools.\n"
            f"- Use the evidence notes from `{evidence_output_key}` below as the "
            "primary source of facts.\n"
            "- Do not claim that you performed additional tool calls in this phase.\n"
            "- Return only the structured response requested by the runtime schema.\n\n"
            f"Evidence notes:\n{evidence_notes}"
        )

    return instruction


def _prompt_text(build_prompt: Any, state: Mapping[str, Any]) -> str:
    prompt, _tools, _metadata = build_prompt(state)
    if getattr(prompt, "messages", None):
        return prompt.to_string()
    return str(getattr(prompt, "system_message", prompt))


def _finalize_native_state_llm_turn(
    *,
    commit_result: Any,
    output_key: str,
    display_name: str,
):
    def finalize(ctx: Context):
        structured_payload = ctx.state.get(output_key)
        if not structured_payload:
            raise RuntimeError(f"{display_name} did not produce structured state")

        result = commit_result(
            snapshot_state(ctx.state),
            structured_payload,
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


def _clear_messages(ctx):
    messages: list[Any] = []
    trade_feedback = str(ctx.state.get(HISTORICAL_TRADE_FEEDBACK_KEY) or "").strip()
    if trade_feedback:
        messages.append(("human", trade_feedback))
    messages.append(("human", "Continue"))
    ctx.state["messages"] = messages
    return None
