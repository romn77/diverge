from __future__ import annotations

import pandas as pd

from diverge.screener.fundamentals import (
    enrich_features_with_fundamentals,
    load_fundamental_snapshots,
)
from diverge.screener.schema import ScreenRunConfig


def test_enrich_features_with_fundamentals_reads_cached_snapshot(tmp_path):
    snapshot_dir = tmp_path / "simfin" / "us"
    snapshot_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "market": "us",
                "source": "simfin",
                "as_of_date": "2026-04-28",
                "report_period": "2025-12-31",
                "market_cap": 100.0,
                "pe_ttm": 25.0,
                "roe": 0.20,
                "revenue_growth_yoy": 0.12,
                "data_status": "partial",
            }
        ]
    ).to_csv(snapshot_dir / "snapshots.csv", index=False)
    features = pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "market": "us",
                "name": "Microsoft",
                "exchange": "NASDAQ",
                "sector": "Technology",
            }
        ]
    )
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-04-28",
        top_k=10,
        us_manifest_path="/tmp/us.csv",
        include_fundamentals=True,
        fundamental_dir=str(tmp_path),
    )

    enriched = enrich_features_with_fundamentals(features, config)

    row = enriched.iloc[0]
    assert row["market_cap"] == 100.0
    assert row["pe_ttm"] == 25.0
    assert row["roe"] == 0.20
    assert row["fundamental_source"] == "simfin"
    assert row["fundamental_data_status"] == "partial"


def test_enrich_features_with_fundamentals_merges_split_snapshots_by_field(tmp_path):
    tencent_dir = tmp_path / "tencent" / "us"
    tencent_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "market": "us",
                "source": "tencent",
                "as_of_date": "2026-04-28",
                "market_cap": 120.0,
                "pe_ttm": 24.0,
                "pb": 8.0,
                "currency": "USD",
            }
        ]
    ).to_csv(tencent_dir / "market_snapshots.csv", index=False)
    fmp_dir = tmp_path / "fmp" / "us"
    fmp_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "market": "us",
                "source": "fmp",
                "report_period": "2025-12-31",
                "roe": 0.20,
                "gross_margin": 0.68,
                "revenue_growth_yoy": 0.12,
                "currency": "USD",
            }
        ]
    ).to_csv(fmp_dir / "financial_snapshots.csv", index=False)
    features = pd.DataFrame([{"symbol": "MSFT", "market": "us"}])
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-04-28",
        top_k=10,
        us_manifest_path="/tmp/us.csv",
        include_fundamentals=True,
        fundamental_dir=str(tmp_path),
    )

    enriched = enrich_features_with_fundamentals(features, config)

    row = enriched.iloc[0]
    assert row["market_cap"] == 120.0
    assert row["market_cap_source"] == "tencent"
    assert row["roe"] == 0.20
    assert row["roe_source"] == "fmp"
    assert row["market_snapshot_coverage"] > 0
    assert row["financial_snapshot_coverage"] > 0
    assert row["fundamental_data_status"] == "partial"


def test_load_fundamental_snapshots_ignores_expired_financial_fields(tmp_path):
    fmp_dir = tmp_path / "fmp" / "us"
    fmp_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "market": "us",
                "source": "fmp",
                "report_period": "2022-03-31",
                "roe": 0.20,
            }
        ]
    ).to_csv(fmp_dir / "financial_snapshots.csv", index=False)
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-04-28",
        top_k=10,
        us_manifest_path="/tmp/us.csv",
        include_fundamentals=True,
        fundamental_dir=str(tmp_path),
    )

    snapshots = load_fundamental_snapshots(config)

    row = snapshots.iloc[0]
    assert pd.isna(row["roe"])
    assert row["financial_snapshot_freshness_status"] == "missing"


def test_enrich_features_marks_missing_snapshot_without_fetching(tmp_path):
    features = pd.DataFrame([{"symbol": "AAPL", "market": "us"}])
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-04-28",
        top_k=10,
        us_manifest_path="/tmp/us.csv",
        include_fundamentals=True,
        fundamental_dir=str(tmp_path),
    )

    enriched = enrich_features_with_fundamentals(features, config)

    assert enriched["fundamental_data_status"].tolist() == ["missing_snapshot"]
    assert "market_cap" in enriched.columns
