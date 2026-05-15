from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import logging
import os
import queue
import re
import shlex
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Iterable, Optional

from google.genai import Client
from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.tools import FunctionTool
from google.genai import types
from pydantic import Field

from diverge.llm_clients.google_client import (
    resolve_google_api_key,
    resolve_google_base_url,
)
from diverge.runtime.messages import message_content, message_role

logger = logging.getLogger(__name__)

DEFAULT_ADK_MODEL_TIMEOUT_SECONDS = 300.0
ADK_MODEL_TIMEOUT_ENV = "DIVERGE_LLM_TIMEOUT_SECONDS"
ADK_TRANSIENT_MAX_RETRIES_ENV = "LLM_TRANSIENT_MAX_RETRIES"
ADK_TRANSIENT_RETRY_BASE_DELAY_ENV = "LLM_TRANSIENT_RETRY_BASE_DELAY"
ADK_TRANSIENT_RETRY_MAX_DELAY_ENV = "LLM_TRANSIENT_RETRY_MAX_DELAY"
DEFAULT_ADK_TRANSIENT_MAX_RETRIES = 2
DEFAULT_ADK_TRANSIENT_RETRY_BASE_DELAY_SECONDS = 1.0
DEFAULT_ADK_TRANSIENT_RETRY_MAX_DELAY_SECONDS = 8.0
_LITELLM_LOOP_START_TIMEOUT_SECONDS = 5.0
_LITELLM_LOOP_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_RETRYABLE_LLM_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

_litellm_loop_lock = threading.Lock()
_litellm_loop: asyncio.AbstractEventLoop | None = None
_litellm_loop_thread: threading.Thread | None = None
_litellm_loop_queue: queue.Queue[tuple[Any, Future[Any]] | None] | None = None


_OPENAI_COMPATIBLE_PROVIDERS = {
    "ollama",
    "siliconflow",
    "sub2api",
    "xiaohumini",
    "mimo",
}

_LITELLM_PROVIDER_PREFIX = {
    "openai": "openai",
    "anthropic": "anthropic",
    "xai": "xai",
    "openrouter": "openrouter",
    "deepseek": "deepseek",
}

_PROVIDER_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "xiaohumini": "XIAOHUMINI_API_KEY",
    "sub2api": "SUB2API_API_KEY",
    "mimo": "MIMO_API_KEY",
}


class DivergeGemini(Gemini):
    """Gemini model with Diverge runtime overrides for routed endpoints."""

    base_url: Optional[str] = None
    api_key: Optional[str] = Field(default=None, exclude=True, repr=False)

    def _diverge_tracking_headers(self) -> dict[str, str]:
        headers = self._tracking_headers
        if callable(headers):
            headers = headers()
        return dict(headers or {})

    @cached_property
    def api_client(self) -> Client:
        return Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                base_url=self.base_url,
                headers=self._diverge_tracking_headers(),
                retry_options=self.retry_options,
            ),
        )

    @cached_property
    def _live_api_client(self) -> Client:
        return Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                base_url=self.base_url,
                headers=self._diverge_tracking_headers(),
                api_version=self._live_api_version,
            ),
        )


def _prefixed_litellm_model(provider: str, model: str) -> str:
    provider = provider.lower()
    if "/" in model and provider in {"openrouter", "anthropic"}:
        return f"{provider}/{model}"
    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        return f"openai/{model}"
    prefix = _LITELLM_PROVIDER_PREFIX.get(provider)
    if prefix is None:
        raise ValueError(f"Unsupported ADK LiteLLM provider: {provider}")
    return f"{prefix}/{model}"


def _normalize_litellm_api_base(
    provider: str, base_url: Optional[str]
) -> Optional[str]:
    if not base_url:
        return None

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return None

    if provider.lower().strip() == "sub2api" and not normalized.endswith(
        ("/v1", "/api/v1")
    ):
        return f"{normalized}/v1"

    return normalized


