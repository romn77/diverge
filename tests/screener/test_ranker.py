from __future__ import annotations

import pandas as pd

from diverge.screener.ranker import score_candidates
from diverge.screener.schema import ScreenRunConfig


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


def test_score_candidates_supports_pattern_ranking_profile_contributions():
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=10,
        ranking_profile_id="pattern_breakout",
    )
    features = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "market": "cn",
                "close": 105.0,
                "ma20": 100.0,
                "ma60": 95.0,
                "ret_20": 0.05,
                "ret_60": 0.08,
                "macdh": 0.2,
                "rsi": 58.0,
                "atr_pct": 0.03,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 101.0,
                "breakout_hit": True,
                "breakout_type": "platform_breakout",
                "breakout_with_volume": True,
            },
            {
                "symbol": "BBB",
                "market": "cn",
                "close": 100.0,
                "ma20": 99.0,
                "ma60": 98.0,
                "ret_20": 0.04,
                "ret_60": 0.07,
                "macdh": 0.1,
                "rsi": 55.0,
                "atr_pct": 0.03,
                "avg_amount_20d": 80_000_000.0,
                "vwma": 100.0,
                "breakout_hit": False,
                "breakout_type": None,
                "breakout_with_volume": False,
            },
        ]
    )

    ranked = score_candidates(features, config)

    top = ranked.iloc[0]
    assert top["symbol"] == "AAA"
    assert top["ranking_profile_id"] == "pattern_breakout"
    assert "pattern:" in top["score_contributions"]
    assert "fundamental:" not in top["score_contributions"]
    assert "pattern_score" in ranked.columns
    assert "technical_score" in ranked.columns


def test_score_candidates_can_rank_with_fundamental_profile():
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=10,
        us_manifest_path="/tmp/us.csv",
        ranking_profile_id="quality_growth_value",
        include_fundamentals=True,
    )
    common = {
        "market": "us",
        "close": 100.0,
        "ma20": 99.0,
        "ma60": 98.0,
        "ret_20": 0.04,
        "ret_60": 0.07,
        "macdh": 0.1,
        "rsi": 55.0,
        "atr_pct": 0.03,
        "avg_amount_20d": 80_000_000.0,
        "vwma": 100.0,
        "breakout_hit": False,
        "breakout_type": None,
        "breakout_with_volume": False,
    }
    features = pd.DataFrame(
        [
            {
                **common,
                "symbol": "GOOD",
                "pe_ttm": 20.0,
                "roe": 0.25,
                "gross_margin": 0.70,
                "net_margin": 0.25,
                "revenue_growth_yoy": 0.30,
                "net_income_growth_yoy": 0.25,
                "current_ratio": 2.0,
                "debt_to_assets": 0.20,
            },
            {
                **common,
                "symbol": "WEAK",
                "pe_ttm": 80.0,
                "roe": 0.05,
                "gross_margin": 0.20,
                "net_margin": 0.02,
                "revenue_growth_yoy": -0.05,
                "net_income_growth_yoy": -0.10,
                "current_ratio": 0.8,
                "debt_to_assets": 0.90,
            },
        ]
    )

    ranked = score_candidates(features, config)

    assert ranked["symbol"].tolist()[0] == "GOOD"
    assert ranked.loc[ranked["symbol"] == "GOOD", "fundamental_score"].item() > 0
    assert "fundamental:" in ranked.iloc[0]["score_contributions"]
