from __future__ import annotations

from unittest.mock import Mock, patch


from diverge.dataflows.akshare_rate_limit import (
    call_akshare_api,
    reset_akshare_rate_limit_state,
)


def test_call_akshare_api_sleeps_with_random_delay_after_each_request():
    reset_akshare_rate_limit_state()
    sleeper = Mock()

    with (
        patch("diverge.dataflows.akshare_rate_limit.random.uniform", return_value=4.2),
        patch("diverge.dataflows.akshare_rate_limit.time.sleep", sleeper),
    ):
        result = call_akshare_api(lambda: "ok")

    assert result == "ok"
    assert sleeper.call_args_list == [((4.2,), {})]


def test_call_akshare_api_adds_block_pause_every_tenth_request():
    reset_akshare_rate_limit_state()
    sleeper = Mock()

    with (
        patch("diverge.dataflows.akshare_rate_limit.random.uniform", return_value=3.5),
        patch("diverge.dataflows.akshare_rate_limit.time.sleep", sleeper),
    ):
        for _ in range(10):
            call_akshare_api(lambda: "ok")

    sleep_values = [call.args[0] for call in sleeper.call_args_list]
    assert sleep_values.count(3.5) == 10
    assert 20.0 in sleep_values


def test_call_akshare_api_still_sleeps_when_request_raises():
    reset_akshare_rate_limit_state()
    sleeper = Mock()

    with (
        patch("diverge.dataflows.akshare_rate_limit.random.uniform", return_value=5.0),
        patch("diverge.dataflows.akshare_rate_limit.time.sleep", sleeper),
    ):
        try:
            call_akshare_api(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:  # pragma: no cover
            raise AssertionError("expected runtime error")

    assert sleeper.call_args_list == [((5.0,), {})]
