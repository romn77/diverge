from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from typer.testing import CliRunner

from cli.main import app
from tradingagents.screener.debug import ScreenDebugResult
from tradingagents.screener.replay import HardFilterReplayResult
from tradingagents.screener.schema import ScreenRunResult


runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _FixedDateTime:
    @classmethod
    def now(cls, tz=None):
        return cls()

    def strftime(self, fmt):
        if fmt == "%Y-%m-%d":
            return "2026-04-14"
        if fmt == "%Y%m%d_%H%M%S":
            return "20260414_120000"
        raise AssertionError(f"unexpected format: {fmt}")


def _base_feature_row(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "market": "cn",
        "name": symbol,
        "exchange": "SZSE",
        "sector": "Technology",
        "list_date": "20000101",
        "as_of_date": "2026-03-24",
        "close": 10.0,
        "volume": 1000.0,
        "amount": 100000.0,
        "avg_amount_20d": 80_000_000.0,
        "ma20": 9.5,
        "ma60": 9.0,
        "ret_20": 0.1,
        "ret_60": 0.2,
        "rsi": 55.0,
        "macd": 1.0,
        "macds": 0.8,
        "macdh": 0.2,
        "atr": 0.5,
        "atr_pct": 0.05,
        "boll": 9.3,
        "boll_ub": 10.4,
        "boll_lb": 8.2,
        "vwma": 9.7,
        "mfi": 50.0,
        "data_start_date": "2025-12-01",
        "data_end_date": "2026-03-24",
        "bar_count": 80,
        "trading_days_20d": 20,
    }


