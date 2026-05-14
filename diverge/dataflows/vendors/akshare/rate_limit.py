from __future__ import annotations

import random
import threading
import time
from typing import Callable, TypeVar


T = TypeVar("T")

AKSHARE_REQUEST_MIN_DELAY_SECONDS = 3.0
AKSHARE_REQUEST_MAX_DELAY_SECONDS = 6.0
AKSHARE_REQUEST_BLOCK_SIZE = 10
AKSHARE_REQUEST_BLOCK_PAUSE_SECONDS = 20.0

_akshare_request_count = 0
_akshare_request_lock = threading.Lock()


def reset_akshare_rate_limit_state() -> None:
    global _akshare_request_count
    with _akshare_request_lock:
        _akshare_request_count = 0


def _sleep_after_request() -> None:
    global _akshare_request_count
    with _akshare_request_lock:
        _akshare_request_count += 1
        request_count = _akshare_request_count

    time.sleep(
        random.uniform(
            AKSHARE_REQUEST_MIN_DELAY_SECONDS,
            AKSHARE_REQUEST_MAX_DELAY_SECONDS,
        )
    )

    if request_count % AKSHARE_REQUEST_BLOCK_SIZE == 0:
        time.sleep(AKSHARE_REQUEST_BLOCK_PAUSE_SECONDS)


def call_akshare_api(func: Callable[..., T], *args, **kwargs) -> T:
    try:
        return func(*args, **kwargs)
    finally:
        _sleep_after_request()
