from __future__ import annotations

import pandas as pd

from diverge.backtest.event_study import run_backtest_snapshot


def test_event_study_uses_t_plus_one_open_and_costs():
    prices = pd.DataFrame(
        [
            {
                "symbol": "300001.SZ",
                "trade_date": "2026-05-14",
                "open": 10.0,
                "close": 10.0,
                "low": 9.8,
            },
            {
                "symbol": "300001.SZ",
                "trade_date": "2026-05-15",
                "open": 10.0,
                "close": 10.5,
                "low": 9.9,
            },
            {
                "symbol": "300001.SZ",
                "trade_date": "2026-05-18",
                "open": 10.6,
                "close": 11.0,
                "low": 10.4,
            },
        ]
    )
    snapshot = run_backtest_snapshot(
        strategy_id="strategy_v1",
        signal_events=[{"symbol": "300001.SZ", "trade_date": "2026-05-14"}],
        price_history=prices,
        cost_model={
            "buy_fee": 0.001,
            "sell_fee": 0.001,
            "stamp_tax_sell": 0.0,
            "slippage": 0.0,
        },
        horizons=(1, 2),
        run_id="bt_test",
    )

    assert snapshot["status"] == "completed"
    assert snapshot["sample_size"] == 1
    assert snapshot["holding_periods"]["1d"]["avg_return"] == 0.048
    assert snapshot["holding_periods"]["2d"]["avg_return"] == 0.098
    assert snapshot["signal_outcomes"][0]["entry_date"] == "2026-05-15"