def _litellm_kwargs(
    provider: str,
    *,
    base_url: Optional[str],
    api_key: Optional[str],
    timeout: Optional[float],
    max_retries: Optional[int],
    extra: dict[str, Any],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    api_base = _normalize_litellm_api_base(provider, base_url)
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    elif provider in _PROVIDER_API_KEY_ENV:
        env_key = _PROVIDER_API_KEY_ENV[provider]
        if os.getenv(env_key):
            kwargs["api_key"] = os.getenv(env_key)
    if timeout is not None:
        kwargs["timeout"] = timeout
    if max_retries is not None:
        kwargs["num_retries"] = max_retries

    allowed_passthrough = {
        "reasoning_effort",
        "effort",
        "temperature",
        "max_tokens",
        "max_output_tokens",
        "drop_params",
        "custom_llm_provider",
    }
    for key, value in extra.items():
        if value is not None and key in allowed_passthrough:
            kwargs[key] = value

    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        kwargs.setdefault("custom_llm_provider", "openai")
    return kwargs


def _coerce_timeout_seconds(value: Any) -> float | None:
    if value is None:
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{ADK_MODEL_TIMEOUT_ENV} must be a number") from exc
    if timeout <= 0:
        return None
    return timeout


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


def _default_adk_model_timeout_seconds() -> float | None:
    raw_value = os.environ.get(ADK_MODEL_TIMEOUT_ENV)
    if raw_value is None or not raw_value.strip():
        return DEFAULT_ADK_MODEL_TIMEOUT_SECONDS
    return _coerce_timeout_seconds(raw_value.strip())


def _default_adk_transient_max_retries() -> int:
    return _coerce_non_negative_int(
        os.environ.get(ADK_TRANSIENT_MAX_RETRIES_ENV),
        DEFAULT_ADK_TRANSIENT_MAX_RETRIES,
    )


def _default_adk_transient_retry_base_delay_seconds() -> float:
    return _coerce_non_negative_float(
        os.environ.get(ADK_TRANSIENT_RETRY_BASE_DELAY_ENV),
        DEFAULT_ADK_TRANSIENT_RETRY_BASE_DELAY_SECONDS,
    )


def _default_adk_transient_retry_max_delay_seconds() -> float:
    return _coerce_non_negative_float(
        os.environ.get(ADK_TRANSIENT_RETRY_MAX_DELAY_ENV),
        DEFAULT_ADK_TRANSIENT_RETRY_MAX_DELAY_SECONDS,
    )


def _error_status_code(error: BaseException) -> int | None:
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


def _is_retryable_adk_model_error(error: BaseException) -> bool:
    status_code = _error_status_code(error)
    if status_code in _RETRYABLE_LLM_STATUS_CODES:
        return True

    message = str(error).lower()
    return (
        "gateway time-out" in message
        or "gateway timeout" in message
        or "bad gateway" in message
        or "service unavailable" in message
        or "connection error" in message
        or "connection reset" in message
        or "unexpected_eof_while_reading" in message
        or "eof occurred in violation of protocol" in message
        or "temporarily unavailable" in message
    )


def create_adk_model(
    *,
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    **kwargs: Any,
) -> Gemini | LiteLlm:
    """Create the ADK 2.0 model object for Diverge's provider config."""
    provider = provider.lower().strip()
    resolved_timeout = (
        _default_adk_model_timeout_seconds()
        if timeout is None
        else _coerce_timeout_seconds(timeout)
    )
    if provider == "google":
        retry_options = kwargs.get("retry_options")
        resolved_base_url = resolve_google_base_url(base_url)
        resolved_api_key = resolve_google_api_key(api_key)
        gemini_kwargs: dict[str, Any] = {}
        if resolved_base_url:
            gemini_kwargs["base_url"] = resolved_base_url
        if resolved_api_key:
            gemini_kwargs["api_key"] = resolved_api_key
        if retry_options is not None:
            gemini_kwargs["retry_options"] = retry_options
        gemini_cls = DivergeGemini if gemini_kwargs else Gemini
        gemini_model = gemini_cls(model=model, **gemini_kwargs)
        setattr(gemini_model, "_diverge_timeout_seconds", resolved_timeout)
        return gemini_model

    litellm_model = _prefixed_litellm_model(provider, model)
    litellm_kwargs = _litellm_kwargs(
        provider,
        base_url=base_url,
        api_key=api_key,
        timeout=resolved_timeout,
        max_retries=max_retries,
        extra=kwargs,
    )
    model_object = LiteLlm(model=litellm_model, **litellm_kwargs)
    setattr(model_object, "_diverge_timeout_seconds", resolved_timeout)
    return model_object


def create_adk_generation_config(
    *,
    provider: str,
    thinking_level: Optional[str] = None,
    google_thinking_level: Optional[str] = None,
    **_kwargs: Any,
) -> types.GenerateContentConfig | None:
    """Create ADK generation config for provider-specific model controls."""
    if provider.lower().strip() != "google":
        return None

    configured_level = (thinking_level or google_thinking_level or "").strip().upper()
    if not configured_level:
        return None

    try:
        level = types.ThinkingLevel[configured_level]
    except KeyError:
        return None

    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level=level)
    )


