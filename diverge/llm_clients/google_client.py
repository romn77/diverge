import os
from typing import Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from .base_client import BaseLLMClient, normalize_content
from .model_config import get_provider_base_url
from .validators import validate_model

GOOGLE_GEMINI_BASE_URL_ENV = "GOOGLE_GEMINI_BASE_URL"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"


def _clean_env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _is_default_google_base_url(base_url: str) -> bool:
    return base_url.strip().rstrip("/") == get_provider_base_url("google").rstrip("/")


def resolve_google_base_url(base_url: Optional[str] = None) -> str | None:
    """Resolve Gemini API base URL, allowing env override of the built-in default."""
    configured = base_url.strip() if base_url and base_url.strip() else None
    env_base_url = _clean_env_value(GOOGLE_GEMINI_BASE_URL_ENV)
    if configured and not _is_default_google_base_url(configured):
        return configured
    if env_base_url:
        return env_base_url
    return None


def resolve_google_api_key(api_key: Optional[str] = None) -> str | None:
    """Resolve Gemini API key from explicit args or supported env aliases."""
    if api_key and api_key.strip():
        return api_key.strip()
    return _clean_env_value(GOOGLE_API_KEY_ENV) or _clean_env_value(GEMINI_API_KEY_ENV)


class NormalizedChatGoogleGenerativeAI(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI with normalized content output.

    Gemini 3 models return content as list of typed blocks.
    This normalizes to string for consistent downstream handling.
    """

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


class GoogleClient(BaseLLMClient):
    """Client for Google Gemini models."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatGoogleGenerativeAI instance."""
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        base_url = resolve_google_base_url(self.base_url)
        if base_url:
            llm_kwargs["base_url"] = base_url

        for key in (
            "timeout",
            "max_retries",
            "callbacks",
            "http_client",
            "http_async_client",
        ):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Unified api_key maps to provider-specific google_api_key
        google_api_key = resolve_google_api_key(
            self.kwargs.get("api_key") or self.kwargs.get("google_api_key")
        )
        if google_api_key:
            llm_kwargs["google_api_key"] = google_api_key

        # Map thinking_level to appropriate API param based on model
        # Gemini 3 Pro: low, high
        # Gemini 3 Flash: minimal, low, medium, high
        # Gemini 2.5: thinking_budget (0=disable, -1=dynamic)
        thinking_level = self.kwargs.get("thinking_level")
        if thinking_level:
            model_lower = self.model.lower()
            if "gemini-3" in model_lower:
                # Gemini 3 Pro doesn't support "minimal", use "low" instead
                if "pro" in model_lower and thinking_level == "minimal":
                    thinking_level = "low"
                llm_kwargs["thinking_level"] = thinking_level
            else:
                # Gemini 2.5: map to thinking_budget
                llm_kwargs["thinking_budget"] = -1 if thinking_level == "high" else 0

        return NormalizedChatGoogleGenerativeAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for Google."""
        return validate_model("google", self.model)
