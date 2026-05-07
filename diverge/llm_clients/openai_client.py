import json
import logging
import os
import time
from json import JSONDecodeError
from typing import Any, Optional

import openai
from langchain_core.messages import AIMessage, ChatMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import (
    _construct_lc_result_from_responses_api,
    _convert_dict_to_message,
    _handle_openai_bad_request,
    _is_pydantic_class,
)

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

logger = logging.getLogger(__name__)

try:
    from langchain_openai.chat_models.base import _handle_openai_api_error
except ImportError:

    def _handle_openai_api_error(error: openai.APIError) -> None:
        raise error


def _extract_responses_instruction_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text = block.strip()
        elif isinstance(block, dict) and block.get("type") in {"text", "input_text"}:
            text = str(block.get("text", "")).strip()
        else:
            text = ""

        if text:
            parts.append(text)

    return "\n".join(parts)


def _promote_responses_instructions(payload: dict) -> dict:
    if payload.get("instructions"):
        return payload

    input_items = payload.get("input")
    if not isinstance(input_items, list):
        payload["instructions"] = "Follow the user request."
        return payload

    instructions: list[str] = []
    remaining_input: list[Any] = []
    for item in input_items:
        if isinstance(item, dict) and item.get("role") in {"system", "developer"}:
            text = _extract_responses_instruction_text(item.get("content"))
            if text:
                instructions.append(text)
            continue

        remaining_input.append(item)

    payload["instructions"] = (
        "\n\n".join(instructions) if instructions else "Follow the user request."
    )
    payload["input"] = remaining_input
    return payload


def _plain_text_chat_result(text: str, metadata: dict | None = None) -> ChatResult:
    return ChatResult(
        generations=[
            ChatGeneration(
                message=AIMessage(
                    content=text,
                    response_metadata=metadata or {},
                )
            )
        ]
    )


def _iter_sse_data_payloads(text: str) -> list[dict[str, Any]]:
    if "event: response." not in text or "data:" not in text:
        return []

    payloads: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue

        data = "\n".join(data_lines)
        if data == "[DONE]":
            continue

        try:
            payload = json.loads(data)
        except JSONDecodeError:
            continue

        if isinstance(payload, dict):
            payloads.append(payload)

    return payloads


def _parse_tool_call_args(arguments: Any) -> Any:
    if not isinstance(arguments, str):
        return arguments if arguments is not None else {}
    try:
        return json.loads(arguments, strict=False)
    except JSONDecodeError:
        return arguments


