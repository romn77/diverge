from __future__ import annotations

from collections import deque
from unittest.mock import Mock, patch

from tradingagents.dataflows.massive_common import (
    _MASSIVE_MAX_CALLS_PER_MINUTE,
    _apply_massive_rate_limit,
    reset_massive_rate_limit_state,
)


def test_apply_massive_rate_limit_allows_requests_below_window_limit():
    reset_massive_rate_limit_state()

    with patch("tradingagents.dataflows.massive_common.time.monotonic", return_value=100.0):
        _apply_massive_rate_limit()


def test_apply_massive_rate_limit_sleeps_when_window_limit_reached():
    reset_massive_rate_limit_state()
    fake_window = deque([100.0 + i * 0.1 for i in range(_MASSIVE_MAX_CALLS_PER_MINUTE)])
    sleeper = Mock()

    with (
        patch("tradingagents.dataflows.massive_common._massive_call_timestamps", fake_window),
        patch("tradingagents.dataflows.massive_common.time.monotonic", return_value=120.0),
        patch("tradingagents.dataflows.massive_common.time.sleep", sleeper),
    ):
        _apply_massive_rate_limit()

    sleeper.assert_called_once()
    assert sleeper.call_args.args[0] > 0