def _write_replay_run_artifacts(
    run_dir: Path,
    features_df: pd.DataFrame,
    filtered_out_df: pd.DataFrame,
) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "features.csv").write_text(features_df.to_csv(index=False), encoding="utf-8")
    (run_dir / "filtered_out.csv").write_text(filtered_out_df.to_csv(index=False), encoding="utf-8")
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "run_timestamp": run_dir.name,
                "as_of_date": "2026-03-24",
                "config": {
                    "markets": ["cn"],
                    "as_of_date": "2026-03-24",
                    "top_k": 20,
                    "output_dir": str(run_dir.parent),
                    "cn_data_source": "tushare",
                    "cn_data_source_fallbacks": [],
                    "cn_manifest_path": None,
                    "us_manifest_path": None,
                },
                "artifact_paths": {
                    "run_meta": str(run_dir / "run_meta.json"),
                    "features": str(run_dir / "features.csv"),
                    "filtered_out": str(run_dir / "filtered_out.csv"),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_screen_command_requires_us_manifest_for_us_market():
    result = runner.invoke(
        app,
        [
            "screen",
            "--date",
            "2026-03-24",
            "--markets",
            "cn,us",
            "--top-k",
            "20",
        ],
    )

    assert result.exit_code != 0
    assert "us-manifest" in result.output


def test_screen_command_help_does_not_expose_limit_per_market_option():
    result = runner.invoke(app, ["screen", "--help"])

    assert result.exit_code == 0
    assert "--limit-per-market" not in result.output


def test_screen_command_prints_progress_and_result_summary():
    def fake_run_screen(config, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                "history",
                1,
                2,
                "600519.SH",
                status="cache_hit",
                detail="cache=2025-02-17..2026-03-24",
            )
            progress_callback(
                "history",
                2,
                2,
                "AAPL",
                status="fetch_tail",
                detail="cache=2025-02-17..2026-03-21 fetch=2026-03-22..2026-03-24 source=yfinance",
            )

        return ScreenRunResult(
            run_dir=Path("/tmp/results/screener/20260324_214530"),
            universe_count_by_market={"cn": 1, "us": 1},
            fetch_failed_count=1,
            filtered_count_by_reason={"fetch_failed": 1, "illiquid_us": 2},
            candidate_count=2,
            candidate_preview=[
                {
                    "symbol": "600519.SH",
                    "market": "cn",
                    "global_rank": 1,
                    "total_score": 1.23,
                },
                {
                    "symbol": "AAPL",
                    "market": "us",
                    "global_rank": 2,
                    "total_score": 0.91,
                },
            ],
        )

    with patch("cli.main.run_screen", side_effect=fake_run_screen):
        result = runner.invoke(
            app,
            [
                "screen",
                "--date",
                "2026-03-24",
                "--markets",
                "cn,us",
                "--top-k",
                "20",
                "--us-manifest",
                "/tmp/us_manifest.csv",
            ],
        )

    assert result.exit_code == 0
    assert "history 1/2 600519.SH [cache_hit]" in result.output
    assert "history 2/2 AAPL [fetch_tail]" in result.output
    assert "Universe counts" in result.output
    assert "fetch_failed: 1" in result.output
    assert "600519.SH" in result.output
    assert "/tmp/results/screener/20260324_214530" in result.output


def test_screen_command_accepts_cn_data_source_override():
    captured = {}

    def fake_run_screen(config, progress_callback=None):
        captured["cn_data_source"] = config.cn_data_source
        captured["cn_data_source_fallbacks"] = config.cn_data_source_fallbacks
        return ScreenRunResult(
            run_dir=Path("/tmp/results/screener/20260324_214530"),
            universe_count_by_market={"cn": 1},
            fetch_failed_count=0,
            filtered_count_by_reason={},
            candidate_count=0,
            candidate_preview=[],
        )

    with patch("cli.main.run_screen", side_effect=fake_run_screen):
        result = runner.invoke(
            app,
            [
                "screen",
                "--date",
                "2026-03-24",
                "--markets",
                "cn",
                "--top-k",
                "20",
                "--cn-data-source",
                "akshare",
                "--cn-data-source-fallbacks",
                "tushare",
            ],
        )

    assert result.exit_code == 0
    assert captured["cn_data_source"] == "akshare"
    assert captured["cn_data_source_fallbacks"] == ["tushare"]


def test_screen_command_accepts_cn_manifest_override():
    captured = {}

    def fake_run_screen(config, progress_callback=None):
        captured["cn_manifest_path"] = config.cn_manifest_path
        return ScreenRunResult(
            run_dir=Path("/tmp/results/screener/20260324_214530"),
            universe_count_by_market={"cn": 1},
            fetch_failed_count=0,
            filtered_count_by_reason={},
            candidate_count=0,
            candidate_preview=[],
        )

    with patch("cli.main.run_screen", side_effect=fake_run_screen):
        result = runner.invoke(
            app,
            [
                "screen",
                "--date",
                "2026-03-24",
                "--markets",
                "cn",
                "--top-k",
                "20",
                "--cn-manifest",
                "/tmp/cn_manifest.csv",
            ],
        )

    assert result.exit_code == 0
    assert captured["cn_manifest_path"] == "/tmp/cn_manifest.csv"


def test_screen_command_defaults_date_to_today_when_omitted():
    captured = {}

    def fake_run_screen(config, progress_callback=None):
        captured["as_of_date"] = config.as_of_date
        return ScreenRunResult(
            run_dir=Path("/tmp/results/screener/20260414_120000"),
            universe_count_by_market={"cn": 1},
            fetch_failed_count=0,
            filtered_count_by_reason={},
            candidate_count=0,
            candidate_preview=[],
        )

    with (
        patch("cli.main.run_screen", side_effect=fake_run_screen),
        patch("cli.main.datetime.datetime", _FixedDateTime),
    ):
        result = runner.invoke(
            app,
            [
                "screen",
                "--markets",
                "cn",
                "--top-k",
                "20",
            ],
        )

    assert result.exit_code == 0
    assert captured["as_of_date"] == "2026-04-14"


def test_screen_debug_command_prints_stage_summary_for_ranked_symbol():
    debug_result = ScreenDebugResult(
        symbol="AAPL",
        market="us",
        as_of_date="2026-03-24",
        universe_row={
            "symbol": "AAPL",
            "market": "us",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "list_date": "19801212",
        },
        history_rows=65,
        history_start_date="2025-12-17",
        history_end_date="2026-03-24",
        feature_row={
            "symbol": "AAPL",
            "market": "us",
            "close": 101.0,
            "avg_amount_20d": 20_000_000.0,
        },
        score_row={
            "symbol": "AAPL",
            "market": "us",
            "global_rank": 1,
            "market_rank": 1,
            "total_score": 0.71,
            "strategy_tags": "trend_up,momentum_positive,above_vwma",
            "risk_flags": "",
        },
    )

    with patch("cli.main.debug_screen_symbol", return_value=debug_result):
        result = runner.invoke(
            app,
            [
                "screen-debug",
                "--symbol",
                "AAPL",
                "--market",
                "us",
                "--date",
                "2026-03-24",
                "--us-manifest",
                "/tmp/us_manifest.csv",
            ],
        )

    assert result.exit_code == 0
    assert "Debug target" in result.output
    assert "Universe match" in result.output
    assert "History summary" in result.output
    assert "Feature row" in result.output
    assert "Hard filter result" in result.output
    assert "kept" in result.output
    assert "Rank result" in result.output
    assert "total_score" in result.output


def test_screen_debug_command_defaults_date_to_today_when_omitted():
    captured = {}

    def fake_debug_screen_symbol(config, symbol, market):
        captured["as_of_date"] = config.as_of_date
        return ScreenDebugResult(
            symbol=symbol,
            market=market,
            as_of_date=config.as_of_date,
            universe_row={
                "symbol": symbol,
                "market": market,
            },
        )

    with (
        patch("cli.main.debug_screen_symbol", side_effect=fake_debug_screen_symbol),
        patch("cli.main.datetime.datetime", _FixedDateTime),
    ):
        result = runner.invoke(
            app,
            [
                "screen-debug",
                "--symbol",
                "AAPL",
                "--market",
                "us",
                "--us-manifest",
                "/tmp/us_manifest.csv",
            ],
        )

    assert result.exit_code == 0
    assert captured["as_of_date"] == "2026-04-14"


def test_screen_replay_command_prints_summary_for_matching_run():
    replay_result = HardFilterReplayResult(
        run_dir=Path("/tmp/results/screener/20260324_214530"),
        features_count=12,
        kept_count=10,
        replay_filtered_count_by_reason={"illiquid_cn": 2},
        saved_filtered_count_by_reason={"illiquid_cn": 2},
        saved_filtered_out_present=True,
        exported_filtered_out_path=Path("/tmp/replayed_filtered_out.csv"),
    )

    with patch("cli.main.replay_screen_hard_filters", return_value=replay_result):
        result = runner.invoke(
            app,
            [
                "screen-replay",
                "/tmp/results/screener/20260324_214530",
                "--export-filtered-out",
                "/tmp/replayed_filtered_out.csv",
            ],
        )

    assert result.exit_code == 0
    assert "Replay hard-filter counts" in result.output
    assert "illiquid_cn: 2" in result.output
    assert "Replay matches saved hard-filter rows." in result.output
    assert "/tmp/replayed_filtered_out.csv" in result.output


def test_screen_replay_command_fails_when_saved_rows_do_not_match():
    replay_result = HardFilterReplayResult(
        run_dir=Path("/tmp/results/screener/20260324_214530"),
        features_count=2,
        kept_count=1,
        replay_filtered_count_by_reason={"low_price_cn": 1},
        saved_filtered_count_by_reason={"missing_features": 1},
        new_drops=[{"symbol": "000002.SZ", "market": "cn", "drop_reason": "low_price_cn"}],
        missing_drops=[{"symbol": "000003.SZ", "market": "cn", "drop_reason": "missing_features"}],
        saved_filtered_out_present=True,
    )

    with patch("cli.main.replay_screen_hard_filters", return_value=replay_result):
        result = runner.invoke(
            app,
            [
                "screen-replay",
                "/tmp/results/screener/20260324_214530",
            ],
        )

    assert result.exit_code == 1
    assert "Replay differs from saved hard-filter rows." in result.output
    assert "+ 000002.SZ (cn) low_price_cn" in result.output
    assert "- 000003.SZ (cn) missing_features" in result.output


def test_main_py_screen_replay_command_dispatches_to_typer_app(tmp_path):
    run_dir = tmp_path / "20260324_214530"
    features_df = pd.DataFrame(
        [
            _base_feature_row("000001.SZ"),
            {**_base_feature_row("000002.SZ"), "close": 2.5},
        ]
    )
    filtered_out_df = pd.DataFrame(
        [
            {"symbol": "000002.SZ", "market": "cn", "drop_reason": "low_price_cn"},
        ]
    )
    _write_replay_run_artifacts(run_dir, features_df, filtered_out_df)

    result = subprocess.run(
        [sys.executable, "main.py", "screen-replay", str(run_dir)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Replay hard-filter counts" in result.stdout
    assert "low_price_cn: 1" in result.stdout
    assert "Replay matches saved hard-filter rows." in result.stdout
