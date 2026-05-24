from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.workflow import BaseNode, FunctionNode

from diverge.agents.analyst_turn import AnalystTurn
from diverge.runtime.tools import AdkToolCollection


@dataclass(frozen=True, slots=True)
class NativeAnalystAdapterRuntime:
    model: Any
    generation_config: Any | None
    tool_nodes: Mapping[str, AdkToolCollection]
    start_turn: Callable[[str], Any]
    evidence_instruction: Callable[..., Any]
    report_instruction: Callable[..., Any]
    before_tool_callback: Callable[..., Any]
    after_tool_callback: Callable[..., Any]
    tool_error_callback: Callable[[str], Any]
    evidence_model_error_callback: Callable[[str, str], Any]
    structured_after_model_callback: Callable[[Any, str], Any]
    model_error_callback: Callable[[Any, str], Any]
    finalize_evidence_turn: Callable[..., Any]
    finalize_state_llm_turn: Callable[..., Any]
    evidence_tool_calls_state_key: Callable[[str], str]


def build_adk_analyst_turn_nodes(
    turn: AnalystTurn,
    runtime: NativeAnalystAdapterRuntime,
) -> list[BaseNode]:
    evidence_tool_calls_key = runtime.evidence_tool_calls_state_key(
        turn.evidence_output_key
    )
    evidence_display_name = f"{turn.display_name} Evidence"
    report_display_name = f"{turn.display_name} Report"

    return [
        FunctionNode(
            func=runtime.start_turn(evidence_display_name),
            name=f"{turn.agent_name}_evidence_start",
        ),
        LlmAgent(
            name=f"{turn.agent_name}_evidence",
            model=runtime.model,
            instruction=runtime.evidence_instruction(
                turn.build_prompt,
                evidence_output_key=turn.evidence_output_key,
            ),
            tools=_tools_for_turn(turn, runtime.tool_nodes),
            output_key=turn.evidence_output_key,
            generate_content_config=runtime.generation_config,
            include_contents="none",
            before_tool_callback=runtime.before_tool_callback(
                build_prompt=turn.build_prompt,
                display_name=evidence_display_name,
            ),
            after_tool_callback=runtime.after_tool_callback(
                evidence_display_name,
                evidence_tool_calls_key=evidence_tool_calls_key,
            ),
            on_tool_error_callback=runtime.tool_error_callback(evidence_display_name),
            on_model_error_callback=runtime.evidence_model_error_callback(
                turn.evidence_output_key,
                evidence_display_name,
            ),
        ),
        FunctionNode(
            func=runtime.finalize_evidence_turn(
                evidence_output_key=turn.evidence_output_key,
                evidence_tool_calls_key=evidence_tool_calls_key,
                display_name=evidence_display_name,
            ),
            name=f"{turn.agent_name}_evidence_finalize",
        ),
        FunctionNode(
            func=runtime.start_turn(report_display_name),
            name=f"{turn.agent_name}_report_start",
        ),
        LlmAgent(
            name=f"{turn.agent_name}_report",
            model=runtime.model,
            instruction=runtime.report_instruction(
                turn.build_prompt,
                evidence_output_key=turn.evidence_output_key,
            ),
            output_schema=turn.output_schema,
            output_key=turn.output_key,
            generate_content_config=runtime.generation_config,
            include_contents="none",
            after_model_callback=runtime.structured_after_model_callback(
                turn.output_schema,
                report_display_name,
            ),
            on_model_error_callback=runtime.model_error_callback(
                turn.output_schema,
                report_display_name,
            ),
        ),
        FunctionNode(
            func=runtime.finalize_state_llm_turn(
                commit_result=turn.commit_output,
                output_key=turn.output_key,
                display_name=report_display_name,
                output_schema=turn.output_schema,
            ),
            name=f"{turn.agent_name}_finalize",
        ),
    ]


def _tools_for_turn(
    turn: AnalystTurn,
    tool_nodes: Mapping[str, AdkToolCollection],
) -> list[Any]:
    collection = tool_nodes[turn.analyst_key]
    tools_by_name = collection.tools_by_name
    missing = [name for name in turn.tool_names if name not in tools_by_name]
    if missing:
        raise KeyError(
            f"{turn.display_name} requested unknown ADK tools: {missing}"
        )
    return [tools_by_name[name] for name in turn.tool_names]
