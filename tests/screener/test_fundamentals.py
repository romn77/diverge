from __future__ import annotations

import pandas as pd

from tradingagents.screener.fundamentals import enrich_features_with_fundamentals
from tradingagents.screener.schema import ScreenRunConfig


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
