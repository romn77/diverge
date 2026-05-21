from __future__ import annotations

import asyncio
import atexit
import contextlib
import logging
import os
import queue
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from functools import cached_property
from typing import Any, Optional

from google.genai import Client
from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from pydantic import Field

from diverge.llm_clients.google_client import (
    resolve_google_api_key,
    resolve_google_base_url,
)

logger = logging.getLogger(__name__)

DEFAULT_ADK_MODEL_TIMEOUT_SECONDS = 300.0
ADK_MODEL_TIMEOUT_ENV = "DIVERGE_LLM_TIMEOUT_SECONDS"
_LITELLM_LOOP_START_TIMEOUT_SECONDS = 5.0
_LITELLM_LOOP_SHUTDOWN_TIMEOUT_SECONDS = 5.0

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


def _default_adk_model_timeout_seconds() -> float | None:
    raw_value = os.environ.get(ADK_MODEL_TIMEOUT_ENV)
    if raw_value is None or not raw_value.strip():
        return DEFAULT_ADK_MODEL_TIMEOUT_SECONDS
    return _coerce_timeout_seconds(raw_value.strip())


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
