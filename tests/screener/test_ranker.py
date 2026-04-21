from __future__ import annotations

import pandas as pd

from tradingagents.screener.ranker import score_candidates
from tradingagents.screener.schema import ScreenRunConfig


def test_score_candidates_assigns_market_and_global_ranks_with_market_level_standardization():
    features = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "close": 110.0,
                "ma20": 100.0,
                "ma60": 95.0,
                "ret_20": 0.10,
                "ret_60": 0.18,
                "macdh": 0.5,
                "rsi": 60.0,
                "atr_pct": 0.02,
                "avg_amount_20d": 20_000_000.0,
                "vwma": 101.0,
            },
            {
                "symbol": "MSFT",
                "market": "us",
                "close": 105.0,
                "ma20": 101.0,
                "ma60": 100.0,
                "ret_20": 0.05,
                "ret_60": 0.08,
                "macdh": 0.1,
                "rsi": 52.0,
                "atr_pct": 0.03,
                "avg_amount_20d": 18_000_000.0,
                "vwma": 104.0,
            },
            {
                "symbol": "600519.SH",
                "market": "cn",
                "close": 210.0,
                "ma20": 200.0,
                "ma60": 190.0,
                "ret_20": 0.15,
                "ret_60": 0.30,
                "macdh": 0.4,
                "rsi": 62.0,
                "atr_pct": 0.03,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 205.0,
            },
            {
                "symbol": "000001.SZ",
                "market": "cn",
                "close": 180.0,
                "ma20": 181.0,
                "ma60": 179.0,
                "ret_20": 0.02,
                "ret_60": 0.05,
                "macdh": -0.1,
                "rsi": 48.0,
                "atr_pct": 0.05,
                "avg_amount_20d": 55_000_000.0,
                "vwma": 182.0,
            },
        ]
    )

    ranked = score_candidates(features)

    assert ranked.columns.tolist().count("trend_score") == 1
    assert ranked.columns.tolist().count("momentum_score") == 1
    assert ranked.columns.tolist().count("risk_score") == 1
    assert ranked.columns.tolist().count("liquidity_score") == 1
    assert ranked.loc[ranked["symbol"] == "AAPL", "market_rank"].item() == 1
    assert ranked.loc[ranked["symbol"] == "600519.SH", "market_rank"].item() == 1
    assert ranked["global_rank"].tolist() == [1, 2, 3, 4]


def test_score_candidates_adds_strategy_tags_and_risk_flags_from_thresholds():
    features = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "close": 110.0,
                "ma20": 100.0,
                "ma60": 95.0,
                "ret_20": 0.10,
                "ret_60": 0.18,
                "macdh": 0.5,
                "rsi": 72.0,
                "atr_pct": 0.06,
                "avg_amount_20d": 20_000_000.0,
                "vwma": 101.0,
            },
            {
                "symbol": "MSFT",
                "market": "us",
                "close": 95.0,
                "ma20": 100.0,
                "ma60": 101.0,
                "ret_20": -0.02,
                "ret_60": 0.01,
                "macdh": -0.2,
                "rsi": 30.0,
                "atr_pct": 0.03,
                "avg_amount_20d": 18_000_000.0,
                "vwma": 97.0,
            },
        ]
    )

    ranked = score_candidates(features)

    first = ranked.loc[ranked["symbol"] == "AAPL"].iloc[0]
    second = ranked.loc[ranked["symbol"] == "MSFT"].iloc[0]

    assert "trend_up" in first["strategy_tags"]
    assert "momentum_positive" in first["strategy_tags"]
    assert "above_vwma" in first["strategy_tags"]
    assert "high_atr" in first["risk_flags"]
    assert "rsi_hot" in first["risk_flags"]
    assert "rsi_cold" in second["risk_flags"]


def test_score_candidates_applies_selected_breakout_bonus_with_cap_and_tags():
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=10,
        breakout_types=["platform_breakout", "wedge_breakout"],
    )
    features = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "market": "cn",
                "close": 100.0,
                "ma20": 100.0,
                "ma60": 100.0,
                "ret_20": 0.0,
                "ret_60": 0.0,
                "macdh": 0.0,
                "rsi": 55.0,
                "atr_pct": 0.02,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 100.0,
                "breakout_hit": True,
                "breakout_type": "platform_breakout",
                "breakout_with_volume": True,
                "breakout_reason": "platform_breakout close=103.2 resistance=100.6",
            },
            {
                "symbol": "BBB",
                "market": "cn",
                "close": 100.0,
                "ma20": 100.0,
                "ma60": 100.0,
                "ret_20": 0.0,
                "ret_60": 0.0,
                "macdh": 0.0,
                "rsi": 55.0,
                "atr_pct": 0.02,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 100.0,
                "breakout_hit": True,
                "breakout_type": "wedge_breakout",
                "breakout_with_volume": False,
                "breakout_reason": "wedge_breakout close=101.1 resistance=99.8",
            },
            {
                "symbol": "CCC",
                "market": "cn",
                "close": 100.0,
                "ma20": 100.0,
                "ma60": 100.0,
                "ret_20": 0.0,
                "ret_60": 0.0,
                "macdh": 0.0,
                "rsi": 55.0,
                "atr_pct": 0.02,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 100.0,
                "breakout_hit": True,
                "breakout_type": "box_breakout",
                "breakout_with_volume": True,
                "breakout_reason": "box_breakout close=101.8 resistance=100.4",
            },
            {
                "symbol": "DDD",
                "market": "cn",
                "close": 100.0,
                "ma20": 100.0,
                "ma60": 100.0,
                "ret_20": 0.0,
                "ret_60": 0.0,
                "macdh": 0.0,
                "rsi": 55.0,
                "atr_pct": 0.02,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 100.0,
                "breakout_hit": False,
                "breakout_type": None,
                "breakout_with_volume": False,
                "breakout_reason": "close_not_above_resistance",
            },
        ]
    )

    ranked = score_candidates(features, config)

    assert ranked["symbol"].tolist()[:2] == ["AAA", "BBB"]

    top = ranked.loc[ranked["symbol"] == "AAA"].iloc[0]
    wedge = ranked.loc[ranked["symbol"] == "BBB"].iloc[0]
    ignored = ranked.loc[ranked["symbol"] == "CCC"].iloc[0]

    assert top["breakout_base_bonus"] > wedge["breakout_base_bonus"]
    assert top["breakout_volume_bonus"] > 0
    assert top["breakout_bonus"] == 0.15
    assert wedge["breakout_bonus"] > 0
    assert ignored["breakout_bonus"] == 0
    assert "platform_breakout" in top["strategy_tags"]
    assert "breakout_with_volume" in top["strategy_tags"]
