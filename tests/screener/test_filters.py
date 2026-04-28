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
        "trading_days_20d": 20,
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


def test_apply_hard_filters_does_not_reapply_listing_age_after_history():
    features = pd.DataFrame(
        [
            _base_feature_row(
                symbol="000001.SZ",
                market="cn",
                exchange="SZSE",
                list_date="20230802",
                as_of_date="2024-01-25",
                data_end_date="2024-01-25",
                avg_amount_20d=80_000_000.0,
            )
        ]
    )
    config = ScreenRunConfig(markets=["cn"], as_of_date="2024-01-25", top_k=20)

    kept, dropped = apply_hard_filters(features, config)

    assert kept["symbol"].tolist() == ["000001.SZ"]
    assert dropped.empty


def test_apply_hard_filters_drops_rows_with_missing_required_features():
    features = pd.DataFrame([_base_feature_row(rsi=pd.NA)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["missing_features"]


def test_apply_hard_filters_drops_rows_with_stale_data():
    features = pd.DataFrame([_base_feature_row(data_end_date="2026-03-18")])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["stale_data"]


def test_apply_hard_filters_prioritizes_stale_data_before_missing_features():
    features = pd.DataFrame([_base_feature_row(data_end_date="2026-03-18", rsi=pd.NA)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["stale_data"]


def test_apply_hard_filters_uses_us_market_holidays_for_stale_data_lag():
    features = pd.DataFrame(
        [_base_feature_row(as_of_date="2026-04-07", data_end_date="2026-04-01")]
    )
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-04-07", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept["symbol"].tolist() == ["AAPL"]
    assert dropped.empty


def test_apply_hard_filters_uses_cn_market_holidays_for_stale_data_lag():
    features = pd.DataFrame(
        [
            _base_feature_row(
                symbol="600519.SH",
                market="cn",
                exchange="SSE",
                as_of_date="2025-10-10",
                data_end_date="2025-09-30",
                avg_amount_20d=80_000_000.0,
            )
        ]
    )
    config = ScreenRunConfig(markets=["cn"], as_of_date="2025-10-10", top_k=20)

    kept, dropped = apply_hard_filters(features, config)

    assert kept["symbol"].tolist() == ["600519.SH"]
    assert dropped.empty


def test_apply_hard_filters_enforces_us_price_floor():
    features = pd.DataFrame([_base_feature_row(close=4.99)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["low_price_us"]


def test_apply_hard_filters_enforces_cn_price_floor():
    features = pd.DataFrame(
        [
            _base_feature_row(
                symbol="600519.SH",
                market="cn",
                exchange="SSE",
                close=2.99,
                avg_amount_20d=80_000_000.0,
            )
        ]
    )
    config = ScreenRunConfig(markets=["cn"], as_of_date="2026-03-24", top_k=20)

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["low_price_cn"]


def test_apply_hard_filters_requires_recent_trading_continuity():
    features = pd.DataFrame([_base_feature_row(trading_days_20d=17)])
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")

    kept, dropped = apply_hard_filters(features, config)

    assert kept.empty
    assert dropped["drop_reason"].tolist() == ["insufficient_trading_days_20d"]


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


def test_apply_hard_filters_applies_semantic_filter_presets():
    features = pd.DataFrame(
        [
            _base_feature_row(symbol="AAPL", rsi=62.0),
            _base_feature_row(symbol="MSFT", rsi=55.0),
        ]
    )
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_manifest_path="/tmp/us.csv",
        filter_preset_selections={"rsi": "strength_60"},
    )

    kept, dropped = apply_hard_filters(features, config)

    assert kept["symbol"].tolist() == ["AAPL"]
    assert kept["matched_conditions"].tolist() == ["Strength >= 60"]
    assert dropped["symbol"].tolist() == ["MSFT"]
    assert dropped["drop_reason"].tolist() == ["preset_rsi_strength_60"]


def test_apply_hard_filters_applies_market_default_liquidity_preset():
    features = pd.DataFrame(
        [
            _base_feature_row(symbol="AAPL", avg_amount_20d=25_000_000.0),
            _base_feature_row(symbol="MSFT", avg_amount_20d=15_000_000.0),
        ]
    )
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_manifest_path="/tmp/us.csv",
        filter_preset_selections={"liquidity": "market_default_2x"},
    )

    kept, dropped = apply_hard_filters(features, config)

    assert kept["symbol"].tolist() == ["AAPL"]
    assert dropped["symbol"].tolist() == ["MSFT"]
    assert dropped["drop_reason"].tolist() == ["preset_liquidity_market_default_2x"]
