from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import datetime

import requests

from ...vendor_errors import VendorAuthError, VendorRetryableError


DEFAULT_MASSIVE_BASE_URL = "http://35.209.101.63/api/v1"
_MASSIVE_MAX_CALLS_PER_MINUTE = 200
_MASSIVE_WINDOW_SECONDS = 60.0
_massive_call_timestamps = deque()
_massive_rate_limit_lock = threading.Lock()


def get_massive_api_key() -> str:
    api_key = os.getenv("MASSIVE_API_KEY") or os.getenv("MASSIVE_TOKEN")
    if not api_key:
        raise VendorAuthError("MASSIVE_API_KEY or MASSIVE_TOKEN environment variable is not set.")
    return api_key


def get_massive_base_url() -> str:
    return (os.getenv("MASSIVE_BASE_URL") or DEFAULT_MASSIVE_BASE_URL).rstrip("/")


def reset_massive_rate_limit_state() -> None:
    with _massive_rate_limit_lock:
        _massive_call_timestamps.clear()


def format_rfc3339_start(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%Y-%m-%dT00:00:00Z")


def format_rfc3339_end(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%Y-%m-%dT23:59:59Z")


def _apply_massive_rate_limit() -> None:
    with _massive_rate_limit_lock:
        now = time.monotonic()
        while _massive_call_timestamps and now - _massive_call_timestamps[0] >= _MASSIVE_WINDOW_SECONDS:
            _massive_call_timestamps.popleft()

        if len(_massive_call_timestamps) >= _MASSIVE_MAX_CALLS_PER_MINUTE:
            sleep_for = _MASSIVE_WINDOW_SECONDS - (now - _massive_call_timestamps[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
                now = time.monotonic()
                while _massive_call_timestamps and now - _massive_call_timestamps[0] >= _MASSIVE_WINDOW_SECONDS:
                    _massive_call_timestamps.popleft()

        _massive_call_timestamps.append(time.monotonic())


def massive_get(path: str, params: dict) -> dict:
    url = f"{get_massive_base_url()}/{path.lstrip('/')}"
    headers = {"X-API-KEY": get_massive_api_key()}
    _apply_massive_rate_limit()

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.RequestException as exc:
        raise VendorRetryableError(f"massive request failed: {exc}") from exc

    if response.status_code == 401:
        raise VendorAuthError("massive API authentication failed.")
    if response.status_code == 429:
        raise VendorRetryableError("massive API rate limit exceeded.")

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise VendorRetryableError(f"massive request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise VendorRetryableError(f"massive response was not valid JSON: {exc}") from exc

    return payload