def _adk_tools_from_legacy_tools(
    tools: Iterable[Any] | None,
) -> dict[str, FunctionTool]:
    registry: dict[str, FunctionTool] = {}
    for tool in tools or []:
        if isinstance(tool, FunctionTool):
            registry[tool.name] = tool
            continue
        func = getattr(tool, "func", None)
        if callable(func):
            adk_tool = FunctionTool(func)
            registry[adk_tool.name] = adk_tool
            continue
        if callable(tool):
            adk_tool = FunctionTool(tool)
            registry[adk_tool.name] = adk_tool
            continue
        raise TypeError(f"Cannot convert tool to ADK FunctionTool: {tool!r}")
    return registry


def _function_call_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _fallback_tool_call_id(name: str, index: int) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "tool"
    return f"call_{safe_name}_{index}"


def _content_parts_from_message(message: Any) -> list[types.Part]:
    tool_calls = getattr(message, "tool_calls", None) or []
    parts: list[types.Part] = []
    content = message_content(message).strip()
    if content:
        parts.append(types.Part.from_text(text=content))

    for index, tool_call in enumerate(tool_calls, start=1):
        name = str(tool_call.get("name") or "")
        if not name:
            continue
        function_call_part = types.Part.from_function_call(
            name=name,
            args=_function_call_args(tool_call.get("args")),
        )
        tool_call_id = str(tool_call.get("id") or _fallback_tool_call_id(name, index))
        function_call_part.function_call.id = tool_call_id
        parts.append(function_call_part)

    if message.__class__.__name__ == "ToolMessage":
        tool_call_id = str(getattr(message, "tool_call_id", "") or "")
        name = str(getattr(message, "name", "") or tool_call_id or "tool")
        function_response_part = types.Part.from_function_response(
            name=name,
            response={"result": content},
        )
        if tool_call_id:
            function_response_part.function_response.id = tool_call_id
        parts = [function_response_part]

    return parts or [types.Part.from_text(text="")]


def _contents_from_prompt(prompt: Any) -> list[types.Content]:
    if hasattr(prompt, "to_messages"):
        messages = prompt.to_messages()
    elif isinstance(prompt, list):
        messages = prompt
    else:
        messages = [("user", str(prompt))]

    contents: list[types.Content] = []
    for message in messages:
        role = message_role(message)
        if role == "system":
            continue
        parts = _content_parts_from_message(message)
        contents.append(types.Content(role=role, parts=parts))
    return contents


def _system_instruction_from_prompt(prompt: Any) -> str | None:
    if hasattr(prompt, "to_messages"):
        messages = prompt.to_messages()
    elif isinstance(prompt, list):
        messages = prompt
    else:
        return None

    system_messages = [
        message_content(message).strip()
        for message in messages
        if message_role(message) == "system" and message_content(message).strip()
    ]
    return "\n\n".join(system_messages) or None


def _copy_generation_config(
    generation_config: Any,
) -> types.GenerateContentConfig:
    if generation_config is None:
        return types.GenerateContentConfig()
    if hasattr(generation_config, "model_copy"):
        return generation_config.model_copy(deep=True)
    return generation_config


def _set_system_instruction(
    config: types.GenerateContentConfig,
    system_instruction: str | None,
) -> None:
    if not system_instruction:
        return

    existing = config.system_instruction
    if not existing:
        config.system_instruction = system_instruction
    elif isinstance(existing, str):
        config.system_instruction = f"{existing}\n\n{system_instruction}"
    else:
        logger.warning(
            "Skipping prompt system instruction because config already has "
            "non-string system_instruction=%s",
            type(existing).__name__,
        )


def _tool_name(tool: Any) -> str | None:
    name = getattr(tool, "name", None)
    if name:
        return str(name)
    func = getattr(tool, "func", None)
    if callable(func):
        return getattr(func, "__name__", None)
    if callable(tool):
        return getattr(tool, "__name__", None)
    return None


def _bound_tool_names(tools: Iterable[Any] | None) -> set[str]:
    return {name for tool in tools or [] if (name := _tool_name(tool))}


