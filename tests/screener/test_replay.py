from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from diverge.screener.replay import replay_screen_hard_filters


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


def _write_run_artifacts(
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


def test_replay_screen_hard_filters_matches_saved_hard_filter_rows(tmp_path):
    run_dir = tmp_path / "20260324_214530"
    kept_row = _base_feature_row("000001.SZ")
    dropped_row = {**_base_feature_row("000002.SZ"), "close": 2.5}

    features_df = pd.DataFrame([kept_row, dropped_row])
    filtered_out_df = pd.DataFrame(
        [
            {"symbol": "301000.SZ", "market": "cn", "drop_reason": "too_new"},
            {"symbol": "000002.SZ", "market": "cn", "drop_reason": "low_price_cn"},
        ]
    )
    _write_run_artifacts(run_dir, features_df, filtered_out_df)

    result = replay_screen_hard_filters(run_dir)

    assert result.features_count == 2
    assert result.kept_count == 1
    assert result.replay_filtered_count_by_reason == {"low_price_cn": 1}
    assert result.saved_filtered_count_by_reason == {"low_price_cn": 1}
    assert result.matches_saved is True
    assert result.new_drops == []
    assert result.missing_drops == []


def test_replay_screen_hard_filters_detects_diffs_and_exports_csv(tmp_path):
    run_dir = tmp_path / "20260324_214530"
    features_df = pd.DataFrame([{**_base_feature_row("000002.SZ"), "close": 2.5}])
    filtered_out_df = pd.DataFrame(
        [
            {"symbol": "000003.SZ", "market": "cn", "drop_reason": "missing_features"},
        ]
    )
    _write_run_artifacts(run_dir, features_df, filtered_out_df)

    export_path = tmp_path / "replayed_filtered_out.csv"
    result = replay_screen_hard_filters(
        run_dir,
        export_filtered_out_path=export_path,
    )

    assert result.matches_saved is False
    assert result.new_drops == [
        {"symbol": "000002.SZ", "market": "cn", "drop_reason": "low_price_cn"}
    ]
    assert result.missing_drops == [
        {"symbol": "000003.SZ", "market": "cn", "drop_reason": "missing_features"}
    ]
    assert result.exported_filtered_out_path == export_path
    replayed_filtered_out = pd.read_csv(export_path)
    assert replayed_filtered_out["drop_reason"].tolist() == ["low_price_cn"]


def test_replay_screen_hard_filters_prefers_supplied_run_dir_artifacts(tmp_path):
    original_run_dir = tmp_path / "original" / "20260324_214530"
    copied_run_dir = tmp_path / "copied" / "20260324_214530"

    original_features_df = pd.DataFrame([_base_feature_row("000001.SZ")])
    empty_filtered_out_df = pd.DataFrame(columns=["symbol", "market", "drop_reason"])
    _write_run_artifacts(original_run_dir, original_features_df, empty_filtered_out_df)

    shutil.copytree(original_run_dir, copied_run_dir)

    copied_features_df = pd.DataFrame([{**_base_feature_row("000002.SZ"), "close": 2.5}])
    (copied_run_dir / "features.csv").write_text(
        copied_features_df.to_csv(index=False),
        encoding="utf-8",
    )

    result = replay_screen_hard_filters(copied_run_dir)

    assert result.features_count == 1
    assert result.replay_filtered_count_by_reason == {"low_price_cn": 1}
    assert result.saved_filtered_count_by_reason == {}
    assert result.matches_saved is False
    assert result.new_drops == [
        {"symbol": "000002.SZ", "market": "cn", "drop_reason": "low_price_cn"}
    ]
    assert result.missing_drops == []
