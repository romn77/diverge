from __future__ import annotations

from typing import Any

from diverge.research.search.session import current_search_context
from diverge.runtime.adk_native.agents import append_runtime_progress_event
from diverge.runtime.adk_native.callbacks import append_runtime_warning
from diverge.runtime.adk_native.state_adapter import snapshot_state
from diverge.runtime.tool_loop import contextual_tool_args, normalize_tool_args


_SEARCH_CONTEXT_TOKENS: dict[str, Any] = {}


def analyst_before_tool_callback(
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
                _SEARCH_CONTEXT_TOKENS[
                    _tool_context_token_key(tool_context, tool_name)
                ] = token
        return None

    return callback


def analyst_after_tool_callback(
    display_name: str,
    *,
    evidence_tool_calls_key: str | None = None,
):
    def callback(tool, args: dict[str, Any], tool_context, tool_response):
        del args
        tool_name = str(getattr(tool, "name", "") or "")
        _reset_search_context_token(tool_context, tool_name)
        if evidence_tool_calls_key:
            tool_context.state[evidence_tool_calls_key] = (
                int(tool_context.state.get(evidence_tool_calls_key) or 0) + 1
            )
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


def analyst_tool_error_callback(display_name: str):
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


def finalize_evidence_turn(
    *,
    evidence_output_key: str,
    evidence_tool_calls_key: str,
    display_name: str,
):
    def finalize(ctx):
        notes = str(ctx.state.get(evidence_output_key) or "").strip()
        tool_calls = int(ctx.state.get(evidence_tool_calls_key) or 0)
        if tool_calls <= 0:
            append_runtime_warning(
                ctx.state,
                missing_evidence_warning(display_name),
            )
            notes = (
                "No evidence-gathering tool returned data in the evidence phase. "
                "Treat this report as data-insufficient and avoid unsupported "
                "fresh-news claims."
            )
            ctx.state[evidence_output_key] = notes
        elif not notes:
            notes = (
                "Evidence tools were called, but the evidence agent returned no "
                "usable notes. Treat the final report as data-insufficient."
            )
            ctx.state[evidence_output_key] = notes

        append_runtime_progress_event(
            ctx.state,
            current_agent=display_name,
            message=f"{display_name} completed with {tool_calls} evidence tool call(s).",
        )
        return None

    return finalize


def evidence_tool_calls_state_key(output_key: str) -> str:
    return f"{output_key.removesuffix('_structured')}_evidence_tool_calls"


def missing_evidence_warning(stage: str) -> dict[str, str]:
    return {
        "stage": stage,
        "kind": "missing_evidence_tool_call",
        "message": (
            f"{stage} did not complete any evidence-gathering tool call; "
            "the report phase will receive a data-insufficient evidence note."
        ),
    }


def _reset_search_context_token(tool_context, tool_name: str) -> None:
    key = _tool_context_token_key(tool_context, tool_name)
    token = _SEARCH_CONTEXT_TOKENS.pop(key, None)
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