def _coerce_textual_tool_arg(value: str) -> Any:
    cleaned = value.strip().strip(",.;")
    if cleaned.isdigit():
        return int(cleaned)
    return cleaned


def _parse_key_value_tool_args(text: str) -> dict[str, Any]:
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError:
        return {}

    args: dict[str, Any] = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            args[key] = _coerce_textual_tool_arg(value)
    return args


def _first_json_object(text: str) -> tuple[dict[str, Any], int] | None:
    search_text = text[:800]
    for start, char in enumerate(search_text):
        if char != "{":
            continue

        depth = 0
        in_string = False
        escaped = False
        for offset, current in enumerate(search_text[start:], start=start):
            if escaped:
                escaped = False
                continue
            if current == "\\":
                escaped = True
                continue
            if current == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    candidate = search_text[start : offset + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict):
                        return parsed, start
                    break
    return None


def _parse_textual_tool_args(segment: str) -> dict[str, Any]:
    json_object = _first_json_object(segment)
    json_args: dict[str, Any] = {}
    key_value_segment = segment
    if json_object is not None:
        json_args, json_start = json_object
        key_value_segment = segment[:json_start]

    args = _parse_key_value_tool_args(key_value_segment)
    args.update(json_args)
    return args


def _extract_textual_tool_calls(
    text: str,
    tool_names: set[str],
) -> list[dict[str, Any]]:
    if not text or not tool_names:
        return []

    alternation = "|".join(
        re.escape(name) for name in sorted(tool_names, key=len, reverse=True)
    )
    pattern = re.compile(rf"(?<![\w.-])to=({alternation})(?=\b|\s|$)")
    matches = list(pattern.finditer(text))
    calls: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        name = match.group(1)
        next_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        )
        segment = text[match.end() : next_start]
        calls.append(
            {
                "name": name,
                "args": _parse_textual_tool_args(segment),
                "id": _fallback_tool_call_id(name, index + 1),
            }
        )
    return calls


