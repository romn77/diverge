from __future__ import annotations

import pandas as pd

from tradingagents.screener.schema import ScreenRunConfig
from tradingagents.screener.universe_prefilter import apply_universe_prefilters


def test_apply_universe_prefilters_drops_recent_listings_before_history():
    universe = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "market": "cn",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "sector": "Liquor",
                "list_date": "20010827",
            },
            {
                "symbol": "301000.SZ",
                "market": "cn",
                "name": "Recent Listing",
                "exchange": "SZSE",
                "sector": "Technology",
                "list_date": "20260115",
            },
        ]
    )
    config = ScreenRunConfig(markets=["cn"], as_of_date="2026-03-24", top_k=20)

    kept, dropped = apply_universe_prefilters(universe, config)

    assert kept["symbol"].tolist() == ["600519.SH"]
    assert dropped["symbol"].tolist() == ["301000.SZ"]
    assert dropped["drop_reason"].tolist() == ["too_new"]


def test_apply_universe_prefilters_drops_non_primary_us_issues_but_keeps_etfs():
    universe = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "",
            },
            {
                "symbol": "QQQ",
                "market": "us",
                "name": "Invesco QQQ Trust, Series 1",
                "exchange": "NASDAQ",
                "sector": "Equity",
                "list_date": "",
            },
            {
                "symbol": "BRK.B",
                "market": "us",
                "name": "Berkshire Hathaway, Inc.",
                "exchange": "NYSE",
                "sector": "Insurance",
                "list_date": "",
            },
            {
                "symbol": "MKC.V",
                "market": "us",
                "name": "McCormick & Co., Inc.",
                "exchange": "NYSE",
                "sector": "Consumer Staples",
                "list_date": "",
            },
            {
                "symbol": "AACT",
                "market": "us",
                "name": "Ares Acquisition Corp. II",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
            },
            {
                "symbol": "AACT.U",
                "market": "us",
                "name": "Ares Acquisition Corporation II Unit",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
            },
            {
                "symbol": "CLACW",
                "market": "us",
                "name": "Capitol Acquisition Corp. V Warrant",
                "exchange": "NASDAQ",
                "sector": "",
                "list_date": "",
            },
            {
                "symbol": "ATEST.A",
                "market": "us",
                "name": "Tick Pilot Test Group 1",
                "exchange": "AMEX",
                "sector": "",
                "list_date": "",
            },
            {
                "symbol": "CTEST.C",
                "market": "us",
                "name": "CTEST.C",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
            },
            {
                "symbol": "MGR.L",
                "market": "us",
                "name": "MGR.L",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
            },
        ]
    )
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us_manifest.csv")

    kept, dropped = apply_universe_prefilters(universe, config)

    assert kept["symbol"].tolist() == ["AAPL", "QQQ", "BRK.B", "MKC.V"]
    assert dropped["symbol"].tolist() == ["AACT", "AACT.U", "CLACW", "ATEST.A", "CTEST.C", "MGR.L"]
    assert dropped["drop_reason"].tolist() == [
        "us_spac",
        "us_non_primary_issue",
        "us_non_primary_issue",
        "us_test_listing",
        "us_test_listing",
        "us_symbol_variant",
    ]
