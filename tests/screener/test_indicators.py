from __future__ import annotations

import math

import pandas as pd

from tradingagents.screener.indicators import build_feature_row, build_features_table


def _make_price_frame(periods: int = 80) -> pd.DataFrame:
    dates = pd.bdate_range("2025-12-01", periods=periods)
    close = pd.Series(range(100, 100 + periods), dtype=float)
    frame = pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000 + pd.Series(range(periods), dtype=float),
            "Amount": (close * (1_000 + pd.Series(range(periods), dtype=float))).astype(float),
        }
    )
    return frame


def test_build_feature_row_populates_required_columns_and_formulas():
    price_df = _make_price_frame()
    meta_row = pd.Series(
        {
            "symbol": "AAPL",
            "market": "us",
            "name": "Apple",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "list_date": "19801212",
        }
    )

    row = build_feature_row(meta_row, price_df, "2026-03-20")

    required_keys = {
        "symbol",
        "market",
        "name",
        "exchange",
        "sector",
        "list_date",
        "as_of_date",
        "close",
        "volume",
        "amount",
        "avg_amount_20d",
        "ma20",
        "ma60",
        "ret_20",
        "ret_60",
        "rsi",
        "macd",
        "macds",
        "macdh",
        "atr",
        "atr_pct",
        "boll",
        "boll_ub",
        "boll_lb",
        "vwma",
        "mfi",
        "data_start_date",
        "data_end_date",
        "bar_count",
    }
    assert required_keys.issubset(row.keys())

    latest = price_df.iloc[-1]
    trailing_20 = price_df.tail(20)
    assert row["close"] == latest["Close"]
    assert row["bar_count"] == len(price_df)
    assert row["ma20"] == trailing_20["Close"].mean()
    assert row["avg_amount_20d"] == trailing_20["Amount"].mean()
    assert row["ret_20"] == (latest["Close"] / price_df.iloc[-21]["Close"]) - 1
    assert row["ret_60"] == (latest["Close"] / price_df.iloc[-61]["Close"]) - 1
    assert math.isclose(row["atr_pct"], row["atr"] / row["close"], rel_tol=1e-9)


def test_build_feature_row_uses_latest_trading_row_on_or_before_as_of_date():
    price_df = _make_price_frame()
    meta_row = pd.Series(
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
        }
    )

    last_trading_date = price_df.iloc[-1]["Date"]
    row = build_feature_row(meta_row, price_df, "2026-03-21")

    assert row["data_end_date"] == last_trading_date
    assert row["close"] == price_df.iloc[-1]["Close"]


def test_build_feature_row_marks_too_short_history_as_insufficient():
    price_df = _make_price_frame(periods=10)
    meta_row = pd.Series(
        {
            "symbol": "AAPL",
            "market": "us",
            "name": "Apple",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "list_date": "19801212",
        }
    )

    row = build_feature_row(meta_row, price_df, "2025-12-12")

    assert row["bar_count"] == 10
    assert pd.isna(row["ma20"])
    assert pd.isna(row["ret_20"])
    assert pd.isna(row["rsi"])
    assert row["data_end_date"] == price_df.iloc[-1]["Date"]


def test_build_features_table_builds_rows_for_each_symbol():
    price_df = _make_price_frame()
    universe_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
            },
            {
                "symbol": "MSFT",
                "market": "us",
                "name": "Microsoft",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19860313",
            },
        ]
    )

    histories = {
        "AAPL": price_df,
        "MSFT": price_df.copy(),
    }

    result = build_features_table(universe_df, histories, "2026-03-20")

    assert list(result["symbol"]) == ["AAPL", "MSFT"]
    assert set(result.columns).issuperset({"ma20", "macdh", "atr_pct", "bar_count"})


def test_build_features_table_skips_symbols_without_successful_history():
    price_df = _make_price_frame()
    universe_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
            },
            {
                "symbol": "MSFT",
                "market": "us",
                "name": "Microsoft",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19860313",
            },
        ]
    )

    histories = {
        "AAPL": price_df,
    }

    result = build_features_table(universe_df, histories, "2026-03-20")

    assert list(result["symbol"]) == ["AAPL"]
