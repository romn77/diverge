from __future__ import annotations

import pandas as pd
from unittest.mock import patch

from tradingagents.screener.debug import debug_screen_symbol
from tradingagents.screener.schema import ScreenRunConfig


def test_debug_screen_symbol_returns_stage_outputs_for_ranked_symbol():
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_manifest_path="/tmp/us_manifest.csv",
    )
    universe_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
            }
        ]
    )
    history_df = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 100.0,
                "High": 102.0,
                "Low": 99.0,
                "Close": 101.0,
                "Volume": 500.0,
                "Amount": 50_500.0,
            }
        ]
    )
    feature_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
                "as_of_date": "2026-03-24",
                "close": 101.0,
                "volume": 500.0,
                "amount": 50_500.0,
                "avg_amount_20d": 20_000_000.0,
                "trading_days_20d": 20,
                "ma20": 99.0,
                "ma60": 95.0,
                "ret_20": 0.1,
                "ret_60": 0.2,
                "rsi": 55.0,
                "macd": 1.0,
                "macds": 0.8,
                "macdh": 0.2,
                "atr": 2.0,
                "atr_pct": 0.02,
                "boll": 98.0,
                "boll_ub": 104.0,
                "boll_lb": 94.0,
                "vwma": 100.0,
                "mfi": 50.0,
                "data_start_date": "2025-12-01",
                "data_end_date": "2026-03-24",
                "bar_count": 80,
            }
        ]
    )
    ranked_df = pd.DataFrame(
        [
            {
                **feature_df.iloc[0].to_dict(),
                "trend_score": 1.0,
                "momentum_score": 0.8,
                "risk_score": 0.2,
                "liquidity_score": 0.3,
                "total_score": 0.71,
                "strategy_tags": "trend_up,momentum_positive,above_vwma",
                "risk_flags": "",
                "global_rank": 1,
                "market_rank": 1,
            }
        ]
    )

    with (
        patch("tradingagents.screener.debug.load_universe", return_value=universe_df),
        patch(
            "tradingagents.screener.debug.apply_universe_prefilters",
            return_value=(universe_df, pd.DataFrame(columns=list(universe_df.columns) + ["drop_reason"])),
        ),
        patch(
            "tradingagents.screener.debug.fetch_history_for_universe",
            return_value=(
                {"AAPL": history_df},
                pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
            ),
        ),
        patch("tradingagents.screener.debug.build_features_table", return_value=feature_df),
        patch(
            "tradingagents.screener.debug.apply_hard_filters",
            return_value=(feature_df, pd.DataFrame(columns=list(feature_df.columns) + ["drop_reason"])),
        ),
        patch("tradingagents.screener.debug.score_candidates", return_value=ranked_df),
    ):
        result = debug_screen_symbol(config, symbol="AAPL", market="us")

    assert result.universe_row == universe_df.iloc[0].to_dict()
    assert result.prefilter_drop_reason is None
    assert result.history_rows == 1
    assert result.history_start_date == "2026-03-24"
    assert result.history_end_date == "2026-03-24"
    assert result.fetch_drop_reason is None
    assert result.feature_row == feature_df.iloc[0].to_dict()
    assert result.hard_filter_drop_reason is None
    assert result.score_row == ranked_df.iloc[0].to_dict()