def _response_text_and_tools(
    response: Any,
    tools: Iterable[Any] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    content = getattr(response, "content", None)
    if content is None:
        return "", []

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for part in getattr(content, "parts", []) or []:
        if getattr(part, "text", None):
            text_parts.append(str(part.text))
        function_call = getattr(part, "function_call", None)
        if function_call is None:
            continue
        tool_calls.append(
            {
                "name": function_call.name,
                "args": dict(function_call.args or {}),
                "id": getattr(function_call, "id", None)
                or _fallback_tool_call_id(function_call.name, len(tool_calls) + 1),
            }
        )
    text = "".join(text_parts).strip()
    if not tool_calls:
        tool_calls = _extract_textual_tool_calls(text, _bound_tool_names(tools))
    return text, tool_calls


def _build_ai_message(content: str, tool_calls: list[dict[str, Any]]):
    try:
        from langchain_core.messages import AIMessage

        return AIMessage(content=content, tool_calls=tool_calls)
    except Exception:
        from diverge.runtime.messages import AdkMessage

        return AdkMessage(content=content, tool_calls=tool_calls)


@dataclass
class _BoundAdkChatModel:
    chat_model: "AdkChatModel"
    tools: tuple[Any, ...]

    def invoke(self, prompt: Any, *, output_schema: Any | None = None):
        return self.chat_model.invoke(
            prompt,
            tools=self.tools,
            output_schema=output_schema,
        )


class AdkChatModel:
    """LangChain-prompt compatible adapter backed by an ADK 2.0 model."""

    def __init__(
        self,
        model: Gemini | LiteLlm,
        *,
        generation_config: Any = None,
        timeout: float | None = None,
    ):
        self.model = model
        self.generation_config = generation_config
        self.timeout = (
            _coerce_timeout_seconds(timeout)
            if timeout is not None
            else getattr(model, "_diverge_timeout_seconds", None)
        )
        self.transient_max_retries = _default_adk_transient_max_retries()
        self.transient_retry_base_delay = (
            _default_adk_transient_retry_base_delay_seconds()
        )
        self.transient_retry_max_delay = (
            _default_adk_transient_retry_max_delay_seconds()
        )

    def bind_tools(self, tools: Iterable[Any]):
        try:
            from langchain_core.runnables import RunnableLambda

            bound_tools = tuple(tools)
            return RunnableLambda(lambda prompt: self.invoke(prompt, tools=bound_tools))
        except Exception:
            return _BoundAdkChatModel(self, tuple(tools))

    def invoke(
        self,
        prompt: Any,
        *,
        tools: Iterable[Any] | None = None,
        output_schema: Any | None = None,
    ):
        is_litellm_model = isinstance(self.model, LiteLlm)
        return _run_coro_blocking(
            self._invoke_async(prompt, tools=tools, output_schema=output_schema),
            persistent_loop=is_litellm_model,
            flush_litellm_logging=is_litellm_model,
        )

    async def _invoke_async(
        self,
        prompt: Any,
        *,
        tools: Iterable[Any] | None = None,
        output_schema: Any | None = None,
    ):
        tool_registry = _adk_tools_from_legacy_tools(tools)
        generation_config = _copy_generation_config(self.generation_config)
        _set_system_instruction(
            generation_config,
            _system_instruction_from_prompt(prompt),
        )
        request = LlmRequest(
            model=getattr(self.model, "model", None),
            contents=_contents_from_prompt(prompt),
            tools_dict=tool_registry,
            config=generation_config,
        )
        if output_schema is not None:
            request.set_output_schema(output_schema)

        model_name = str(getattr(self.model, "model", None) or request.model or "")
        content_count = len(request.contents or [])
        tool_count = len(tool_registry)
        start_time = time.monotonic()
        logger.info(
            "adk_model_call_start model=%s timeout=%s contents=%s tools=%s",
            model_name,
            self.timeout,
            content_count,
            tool_count,
        )
        try:
            final_response = await self._collect_final_response(request)
        except TimeoutError:
            duration = time.monotonic() - start_time
            logger.exception(
                "adk_model_call_timeout model=%s timeout=%s duration=%.2fs contents=%s tools=%s",
                model_name,
                self.timeout,
                duration,
                content_count,
                tool_count,
            )
            raise
        except Exception:
            duration = time.monotonic() - start_time
            logger.exception(
                "adk_model_call_error model=%s duration=%.2fs contents=%s tools=%s",
                model_name,
                duration,
                content_count,
                tool_count,
            )
            raise

        duration = time.monotonic() - start_time
        logger.info(
            "adk_model_call_finish model=%s duration=%.2fs response=%s",
            model_name,
            duration,
            final_response is not None,
        )
        if final_response is None:
            return _build_ai_message("", [])

        text, tool_calls = _response_text_and_tools(final_response, tools)
        return _build_ai_message(text, tool_calls)

    async def _collect_final_response(self, request: LlmRequest):
        async def collect():
            final_response = None
            async for response in self.model.generate_content_async(
                request,
                stream=False,
            ):
                final_response = response
            return final_response

        async def collect_with_timeout():
            if self.timeout is None:
                return await collect()

            try:
                return await asyncio.wait_for(collect(), timeout=self.timeout)
            except asyncio.TimeoutError as exc:
                model_name = str(
                    getattr(self.model, "model", None) or request.model or ""
                )
                raise TimeoutError(
                    f"ADK model call timed out after {self.timeout:g}s for {model_name}"
                ) from exc

        model_name = str(getattr(self.model, "model", None) or request.model or "")
        max_retries = self.transient_max_retries
        base_delay = self.transient_retry_base_delay
        max_delay = self.transient_retry_max_delay
        for attempt in range(max_retries + 1):
            try:
                return await collect_with_timeout()
            except Exception as exc:
                if attempt >= max_retries or not _is_retryable_adk_model_error(exc):
                    raise

                delay = min(max_delay, base_delay * (2**attempt))
                logger.warning(
                    "Retrying transient ADK model error model=%s status=%s "
                    "attempt=%s/%s delay=%.1fs: %s",
                    model_name,
                    _error_status_code(exc),
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                if delay > 0:
                    await asyncio.sleep(delay)

        raise RuntimeError("unreachable ADK model retry state")


def _run_coro_blocking(
    coro,
    *,
    persistent_loop: bool = False,
    flush_litellm_logging: bool = True,
):
    wrapped = _await_and_flush_litellm_logging(coro, enabled=flush_litellm_logging)
    if persistent_loop:
        return _run_coro_on_litellm_loop(wrapped)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(wrapped)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, wrapped).result()


def _run_coro_on_litellm_loop(coro):
    loop = _get_litellm_loop()
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None
    if running_loop is loop:
        coro.close()
        raise RuntimeError("Cannot synchronously wait on the persistent LiteLLM loop")

    future: Future[Any] = Future()
    with _litellm_loop_lock:
        work_queue = _litellm_loop_queue
    if work_queue is None:
        coro.close()
        raise RuntimeError("Persistent LiteLLM event loop is not running")
    work_queue.put((coro, future))

    try:
        return future.result()
    except BaseException:
        if not future.done():
            future.cancel()
        raise


def _get_litellm_loop() -> asyncio.AbstractEventLoop:
    global _litellm_loop, _litellm_loop_thread, _litellm_loop_queue

    with _litellm_loop_lock:
        if (
            _litellm_loop is not None
            and not _litellm_loop.is_closed()
            and _litellm_loop_thread is not None
            and _litellm_loop_thread.is_alive()
            and _litellm_loop_queue is not None
        ):
            return _litellm_loop

        ready = threading.Event()
        loop_holder: dict[str, asyncio.AbstractEventLoop] = {}
        work_queue: queue.Queue[tuple[Any, Future[Any]] | None] = queue.Queue()
        thread = threading.Thread(
            target=_run_litellm_loop_forever,
            args=(loop_holder, work_queue, ready),
            name="diverge-litellm-asyncio-loop",
            daemon=True,
        )
        _litellm_loop_thread = thread
        _litellm_loop_queue = work_queue
        thread.start()
        if not ready.wait(timeout=_LITELLM_LOOP_START_TIMEOUT_SECONDS):
            _litellm_loop = None
            _litellm_loop_thread = None
            _litellm_loop_queue = None
            raise RuntimeError("Timed out starting persistent LiteLLM event loop")
        loop = loop_holder["loop"]
        _litellm_loop = loop
        return loop


def _run_litellm_loop_forever(
    loop_holder: dict[str, asyncio.AbstractEventLoop],
    work_queue: queue.Queue[tuple[Any, Future[Any]] | None],
    ready: threading.Event,
) -> None:
    loop = asyncio.new_event_loop()
    loop_holder["loop"] = loop
    asyncio.set_event_loop(loop)
    ready.set()
    try:
        while True:
            item = work_queue.get()
            if item is None:
                break
            coro, future = item
            if not future.set_running_or_notify_cancel():
                coro.close()
                continue
            try:
                future.set_result(loop.run_until_complete(coro))
            except BaseException as exc:
                future.set_exception(exc)
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            with contextlib.suppress(Exception):
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_default_executor())
        asyncio.set_event_loop(None)
        loop.close()


