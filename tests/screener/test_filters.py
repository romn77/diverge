from __future__ import annotations

import pandas as pd

from tradingagents.screener.filters import apply_hard_filters
from tradingagents.screener.schema import ScreenRunConfig


def _base_feature_row(**overrides):
    row = {
        "symbol": "AAPL",
        "market": "us",
        "name": "Apple",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "list_date": "19801212",
        "as_of_date": "2026-03-24",
        "close": 100.0,
        "volume": 1000.0,
        "amount": 100_000.0,
        "avg_amount_20d": 20_000_000.0,
        "ma20": 95.0,
        "ma60": 90.0,
        "ret_20": 0.1,
        "ret_60": 0.2,
        "rsi": 60.0,
        "macd": 1.0,
        "macds": 0.8,
        "macdh": 0.2,
        "atr": 2.0,
        "atr_pct": 0.02,
        "boll": 94.0,
        "boll_ub": 102.0,
        "boll_lb": 86.0,
        "vwma": 96.0,
        "mfi": 55.0,
        "data_start_date": "2025-12-01",
        "data_end_date": "2026-03-24",
        "bar_count": 80,
    }
    row.update(overrides)
    return row


def test_apply_hard_filters_drops_rows_with_insufficient_bars():
    features = pd.DataFrame([_base_feature_row(bar_count=40)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["insufficient_bars"]


def test_apply_hard_filters_marks_recent_listings_as_too_new_before_bar_check():
    features = pd.DataFrame([_base_feature_row(list_date="20260115", bar_count=20)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["too_new"]


def test_apply_hard_filters_drops_rows_with_missing_required_features():
    features = pd.DataFrame([_base_feature_row(rsi=pd.NA)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["missing_features"]


def test_apply_hard_filters_uses_cn_liquidity_threshold():
    features = pd.DataFrame(
        [_base_feature_row(symbol="600519.SH", market="cn", exchange="SSE", avg_amount_20d=1_000_000.0)]
    )
    config = ScreenRunConfig(markets=["cn"], as_of_date="2026-03-24", top_k=20)

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["illiquid_cn"]


def test_apply_hard_filters_uses_us_dollar_volume_threshold():
    features = pd.DataFrame([_base_feature_row(avg_amount_20d=1_000_000.0)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["illiquid_us"]

