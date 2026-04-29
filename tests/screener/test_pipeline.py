from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from diverge.screener.pipeline import run_screen
from diverge.screener.schema import ScreenRunConfig
from diverge.screener.stages import evaluate_screen_stage
from diverge.screener.storage import prepare_run_dir


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 3, 24, 21, 45, 30)


def _universe_stage(
    universe_df: pd.DataFrame,
    *,
    prefiltered_df: pd.DataFrame | None = None,
    prefiltered_out_df: pd.DataFrame | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        universe_df=universe_df,
        prefiltered_df=universe_df if prefiltered_df is None else prefiltered_df,
        prefiltered_out_df=(
            pd.DataFrame(columns=list(universe_df.columns) + ["drop_reason"])
            if prefiltered_out_df is None
            else prefiltered_out_df
        ),
    )


def _evaluation_stage(
    *,
    histories: dict[str, pd.DataFrame] | None = None,
    fetch_failures: pd.DataFrame | None = None,
    features_df: pd.DataFrame | None = None,
    kept_df: pd.DataFrame | None = None,
    dropped_df: pd.DataFrame | None = None,
    ranked_df: pd.DataFrame | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        histories={} if histories is None else histories,
        fetch_failures=(
            pd.DataFrame(columns=["symbol", "market", "drop_reason"])
            if fetch_failures is None
            else fetch_failures
        ),
        features_df=pd.DataFrame() if features_df is None else features_df,
        kept_df=pd.DataFrame() if kept_df is None else kept_df,
        dropped_df=pd.DataFrame(columns=["drop_reason"]) if dropped_df is None else dropped_df,
        ranked_df=pd.DataFrame() if ranked_df is None else ranked_df,
    )


def test_prepare_run_dir_avoids_same_second_collisions(tmp_path):
    with patch("diverge.screener.storage.datetime", _FixedDateTime):
        first_run_dir = prepare_run_dir(str(tmp_path), "2026-03-24")
        second_run_dir = prepare_run_dir(str(tmp_path), "2026-03-24")

    assert first_run_dir.name == "20260324_214530"
    assert second_run_dir.name.startswith("20260324_214530_")
    assert first_run_dir != second_run_dir


def test_evaluate_screen_stage_passes_us_data_source_fallbacks(tmp_path):
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=10,
        us_data_source="yfinance",
        us_data_source_fallbacks=["massive"],
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
            }
        ]
    )
    features_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "close": 10.0,
                "volume": 10.0,
                "amount": 100.0,
            }
        ]
    )

    with (
        patch(
            "diverge.screener.stages.fetch_history_for_universe",
            return_value=(
                {"AAPL": pd.DataFrame()},
                pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
            ),
        ) as fetch_history,
        patch(
            "diverge.screener.stages.build_features_table",
            return_value=features_df,
        ),
        patch(
            "diverge.screener.stages.apply_hard_filters",
            return_value=(features_df, pd.DataFrame(columns=["drop_reason"])),
        ),
        patch("diverge.screener.stages.score_candidates", return_value=features_df),
    ):
        evaluate_screen_stage(
            config,
            source_universe_df=universe_df,
            fetch_universe_df=universe_df,
            cache_root=tmp_path / "cache",
            history_root=tmp_path / "history",
        )

    self_kwargs = fetch_history.call_args.kwargs
    assert self_kwargs["us_data_source"] == "yfinance"
    assert self_kwargs["us_data_source_fallbacks"] == ["massive"]


