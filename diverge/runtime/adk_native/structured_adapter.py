from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.workflow import BaseNode, FunctionNode

from diverge.agents.structured_turn import StructuredAgentTurn


@dataclass(frozen=True, slots=True)
class NativeStructuredAgentAdapterRuntime:
    model: Any
    generation_config: Any | None
    build_prompt: Callable[..., Any]
    start_turn: Callable[[str], Any]
    prompt_instruction: Callable[[Any], Any]
    structured_after_model_callback: Callable[[StructuredAgentTurn], Any]
    model_error_callback: Callable[[StructuredAgentTurn], Any]
    finalize_state_llm_turn: Callable[..., Any]


def build_adk_structured_turn_nodes(
    turn: StructuredAgentTurn,
    runtime: NativeStructuredAgentAdapterRuntime,
    *,
    node_name: str | None = None,
) -> list[BaseNode]:
    name = node_name or turn.agent_name
    return [
        FunctionNode(
            func=runtime.start_turn(turn.display_name),
            name=f"{name}_start",
        ),
        LlmAgent(
            name=name,
            model=runtime.model,
            instruction=runtime.prompt_instruction(runtime.build_prompt),
            output_schema=turn.output_schema,
            output_key=turn.output_key,
            generate_content_config=runtime.generation_config,
            include_contents="none",
            after_model_callback=runtime.structured_after_model_callback(turn),
            on_model_error_callback=runtime.model_error_callback(turn),
        ),
        FunctionNode(
            func=runtime.finalize_state_llm_turn(
                commit_result=turn.commit_output,
                output_key=turn.output_key,
                display_name=turn.display_name,
                output_schema=turn.output_schema,
                fallback_from_invalid_response=turn.fallback_from_invalid_response,
            ),
            name=f"{name}_finalize",
        ),
    ]
