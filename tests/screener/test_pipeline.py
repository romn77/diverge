from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tradingagents.screener.pipeline import run_screen
from tradingagents.screener.schema import ScreenRunConfig


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 3, 24, 21, 45, 30)


def test_run_screen_writes_all_required_artifacts_and_merges_fetch_failures(tmp_path):
    config = ScreenRunConfig(
        markets=["cn", "us"],
        as_of_date="2026-03-24",
        top_k=2,
        output_dir=str(tmp_path),
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "Technology", "list_date": "19801212"},
        ]
    )
    features_df = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "market": "cn",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "sector": "Liquor",
                "list_date": "20010827",
                "as_of_date": "2026-03-24",
                "close": 210.0,
                "volume": 1000.0,
                "amount": 210000.0,
                "avg_amount_20d": 80_000_000.0,
                "ma20": 200.0,
                "ma60": 190.0,
                "ret_20": 0.15,
                "ret_60": 0.30,
                "rsi": 62.0,
                "macd": 1.0,
                "macds": 0.8,
                "macdh": 0.4,
                "atr": 6.0,
                "atr_pct": 0.03,
                "boll": 198.0,
                "boll_ub": 214.0,
                "boll_lb": 182.0,
                "vwma": 205.0,
                "mfi": 55.0,
                "data_start_date": "2025-12-01",
                "data_end_date": "2026-03-24",
                "bar_count": 80,
            }
        ]
    )
    histories = {
        "600519.SH": pd.DataFrame(
            [{"Date": "2026-03-24", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1, "Amount": 1}]
        )
    }
    fetch_failures = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "drop_reason": "fetch_failed"}]
    )
    scored_df = pd.DataFrame(
        [
            {
                **features_df.iloc[0].to_dict(),
                "trend_score": 1.0,
                "momentum_score": 1.0,
                "risk_score": 1.0,
                "liquidity_score": 1.0,
                "total_score": 1.0,
                "strategy_tags": "trend_up,momentum_positive,above_vwma",
                "risk_flags": "",
                "market_rank": 1,
                "global_rank": 1,
            }
        ]
    )

    with (
        patch("tradingagents.screener.pipeline.load_universe", return_value=universe_df),
        patch(
            "tradingagents.screener.pipeline.fetch_history_for_universe",
            return_value=(histories, fetch_failures),
        ),
        patch("tradingagents.screener.pipeline.build_features_table", return_value=features_df),
        patch(
            "tradingagents.screener.pipeline.apply_hard_filters",
            return_value=(features_df, pd.DataFrame(columns=list(features_df.columns) + ["drop_reason"])),
        ),
        patch("tradingagents.screener.pipeline.score_candidates", return_value=scored_df),
        patch("tradingagents.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    run_dir = Path(result.run_dir)
    assert run_dir.name == "20260324_214530"
    assert (run_dir / "run_meta.json").is_file()
    assert (run_dir / "universe.csv").is_file()
    assert (run_dir / "features.csv").is_file()
    assert (run_dir / "filtered_out.csv").is_file()
    assert (run_dir / "candidates.csv").is_file()
    assert (run_dir / "llm_pool.json").is_file()

    filtered_out = pd.read_csv(run_dir / "filtered_out.csv")
    assert filtered_out["drop_reason"].tolist() == ["fetch_failed"]

    llm_pool = json.loads((run_dir / "llm_pool.json").read_text(encoding="utf-8"))
    assert len(llm_pool) == 1
    assert llm_pool[0]["symbol"] == "600519.SH"

    run_meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["config"]["top_k"] == 2
    assert run_meta["universe_count_by_market"] == {"cn": 1, "us": 1}
    assert run_meta["fetch_failed_count"] == 1
    assert run_meta["candidate_count"] == 1
    assert set(run_meta["artifact_paths"]) == {
        "run_meta",
        "universe",
        "features",
        "filtered_out",
        "candidates",
        "llm_pool",
    }


def test_run_screen_prefilters_too_new_symbols_before_history(tmp_path):
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=2,
        output_dir=str(tmp_path),
    )
    universe_df = pd.DataFrame(
        [
            {"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "301000.SZ", "market": "cn", "name": "Recent Listing", "exchange": "SZSE", "sector": "Technology", "list_date": "20260115"},
        ]
    )
    filtered_universe_df = universe_df.iloc[[0]].reset_index(drop=True)
    prefiltered_out_df = pd.DataFrame(
        [
            {
                "symbol": "301000.SZ",
                "market": "cn",
                "name": "Recent Listing",
                "exchange": "SZSE",
                "sector": "Technology",
                "list_date": "20260115",
                "drop_reason": "too_new",
            }
        ]
    )
    features_df = pd.DataFrame()
    histories = {
        "600519.SH": pd.DataFrame(
            [{"Date": "2026-03-24", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1, "Amount": 1}]
        )
    }

    with (
        patch("tradingagents.screener.pipeline.load_universe", return_value=universe_df),
        patch(
            "tradingagents.screener.pipeline.apply_universe_prefilters",
            return_value=(filtered_universe_df, prefiltered_out_df),
        ) as mock_prefilter,
        patch(
            "tradingagents.screener.pipeline.fetch_history_for_universe",
            return_value=(histories, pd.DataFrame(columns=["symbol", "market", "drop_reason"])),
        ) as mock_fetch,
        patch("tradingagents.screener.pipeline.build_features_table", return_value=features_df),
        patch(
            "tradingagents.screener.pipeline.apply_hard_filters",
            return_value=(features_df, pd.DataFrame(columns=["drop_reason"])),
        ),
        patch("tradingagents.screener.pipeline.score_candidates", return_value=pd.DataFrame()),
        patch("tradingagents.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    mock_prefilter.assert_called_once()
    fetch_universe = mock_fetch.call_args.args[0]
    assert fetch_universe["symbol"].tolist() == ["600519.SH"]

    filtered_out = pd.read_csv(Path(result.run_dir) / "filtered_out.csv")
    assert filtered_out["symbol"].tolist() == ["301000.SZ"]
    assert filtered_out["drop_reason"].tolist() == ["too_new"]
