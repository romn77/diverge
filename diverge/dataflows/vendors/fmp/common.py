from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from ...vendor_errors import VendorAuthError, VendorDataEmptyError, VendorRetryableError


FMP_BASE_URL = "https://financialmodelingprep.com"
FMP_TIMEOUT_SECONDS = 30


def _redact_secret_text(value: Any) -> str:
    return re.sub(r"([?&]apikey=)[^&\s]+", r"\1<redacted>", str(value))


def get_api_key() -> str:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise VendorAuthError("FMP_API_KEY environment variable is not set.")
    return api_key


def _make_api_request(path: str, params: dict[str, Any] | None = None) -> Any:
    normalized_path = path if path.startswith("/") else f"/{path}"
    api_params = dict(params or {})
    api_params["apikey"] = get_api_key()
    url = f"{FMP_BASE_URL}{normalized_path}"

    try:
        response = requests.get(url, params=api_params, timeout=FMP_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        message = _redact_secret_text(exc)
        if status_code in {401, 402, 403}:
            raise VendorAuthError(f"FMP request is not permitted: {message}") from exc
        raise VendorRetryableError(f"FMP request failed: {message}") from exc
    except requests.RequestException as exc:
        raise VendorRetryableError(
            f"FMP request failed: {_redact_secret_text(exc)}"
        ) from exc
    except Exception as exc:
        raise VendorRetryableError(
            f"FMP request failed: {_redact_secret_text(exc)}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise VendorRetryableError(
            f"FMP returned non-JSON response: {response.text[:200]}"
        ) from exc

    if isinstance(payload, dict):
        message = (
            payload.get("Error Message")
            or payload.get("error")
            or payload.get("message")
        )
        if message:
            lowered = str(message).lower()
            if "limit" in lowered or "apikey" in lowered or "api key" in lowered:
                raise VendorAuthError(
                    f"FMP rejected the request: {_redact_secret_text(message)}"
                )
            raise VendorRetryableError(
                f"FMP rejected the request: {_redact_secret_text(message)}"
            )

    return payload


def require_non_empty(payload: Any, *, context: str) -> Any:
    if payload is None or payload == [] or payload == {}:
        raise VendorDataEmptyError(f"FMP returned no data for {context}")
    return payload


def dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)