def _shutdown_litellm_loop_for_tests() -> None:
    _shutdown_litellm_loop()


def _shutdown_litellm_loop() -> None:
    global _litellm_loop, _litellm_loop_thread, _litellm_loop_queue

    with _litellm_loop_lock:
        loop = _litellm_loop
        thread = _litellm_loop_thread
        work_queue = _litellm_loop_queue
        _litellm_loop = None
        _litellm_loop_thread = None
        _litellm_loop_queue = None

    if loop is None or loop.is_closed() or work_queue is None:
        return
    if (
        thread is not None
        and thread.is_alive()
        and threading.current_thread() is not thread
    ):
        with contextlib.suppress(Exception):
            future: Future[Any] = Future()
            work_queue.put((_flush_litellm_logging_worker(), future))
            future.result(timeout=_LITELLM_LOOP_SHUTDOWN_TIMEOUT_SECONDS)
    work_queue.put(None)
    if (
        thread is not None
        and thread.is_alive()
        and threading.current_thread() is not thread
    ):
        thread.join(timeout=_LITELLM_LOOP_SHUTDOWN_TIMEOUT_SECONDS)


atexit.register(_shutdown_litellm_loop)


async def _await_and_flush_litellm_logging(coro, *, enabled: bool = True):
    try:
        return await coro
    finally:
        if enabled:
            await _flush_litellm_logging_worker()


async def _flush_litellm_logging_worker() -> None:
    worker_module = sys.modules.get("litellm.litellm_core_utils.logging_worker")
    if worker_module is None:
        return

    worker = getattr(worker_module, "GLOBAL_LOGGING_WORKER", None)
    flush = getattr(worker, "flush", None)
    if not callable(flush):
        return

    # LiteLLM logging is best-effort; a flush failure must not replace the model
    # result or mask the original model exception.
    with contextlib.suppress(Exception):
        await flush()
