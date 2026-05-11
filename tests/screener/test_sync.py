from __future__ import annotations

import json

import pandas as pd

from diverge.screener import sync


def test_normalize_simfin_snapshot_keeps_latest_values_and_optional_missing_fields():
    frame = pd.DataFrame(
        [
            {
                "Ticker": "MSFT",
                "Date": "2025-01-01",
                "Market-Cap": 100.0,
                "P/E": 20.0,
                "Return on Equity": 0.20,
            },
            {
                "Ticker": "MSFT",
                "Date": "2025-04-01",
                "Market-Cap": 120.0,
                "P/E": 25.0,
                "Return on Equity": 0.25,
                "Sales Growth": 0.11,
            },
        ]
    )

    snapshot = sync._normalize_simfin_snapshot(frame, as_of_date="2026-04-28")

    row = snapshot.iloc[0]
    assert row["symbol"] == "MSFT"
    assert row["market_cap"] == 120.0
    assert row["pe_ttm"] == 25.0
    assert row["roe"] == 0.25
    assert row["revenue_growth_yoy"] == 0.11
    assert "pb" in row["missing_fields"]


def test_save_fundamental_snapshot_writes_split_csv_and_meta(tmp_path):
    frame = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "source": "simfin",
                "market_cap": 100.0,
                "pe_ttm": 20.0,
            }
        ]
    )
    result = sync.SyncResult(
        sync_type="fundamentals",
        markets=["us"],
        source="simfin",
        status="completed",
    )

    saved = sync._save_fundamental_snapshot(
        frame,
        base_dir=tmp_path,
        market="us",
        source="simfin",
        sync_result=result,
        snapshot_type="market",
    )

    assert saved.rows_written == 1
    assert saved.snapshot_path is not None
    assert saved.meta_path is not None
    assert pd.read_csv(saved.snapshot_path)["symbol"].tolist() == ["AAPL"]
    meta = json.loads(open(saved.meta_path, encoding="utf-8").read())
    assert meta["schema_version"] == "fundamental_snapshot.v1"
    assert meta["snapshot_type"] == "market"
    assert meta["field_coverage"] > 0
    assert "peg" in meta["missing_fields"]
    assert saved.snapshot_paths["market"] == saved.snapshot_path


def test_normalize_tushare_indicator_frame_maps_cn_fields():
    frame = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "end_date": "20231231",
                "roe": 30.0,
                "grossprofit_margin": 92.0,
                "netprofit_margin": 52.0,
                "current_ratio": 2.1,
                "debt_to_assets": 20.0,
            }
        ]
    )

    snapshot = sync._normalize_tushare_indicator_frame(frame, as_of_date="2026-04-28")

    row = snapshot.iloc[0]
    assert row["symbol"] == "600519.SH"
    assert row["market"] == "cn"
    assert row["source"] == "tushare"
    assert row["roe"] == 0.30
    assert row["gross_margin"] == 0.92
    assert row["current_ratio"] == 2.1


def test_normalize_tushare_daily_basic_frame_maps_screening_fields():
    frame = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260428",
                "turnover_rate": 45.0,
                "pe_ttm": 24.0,
                "pb": 8.5,
                "ps_ttm": 12.0,
                "total_mv": 2100000.0,
                "circ_mv": 2000000.0,
            }
        ]
    )

    snapshot = sync._normalize_tushare_daily_basic_frame(
        frame,
        as_of_date="2026-04-28",
    )

    row = snapshot.iloc[0]
    assert row["symbol"] == "600519.SH"
    assert row["market"] == "cn"
    assert row["source"] == "tushare"
    assert row["pe_ttm"] == 24.0
    assert row["pb"] == 8.5
    assert row["ps_ttm"] == 12.0
    assert row["market_cap"] == 21000000000.0
    assert row["turnover_rate"] == 0.45
