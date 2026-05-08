from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.tools import FunctionTool
from google.genai import types

from diverge.runtime.messages import message_content, message_role


_OPENAI_COMPATIBLE_PROVIDERS = {
    "ollama",
    "siliconflow",
    "sub2api",
    "xiaohumini",
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
}


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
    if base_url:
        kwargs["api_base"] = base_url
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
    if provider == "google":
        retry_options = kwargs.get("retry_options")
        gemini_kwargs: dict[str, Any] = {}
        if base_url:
            gemini_kwargs["base_url"] = base_url
        if retry_options is not None:
            gemini_kwargs["retry_options"] = retry_options
        return Gemini(model=model, **gemini_kwargs)

    litellm_model = _prefixed_litellm_model(provider, model)
    litellm_kwargs = _litellm_kwargs(
        provider,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
        extra=kwargs,
    )
    return LiteLlm(model=litellm_model, **litellm_kwargs)


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


def _adk_tools_from_legacy_tools(tools: Iterable[Any] | None) -> dict[str, FunctionTool]:
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


def _content_parts_from_message(message: Any) -> list[types.Part]:
    tool_calls = getattr(message, "tool_calls", None) or []
    parts: list[types.Part] = []
    content = message_content(message).strip()
    if content:
        parts.append(types.Part.from_text(text=content))

    for tool_call in tool_calls:
        name = str(tool_call.get("name") or "")
        if not name:
            continue
        parts.append(
            types.Part.from_function_call(
                name=name,
                args=_function_call_args(tool_call.get("args")),
            )
        )

    if message.__class__.__name__ == "ToolMessage":
        name = str(getattr(message, "name", "") or getattr(message, "tool_call_id", "tool"))
        parts = [
            types.Part.from_function_response(
                name=name,
                response={"result": content},
            )
        ]

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
        parts = _content_parts_from_message(message)
        contents.append(types.Content(role=role, parts=parts))
    return contents


def _response_text_and_tools(response: Any) -> tuple[str, list[dict[str, Any]]]:
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
                "id": getattr(function_call, "id", None) or function_call.name,
            }
        )
    return "".join(text_parts).strip(), tool_calls


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

    def invoke(self, prompt: Any):
        return self.chat_model.invoke(prompt, tools=self.tools)


class AdkChatModel:
    """LangChain-prompt compatible adapter backed by an ADK 2.0 model."""

    def __init__(self, model: Gemini | LiteLlm, *, generation_config: Any = None):
        self.model = model
        self.generation_config = generation_config

    def bind_tools(self, tools: Iterable[Any]):
        try:
            from langchain_core.runnables import RunnableLambda

            bound_tools = tuple(tools)
            return RunnableLambda(lambda prompt: self.invoke(prompt, tools=bound_tools))
        except Exception:
            return _BoundAdkChatModel(self, tuple(tools))

    def invoke(self, prompt: Any, *, tools: Iterable[Any] | None = None):
        return _run_coro_blocking(self._invoke_async(prompt, tools=tools))

    async def _invoke_async(self, prompt: Any, *, tools: Iterable[Any] | None = None):
        tool_registry = _adk_tools_from_legacy_tools(tools)
        request = LlmRequest(
            model=getattr(self.model, "model", None),
            contents=_contents_from_prompt(prompt),
            tools_dict=tool_registry,
        )
        if self.generation_config is not None:
            request.config = self.generation_config

        final_response = None
        async for response in self.model.generate_content_async(request, stream=False):
            final_response = response
        if final_response is None:
            return _build_ai_message("", [])

        text, tool_calls = _response_text_and_tools(final_response)
        return _build_ai_message(text, tool_calls)


def _run_coro_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()