def test_run_screen_uses_shared_stage_helpers(tmp_path):
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=1,
        output_dir=str(tmp_path),
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
            }
        ]
    )
    features_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
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
                **features_df.iloc[0].to_dict(),
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
        histories={"AAPL": pd.DataFrame([{"Date": "2026-03-24", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1, "Amount": 1}])},
        fetch_failures=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        features_df=features_df,
        kept_df=features_df,
        dropped_df=pd.DataFrame(columns=list(features_df.columns) + ["drop_reason"]),
        ranked_df=ranked_df,
    )

    with (
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=universe_stage),
        patch("diverge.screener.pipeline.evaluate_screen_stage", return_value=evaluation_stage),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    assert result.candidate_count == 1


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
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=_universe_stage(universe_df)),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                histories=histories,
                fetch_failures=fetch_failures,
                features_df=features_df,
                kept_df=features_df,
                dropped_df=pd.DataFrame(columns=list(features_df.columns) + ["drop_reason"]),
                ranked_df=scored_df,
            ),
        ),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
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
        patch(
            "diverge.screener.pipeline.prepare_universe_stage",
            return_value=_universe_stage(
                universe_df,
                prefiltered_df=filtered_universe_df,
                prefiltered_out_df=prefiltered_out_df,
            ),
        ),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                histories=histories,
                features_df=features_df,
            ),
        ) as mock_evaluate,
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    fetch_universe = mock_evaluate.call_args.kwargs["fetch_universe_df"]
    assert fetch_universe["symbol"].tolist() == ["600519.SH"]

    filtered_out = pd.read_csv(Path(result.run_dir) / "filtered_out.csv")
    assert filtered_out["symbol"].tolist() == ["301000.SZ"]
    assert filtered_out["drop_reason"].tolist() == ["too_new"]


def test_run_screen_writes_stale_data_rows_with_as_of_and_data_end_dates(tmp_path):
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=2,
        output_dir=str(tmp_path),
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
            }
        ]
    )
    stale_features_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
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
                "data_end_date": "2026-03-18",
                "bar_count": 80,
            }
        ]
    )

    with (
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=_universe_stage(universe_df)),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                histories={"AAPL": pd.DataFrame()},
                features_df=stale_features_df,
                kept_df=pd.DataFrame(columns=stale_features_df.columns),
                dropped_df=pd.DataFrame([{**stale_features_df.iloc[0].to_dict(), "drop_reason": "stale_data"}]),
                ranked_df=pd.DataFrame(),
            ),
        ),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    filtered_out = pd.read_csv(Path(result.run_dir) / "filtered_out.csv")
    assert filtered_out["drop_reason"].tolist() == ["stale_data"]
    assert filtered_out["as_of_date"].tolist() == ["2026-03-24"]
    assert filtered_out["data_end_date"].tolist() == ["2026-03-18"]


def test_run_screen_allocates_dual_market_candidates_with_floor_and_global_backfill(tmp_path):
    config = ScreenRunConfig(
        markets=["cn", "us"],
        as_of_date="2026-03-24",
        top_k=4,
        output_dir=str(tmp_path),
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "Technology", "list_date": "19801212"},
        ]
    )
    ranked_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "us", "global_rank": 1, "market_rank": 1, "total_score": 9.5},
            {"symbol": "MSFT", "market": "us", "global_rank": 2, "market_rank": 2, "total_score": 8.5},
            {"symbol": "NVDA", "market": "us", "global_rank": 3, "market_rank": 3, "total_score": 8.0},
            {"symbol": "600519.SH", "market": "cn", "global_rank": 4, "market_rank": 1, "total_score": 7.8},
            {"symbol": "000001.SZ", "market": "cn", "global_rank": 5, "market_rank": 2, "total_score": 7.2},
            {"symbol": "AMZN", "market": "us", "global_rank": 6, "market_rank": 4, "total_score": 7.0},
        ]
    )

    with (
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=_universe_stage(universe_df)),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                kept_df=ranked_df,
                ranked_df=ranked_df,
            ),
        ),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    candidates = pd.read_csv(Path(result.run_dir) / "candidates.csv")
    assert candidates["symbol"].tolist() == ["AAPL", "MSFT", "600519.SH", "000001.SZ"]
    assert candidates["market"].tolist() == ["us", "us", "cn", "cn"]


def test_run_screen_backfills_from_global_ranking_when_one_market_cannot_fill_floor(tmp_path):
    config = ScreenRunConfig(
        markets=["cn", "us"],
        as_of_date="2026-03-24",
        top_k=4,
        output_dir=str(tmp_path),
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "Technology", "list_date": "19801212"},
        ]
    )
    ranked_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "us", "global_rank": 1, "market_rank": 1, "total_score": 9.5},
            {"symbol": "MSFT", "market": "us", "global_rank": 2, "market_rank": 2, "total_score": 8.5},
            {"symbol": "NVDA", "market": "us", "global_rank": 3, "market_rank": 3, "total_score": 8.0},
            {"symbol": "600519.SH", "market": "cn", "global_rank": 4, "market_rank": 1, "total_score": 7.8},
            {"symbol": "AMZN", "market": "us", "global_rank": 5, "market_rank": 4, "total_score": 7.0},
        ]
    )

    with (
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=_universe_stage(universe_df)),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                kept_df=ranked_df,
                ranked_df=ranked_df,
            ),
        ),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    candidates = pd.read_csv(Path(result.run_dir) / "candidates.csv")
    assert candidates["symbol"].tolist() == ["AAPL", "MSFT", "NVDA", "600519.SH"]
    assert candidates["market"].tolist() == ["us", "us", "us", "cn"]


