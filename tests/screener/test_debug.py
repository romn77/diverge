from __future__ import annotations

import pandas as pd
from types import SimpleNamespace
from unittest.mock import patch

from diverge.screener.debug import debug_screen_symbol
from diverge.screener.schema import ScreenRunConfig


def test_debug_screen_symbol_uses_shared_stage_helpers_for_target_symbol():
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
    universe_stage = SimpleNamespace(
        universe_df=universe_df,
        prefiltered_df=universe_df,
        prefiltered_out_df=pd.DataFrame(columns=list(universe_df.columns) + ["drop_reason"]),
    )
    evaluation_stage = SimpleNamespace(
        histories={"AAPL": pd.DataFrame([{"Date": "2026-03-24", "Open": 100.0, "High": 102.0, "Low": 99.0, "Close": 101.0, "Volume": 500.0, "Amount": 50_500.0}])},
        fetch_failures=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        features_df=feature_df,
        kept_df=feature_df,
        dropped_df=pd.DataFrame(columns=list(feature_df.columns) + ["drop_reason"]),
        ranked_df=ranked_df,
    )

    with (
        patch("diverge.screener.debug.prepare_universe_stage", return_value=universe_stage),
        patch("diverge.screener.debug.evaluate_screen_stage", return_value=evaluation_stage),
    ):
        result = debug_screen_symbol(config, symbol="AAPL", market="us")

    assert result.score_row["global_rank"] == 1


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

    universe_stage = SimpleNamespace(
        universe_df=universe_df,
        prefiltered_df=universe_df,
        prefiltered_out_df=pd.DataFrame(columns=list(universe_df.columns) + ["drop_reason"]),
    )
    evaluation_stage = SimpleNamespace(
        histories={"AAPL": history_df},
        fetch_failures=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        features_df=feature_df,
        kept_df=feature_df,
        dropped_df=pd.DataFrame(columns=list(feature_df.columns) + ["drop_reason"]),
        ranked_df=ranked_df,
    )

    with (
        patch("diverge.screener.debug.prepare_universe_stage", return_value=universe_stage),
        patch("diverge.screener.debug.evaluate_screen_stage", return_value=evaluation_stage),
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
