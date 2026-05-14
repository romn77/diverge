from __future__ import annotations

import importlib
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

_INITIALIZED = False

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "dsn",
    "database_url",
    "openai_api_key",
    "google_api_key",
    "gemini_api_key",
    "minimax_api_key",
    "tushare_token",
    "prompt",
    "agent_input",
    "agent_output",
    "llm_response",
    "messages",
    "portfolio",
    "holdings",
    "positions",
    "trade_records",
    "api_raw_response",
}

SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "database_url",
    "prompt",
    "agent_input",
    "agent_output",
    "llm_response",
    "portfolio",
    "holdings",
    "positions",
    "trade_records",
)

SENSITIVE_VALUE_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-=]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (
        re.compile(r"\b(postgresql|postgres|mysql|redis)://[^\s'\"<>]+", re.IGNORECASE),
        lambda match: f"{match.group(1)}://[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"openai_api_key|google_api_key|gemini_api_key|minimax_api_key|"
            r"tushare_token|api[_-]?key|access_token|refresh_token|token|"
            r"password|secret|dsn"
            r")=([^&\s]+)"
        ),
        r"\1=[REDACTED]",
    ),
)


def _normalize_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalize_key(key)
    return normalized in SENSITIVE_KEYS or any(
        fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS
    )


def scrub_value(value: str) -> str:
    text = value
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def scrub_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else scrub_obj(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [scrub_obj(value) for value in obj]
    if isinstance(obj, tuple):
        return tuple(scrub_obj(value) for value in obj)
    if isinstance(obj, str):
        return scrub_value(obj)
    return obj


def before_send(event: dict[str, Any], _hint: dict[str, Any] | None) -> dict[str, Any]:
    return scrub_obj(event)


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return float(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw_value, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw_value, default)
        return default


def _logging_level(name: str, default: str) -> int:
    raw_value = os.environ.get(name, default).strip().upper() or default
    value = getattr(logging, raw_value, None)
    if isinstance(value, int):
        return value
    logger.warning("Invalid %s=%r; using %s", name, raw_value, default)
    return getattr(logging, default)


def _optional_integration(module_name: str, class_name: str) -> Any | None:
    try:
        module = importlib.import_module(module_name)
        integration_cls = getattr(module, class_name)
    except (ImportError, AttributeError):
        return None
    return integration_cls()


def initialize_sentry(*, default_service_name: str) -> bool:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    global _INITIALIZED
    if _INITIALIZED:
        return True

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning("SENTRY_DSN is configured but sentry-sdk is not installed")
        return False

    service_name = os.environ.get("SENTRY_SERVICE", default_service_name).strip()
    if not service_name:
        service_name = default_service_name

    integrations: list[Any] = [
        LoggingIntegration(
            level=_logging_level("SENTRY_LOG_BREADCRUMB_LEVEL", "INFO"),
            event_level=_logging_level("SENTRY_LOG_EVENT_LEVEL", "ERROR"),
        )
    ]
    for module_name, class_name in (
        ("sentry_sdk.integrations.fastapi", "FastApiIntegration"),
        ("sentry_sdk.integrations.arq", "ArqIntegration"),
    ):
        integration = _optional_integration(module_name, class_name)
        if integration is not None:
            integrations.append(integration)

    environment = (
        os.environ.get("SENTRY_ENVIRONMENT")
        or os.environ.get("APP_ENV")
        or "production"
    )
    server_name = os.environ.get("SENTRY_SERVER_NAME", "").strip() or service_name
    options: dict[str, Any] = {
        "dsn": dsn,
        "environment": environment,
        "traces_sample_rate": _env_float("SENTRY_TRACES_SAMPLE_RATE", 0.05),
        "sample_rate": _env_float("SENTRY_ERROR_SAMPLE_RATE", 1.0),
        "send_default_pii": False,
        "include_local_variables": _env_bool("SENTRY_INCLUDE_LOCAL_VARIABLES", False),
        "max_breadcrumbs": _env_int("SENTRY_MAX_BREADCRUMBS", 50),
        "before_send": before_send,
        "integrations": integrations,
        "server_name": server_name,
    }
    release = os.environ.get("SENTRY_RELEASE", "").strip()
    if release:
        options["release"] = release

    sentry_sdk.init(**options)
    sentry_sdk.set_tag("service", service_name)
    sentry_sdk.set_tag("component", "web-backend")
    _INITIALIZED = True
    logger.info(
        "sentry_initialized service=%s environment=%s", service_name, environment
    )
    return True