def test_run_screen_keeps_single_market_selection_as_plain_top_k(tmp_path):
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=2,
        output_dir=str(tmp_path),
        us_manifest_path="/tmp/us.csv",
    )
    universe_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "Technology", "list_date": "19801212"},
        ]
    )
    ranked_df = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "us", "global_rank": 1, "market_rank": 1, "total_score": 9.5},
            {"symbol": "MSFT", "market": "us", "global_rank": 2, "market_rank": 2, "total_score": 8.5},
            {"symbol": "NVDA", "market": "us", "global_rank": 3, "market_rank": 3, "total_score": 8.0},
        ]
    )

    with (
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=_universe_stage(universe_df)),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                kept_df=ranked_df,
                ranked_df=ranked_df,
            ),
        ),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    candidates = pd.read_csv(Path(result.run_dir) / "candidates.csv")
    assert candidates["symbol"].tolist() == ["AAPL", "MSFT"]


def test_run_screen_requires_selected_breakout_type_in_final_candidates(tmp_path):
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=3,
        breakout_types=["platform_breakout"],
        output_dir=str(tmp_path),
    )
    universe_df = pd.DataFrame(
        [
            {"symbol": "300308.SZ", "market": "cn", "name": "No Breakout", "exchange": "SZSE", "sector": "Technology", "list_date": "20120927"},
            {"symbol": "600519.SH", "market": "cn", "name": "Platform Hit", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "688256.SH", "market": "cn", "name": "Wrong Breakout", "exchange": "SSE", "sector": "Technology", "list_date": "20200722"},
            {"symbol": "000001.SZ", "market": "cn", "name": "Volume Hit", "exchange": "SZSE", "sector": "Banking", "list_date": "19910403"},
        ]
    )
    ranked_df = pd.DataFrame(
        [
            {
                "symbol": "300308.SZ",
                "market": "cn",
                "global_rank": 1,
                "market_rank": 1,
                "total_score": 9.8,
                "breakout_hit": False,
                "breakout_type": None,
                "breakout_with_volume": False,
            },
            {
                "symbol": "688256.SH",
                "market": "cn",
                "global_rank": 2,
                "market_rank": 2,
                "total_score": 8.4,
                "breakout_hit": True,
                "breakout_type": "box_breakout",
                "breakout_with_volume": True,
            },
            {
                "symbol": "600519.SH",
                "market": "cn",
                "global_rank": 3,
                "market_rank": 3,
                "total_score": 7.2,
                "breakout_hit": True,
                "breakout_type": "platform_breakout",
                "breakout_with_volume": False,
            },
            {
                "symbol": "000001.SZ",
                "market": "cn",
                "global_rank": 4,
                "market_rank": 4,
                "total_score": 6.9,
                "breakout_hit": True,
                "breakout_type": "platform_breakout",
                "breakout_with_volume": True,
            },
        ]
    )

    with (
        patch("diverge.screener.pipeline.prepare_universe_stage", return_value=_universe_stage(universe_df)),
        patch(
            "diverge.screener.pipeline.evaluate_screen_stage",
            return_value=_evaluation_stage(
                kept_df=ranked_df,
                ranked_df=ranked_df,
            ),
        ),
        patch("diverge.screener.storage.datetime", _FixedDateTime),
    ):
        result = run_screen(config)

    candidates = pd.read_csv(Path(result.run_dir) / "candidates.csv")
    assert result.candidate_count == 2
    assert candidates["symbol"].tolist() == ["600519.SH", "000001.SZ"]
    assert candidates["breakout_type"].tolist() == ["platform_breakout", "platform_breakout"]
