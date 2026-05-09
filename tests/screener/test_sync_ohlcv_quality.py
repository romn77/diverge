from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from diverge.market_data import price_history
from diverge.market_data.history_cache import classify_history_cache_coverage
from diverge.screener import market_data, sync
from diverge.screener.schema import ScreenRunConfig


def _price_frame(*dates: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": date,
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.0,
                "Close": 10.5,
                "Volume": 1000,
                "Amount": 10_500,
            }
            for date in dates
        ]
    )


def test_classify_history_cache_coverage_ready_when_as_of_bar_exists():
    result = classify_history_cache_coverage(
        _price_frame("2026-04-28", "2026-04-29"),
        start_date="2025-03-25",
        as_of_date="2026-04-29",
    )

    assert result == {
        "status": "ready",
        "cache_start": "2026-04-28",
        "cache_end": "2026-04-29",
        "cache_span": "2026-04-28..2026-04-29",
    }


def test_classify_history_cache_coverage_missing_as_of_bar_when_latest_bar_is_before_as_of_date():
    result = classify_history_cache_coverage(
        _price_frame("2026-04-27", "2026-04-28"),
        start_date="2025-03-25",
        as_of_date="2026-04-29",
    )

    assert result["status"] == "missing_as_of_bar"
    assert result["cache_span"] == "2026-04-27..2026-04-28"


def test_classify_history_cache_coverage_miss_when_frame_empty():
    result = classify_history_cache_coverage(
        pd.DataFrame(),
        start_date="2025-03-25",
        as_of_date="2026-04-29",
    )

    assert result == {
        "status": "history_cache_miss",
        "cache_start": None,
        "cache_end": None,
        "cache_span": None,
    }


def _sync_config(tmp_path, *, as_of_date: str = "2026-04-29") -> ScreenRunConfig:
    return ScreenRunConfig(
        markets=["cn"],
        as_of_date=as_of_date,
        top_k=10,
        output_dir=str(tmp_path / "runs"),
        cache_dir=str(tmp_path / "cache"),
        history_dir=str(tmp_path / "history"),
        cn_data_source="tushare",
    )


def _single_symbol_universe(symbol: str = "000010.SZ") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "market": "cn",
                "name": "Test",
                "exchange": "SZSE",
                "sector": "",
                "list_date": "20200101",
            }
        ]
    )


def test_sync_ohlcv_cache_retries_missing_as_of_bar_until_ready(tmp_path, monkeypatch):
    config = _sync_config(tmp_path)
    universe_df = _single_symbol_universe()
    calls = []

    monkeypatch.setattr(
        sync,
        "prepare_universe_stage",
        lambda *_args, **_kwargs: SimpleNamespace(prefiltered_df=universe_df),
    )
    monkeypatch.setattr(price_history, "CN_REQUEST_DELAY_SECONDS", 0)

    def fake_fetch_price_history(*_args, **_kwargs):
        calls.append(_args)
        if len(calls) < 3:
            return pd.DataFrame()
        return _price_frame("2026-04-29")

    monkeypatch.setattr(market_data, "fetch_price_history", fake_fetch_price_history)

    result = sync.sync_ohlcv_cache(config)

    assert len(calls) == 3
    assert result.symbols_success == 1
    assert result.symbols_failed == 0
    assert result.symbols_missing_as_of_bar == 0
    assert result.quality_reason_counts == {"ready": 1}
    assert result.quality_artifact_path is not None
    artifact = json.loads(open(result.quality_artifact_path, encoding="utf-8").read())
    assert artifact["reason_counts"] == {"ready": 1}
    assert artifact["rows"][0]["status"] == "ready"


def test_sync_ohlcv_cache_marks_persistent_missing_as_of_bar_after_three_retries(
    tmp_path,
    monkeypatch,
):
    config = _sync_config(tmp_path)
    universe_df = _single_symbol_universe()
    calls = []

    monkeypatch.setattr(
        sync,
        "prepare_universe_stage",
        lambda *_args, **_kwargs: SimpleNamespace(prefiltered_df=universe_df),
    )
    monkeypatch.setattr(price_history, "CN_REQUEST_DELAY_SECONDS", 0)

    def fake_fetch_price_history(*_args, **_kwargs):
        calls.append(_args)
        return _price_frame("2026-04-28")

    monkeypatch.setattr(market_data, "fetch_price_history", fake_fetch_price_history)

    result = sync.sync_ohlcv_cache(config)

    assert len(calls) == 4
    assert result.symbols_success == 0
    assert result.symbols_failed == 1
    assert result.symbols_missing_as_of_bar == 1
    assert result.symbols_pruned_from_screener == 1
    assert result.failed_symbols == [
        {
            "symbol": "000010.SZ",
            "market": "cn",
            "drop_reason": "missing_as_of_bar",
        }
    ]
    assert result.missing_as_of_bar_symbols == [
        {
            "symbol": "000010.SZ",
            "market": "cn",
            "cache_span": "2026-04-28..2026-04-28",
        }
    ]
