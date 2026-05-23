from __future__ import annotations

import json
from typing import Any

from google.genai import types

from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.runtime.structured_output import (
    fallback_structured_output,
    repair_structured_output,
    structured_output_warning,
)


def append_runtime_warning(state: dict[str, Any], warning: dict[str, str]) -> None:
    runtime_warnings = list(state.get("runtime_warnings") or [])
    runtime_warnings.append(warning)
    state["runtime_warnings"] = runtime_warnings


def structured_after_model_callback(output_schema: Any, display_name: str):
    def callback(callback_context, llm_response):
        return _repair_or_replace_structured_response(
            callback_context=callback_context,
            llm_response=llm_response,
            output_schema=output_schema,
            display_name=display_name,
        )

    return callback


def structured_model_error_callback(output_schema: Any, display_name: str):
    def callback(callback_context, llm_request, error: Exception):
        del llm_request
        if not is_transient_llm_error(error):
            return None

        append_runtime_warning(
            callback_context.state,
            transient_llm_warning(display_name, error),
        )
        structured = fallback_structured_output(output_schema, "", display_name)
        return llm_response_from_structured(structured)

    return callback


def evidence_model_error_callback(
    output_key: str,
    display_name: str,
):
    def callback(callback_context, llm_request, error: Exception):
        del llm_request
        if not is_transient_llm_error(error):
            return None

        append_runtime_warning(
            callback_context.state,
            transient_llm_warning(display_name, error),
        )
        notes = (
            f"{display_name} could not complete because the LLM request failed "
            "with a transient connection error. Treat the final report as "
            "data-insufficient unless regenerated."
        )
        callback_context.state[output_key] = notes
        return llm_response_from_text(notes)

    return callback


def turn_after_model_callback(turn: StructuredAgentTurn):
    def callback(callback_context, llm_response):
        return _repair_or_replace_structured_response(
            callback_context=callback_context,
            llm_response=llm_response,
            output_schema=turn.output_schema,
            display_name=turn.display_name,
            invalid_response_warning=turn.invalid_response_warning,
            fallback_from_invalid_response=turn.fallback_from_invalid_response,
        )

    return callback


def turn_model_error_callback(turn: StructuredAgentTurn):
    def callback(callback_context, llm_request, error: Exception):
        del llm_request
        is_transient = turn.is_transient_error or is_transient_llm_error
        if not is_transient(error):
            return None

        warning = (
            turn.transient_error_warning(error)
            if turn.transient_error_warning is not None
            else transient_llm_warning(turn.display_name, error)
        )
        append_runtime_warning(callback_context.state, warning)
        if turn.fallback_from_transient_error is not None:
            structured = turn.fallback_from_transient_error(
                callback_context.state,
                error,
            )
        else:
            structured = fallback_structured_output(
                turn.output_schema,
                "",
                turn.display_name,
            )
        return llm_response_from_structured(structured)

    return callback


def _repair_or_replace_structured_response(
    *,
    callback_context,
    llm_response,
    output_schema: Any,
    display_name: str,
    invalid_response_warning: Any | None = None,
    fallback_from_invalid_response: Any | None = None,
):
    if getattr(llm_response, "partial", False):
        return None
    if llm_response_has_function_call(llm_response):
        return None

    raw_response = llm_response_text(llm_response)
    try:
        output_schema.model_validate_json(raw_response)
    except Exception as exc:
        repaired = repair_structured_output(output_schema, raw_response)
        if repaired is not None:
            return llm_response_from_structured(repaired)
        warning = (
            invalid_response_warning(exc)
            if invalid_response_warning is not None
            else structured_output_warning(display_name, exc)
        )
        append_runtime_warning(callback_context.state, warning)
        structured = (
            fallback_from_invalid_response(raw_response, exc)
            if fallback_from_invalid_response is not None
            else fallback_structured_output(output_schema, raw_response, display_name)
        )
        return llm_response_from_structured(structured)
    return None


def is_transient_llm_error(error: BaseException) -> bool:
    status_code = _error_status_code(error)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True

    message = str(error).lower()
    return (
        "gateway time-out" in message
        or "gateway timeout" in message
        or "connection error" in message
        or "connection reset" in message
        or "unexpected_eof_while_reading" in message
        or "eof occurred in violation of protocol" in message
        or "timed out" in message
        or "timeout" in message
        or "temporarily unavailable" in message
    )


def transient_llm_warning(stage: str, error: BaseException) -> dict[str, str]:
    error_note = str(error).strip()[:500] or error.__class__.__name__
    return {
        "stage": stage,
        "kind": "transient_llm_error",
        "message": (
            f"{stage} used a conservative fallback because the LLM request "
            f"failed with a transient connection error: {error_note}"
        ),
    }


def _error_status_code(error: BaseException) -> int | None:
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


def llm_response_text(response) -> str:
    content = getattr(response, "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(str(part.text) for part in parts if getattr(part, "text", None))


def llm_response_has_function_call(response) -> bool:
    content = getattr(response, "content", None)
    parts = getattr(content, "parts", None) or []
    return any(getattr(part, "function_call", None) for part in parts)


def llm_response_from_structured(structured: Any):
    payload = json.dumps(structured.model_dump(mode="json"), ensure_ascii=False)
    return llm_response_from_text(payload)


def llm_response_from_text(text: str):
    from google.adk.models.llm_response import LlmResponse

    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)],
        )
    )