def _chat_result_from_sse_text(
    text: str, metadata: dict | None = None
) -> ChatResult | None:
    payloads = _iter_sse_data_payloads(text)
    if not payloads:
        return None

    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    seen_tool_call_ids: set[str] = set()
    response_id: str | None = None
    response_metadata = dict(metadata or {})

    for payload in payloads:
        payload_type = payload.get("type")
        if payload_type == "response.output_text.delta":
            delta = payload.get("delta")
            if isinstance(delta, str):
                content_parts.append(delta)
            continue

        if payload_type == "response.output_text.done":
            text_value = payload.get("text")
            if isinstance(text_value, str) and not content_parts:
                content_parts.append(text_value)
            continue

        if payload_type == "response.output_item.done":
            item = payload.get("item")
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue

            call_id = item.get("call_id") or item.get("id")
            name = item.get("name")
            if not isinstance(call_id, str) or not isinstance(name, str):
                continue
            if call_id in seen_tool_call_ids:
                continue

            seen_tool_call_ids.add(call_id)
            tool_calls.append(
                {
                    "name": name,
                    "args": _parse_tool_call_args(item.get("arguments")),
                    "id": call_id,
                    "type": "tool_call",
                }
            )
            continue

        if payload_type in {"response.completed", "response.incomplete"}:
            response = payload.get("response")
            if not isinstance(response, dict):
                continue

            if isinstance(response.get("id"), str):
                response_id = response["id"]
            for key in ("created_at", "id", "status", "model", "service_tier"):
                if key in response:
                    response_metadata[key] = response[key]

            for item in response.get("output") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "function_call":
                    call_id = item.get("call_id") or item.get("id")
                    name = item.get("name")
                    if (
                        isinstance(call_id, str)
                        and isinstance(name, str)
                        and call_id not in seen_tool_call_ids
                    ):
                        seen_tool_call_ids.add(call_id)
                        tool_calls.append(
                            {
                                "name": name,
                                "args": _parse_tool_call_args(item.get("arguments")),
                                "id": call_id,
                                "type": "tool_call",
                            }
                        )
                elif item.get("type") == "message":
                    for content in item.get("content") or []:
                        if (
                            isinstance(content, dict)
                            and content.get("type") == "output_text"
                            and isinstance(content.get("text"), str)
                            and not content_parts
                        ):
                            content_parts.append(content["text"])

    return ChatResult(
        generations=[
            ChatGeneration(
                message=AIMessage(
                    content="".join(content_parts),
                    id=response_id,
                    response_metadata=response_metadata,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


_RETRYABLE_OPENAI_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


def _coerce_non_negative_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, parsed)


def _coerce_non_negative_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, parsed)


def _error_status_code(error: BaseException) -> int | None:
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


def _is_retryable_openai_error(error: BaseException) -> bool:
    if isinstance(error, (openai.APIConnectionError, openai.APITimeoutError)):
        return True

    status_code = _error_status_code(error)
    if status_code in _RETRYABLE_OPENAI_STATUS_CODES:
        return True

    message = str(error).lower()
    return (
        "gateway time-out" in message
        or "gateway timeout" in message
        or "connection error" in message
        or "connection reset" in message
        or "unexpected_eof_while_reading" in message
        or "eof occurred in violation of protocol" in message
        or "temporarily unavailable" in message
    )


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output.

    The Responses API returns content as a list of typed blocks
    (reasoning, text, etc.). This normalizes to string for consistent
    downstream handling.
    """

    preserve_reasoning_content: bool = False
    ensure_responses_instructions: bool = False
    transient_max_retries: int = 2
    transient_retry_base_delay: float = 1.0
    transient_retry_max_delay: float = 8.0

    def invoke(self, input, config=None, **kwargs):
        max_retries = _coerce_non_negative_int(
            self.transient_max_retries,
            2,
        )
        base_delay = _coerce_non_negative_float(
            self.transient_retry_base_delay,
            1.0,
        )
        max_delay = _coerce_non_negative_float(
            self.transient_retry_max_delay,
            8.0,
        )

        for attempt in range(max_retries + 1):
            try:
                return normalize_content(super().invoke(input, config, **kwargs))
            except Exception as exc:
                if attempt >= max_retries or not _is_retryable_openai_error(exc):
                    raise

                delay = min(max_delay, base_delay * (2**attempt))
                logger.warning(
                    "Retrying transient OpenAI-compatible LLM error "
                    "status=%s attempt=%s/%s delay=%.1fs: %s",
                    _error_status_code(exc),
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                if delay > 0:
                    time.sleep(delay)

    def _ensure_sync_client_available(self) -> None:
        root_client = getattr(self, "root_client", None)
        if root_client is None or getattr(root_client, "responses", None) is None:
            raise ValueError("Responses API requires a synchronous OpenAI client.")

    def _generate(
        self,
        messages,
        stop=None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        if not self.ensure_responses_instructions or not self._use_responses_api(
            payload
        ):
            return super()._generate(
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            )

        self._ensure_sync_client_available()
        generation_info = None
        raw_response = None
        try:
            original_schema_obj = kwargs.get("response_format")
            if original_schema_obj and _is_pydantic_class(original_schema_obj):
                raw_response = self.root_client.responses.with_raw_response.parse(
                    **payload
                )
            else:
                raw_response = self.root_client.responses.with_raw_response.create(
                    **payload
                )
            response = raw_response.parse()
            if self.include_response_headers:
                generation_info = {"headers": dict(raw_response.headers)}
            if isinstance(response, str):
                return _chat_result_from_sse_text(
                    response,
                    generation_info,
                ) or _plain_text_chat_result(response, generation_info)
            return _construct_lc_result_from_responses_api(
                response,
                schema=original_schema_obj,
                metadata=generation_info,
                output_version=self.output_version,
            )
        except openai.BadRequestError as e:
            _handle_openai_bad_request(e)
        except openai.APIError as e:
            _handle_openai_api_error(e)
        except Exception as e:
            if raw_response is not None and hasattr(raw_response, "http_response"):
                e.response = raw_response.http_response
            raise e

    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        if not self.preserve_reasoning_content:
            return result

        response_dict = (
            response if isinstance(response, dict) else response.model_dump()
        )
        choices = response_dict.get("choices") or []
        for generation, choice in zip(result.generations, choices):
            response_message = choice.get("message") or {}
            if isinstance(generation.message, ChatMessage):
                generation.message = _convert_dict_to_message(
                    {**response_message, "role": "assistant"}
                )

            reasoning_content = response_message.get("reasoning_content")
            if reasoning_content:
                generation.message.additional_kwargs["reasoning_content"] = (
                    reasoning_content
                )

        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if self.ensure_responses_instructions:
            payload = _promote_responses_instructions(payload)

        if not self.preserve_reasoning_content:
            return payload

        input_messages = self._convert_input(input_).to_messages()
        for source_message, payload_message in zip(
            input_messages,
            payload.get("messages", []),
        ):
            reasoning_content = getattr(source_message, "additional_kwargs", {}).get(
                "reasoning_content"
            )
            if (
                reasoning_content
                and payload_message.get("role") == "assistant"
                and payload_message.get("tool_calls")
            ):
                payload_message["reasoning_content"] = reasoning_content

        return payload


# Kwargs forwarded from user config to ChatOpenAI
_PASSTHROUGH_KWARGS = (
    "timeout",
    "max_retries",
    "reasoning_effort",
    "api_key",
    "callbacks",
    "http_client",
    "http_async_client",
)

# Provider base URLs and API key env vars
_PROVIDER_CONFIG = {
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "qwen": (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_API_KEY",
    ),
    "glm": ("https://api.z.ai/api/paas/v4/", "ZHIPU_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "siliconflow": ("https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "xiaohumini": ("https://xiaohumini.site/v1", "XIAOHUMINI_API_KEY"),
    "sub2api": ("https://cc.z2blog.com", "SUB2API_API_KEY"),
    "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}

_REASONING_CONTENT_PROVIDERS = {"deepseek", "qwen", "siliconflow", "xiaohumini"}
_RESPONSES_API_PROVIDERS = {"openai", "sub2api"}


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI-compatible providers.

    For native OpenAI models, uses the Responses API (/v1/responses) which
    supports reasoning_effort with function tools across all model families
    (GPT-4.1, GPT-5). Sub2API also uses the Responses wire API. Other
    third-party compatible providers (xAI, OpenRouter, DeepSeek, SiliconFlow,
    XiaoHuMini, Ollama) use standard Chat Completions.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance."""
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        # Provider-specific base URL and auth
        if self.provider in _PROVIDER_CONFIG:
            base_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = base_url
            if api_key_env:
                api_key = os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url

        if self.provider in _REASONING_CONTENT_PROVIDERS:
            llm_kwargs["preserve_reasoning_content"] = True
        if self.provider == "sub2api":
            llm_kwargs["ensure_responses_instructions"] = True

        llm_kwargs["transient_max_retries"] = _coerce_non_negative_int(
            os.environ.get("LLM_TRANSIENT_MAX_RETRIES"),
            2,
        )
        llm_kwargs["transient_retry_base_delay"] = _coerce_non_negative_float(
            os.environ.get("LLM_TRANSIENT_RETRY_BASE_DELAY"),
            1.0,
        )
        llm_kwargs["transient_retry_max_delay"] = _coerce_non_negative_float(
            os.environ.get("LLM_TRANSIENT_RETRY_MAX_DELAY"),
            8.0,
        )

        # Forward user-provided kwargs
        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Native OpenAI: use Responses API for consistent behavior across
        # all model families. Third-party providers use Chat Completions.
        if self.provider in _RESPONSES_API_PROVIDERS:
            llm_kwargs["use_responses_api"] = True

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model(self.provider, self.model)
