from __future__ import annotations

import pandas as pd

from diverge.screener.schema import ScreenRunConfig
from diverge.screener.universe_prefilter import apply_universe_prefilters


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
                "symbol": "430047.BJ",
                "market": "cn",
                "name": "Example BSE",
                "exchange": "BSE",
                "sector": "Industry",
                "list_date": "20200101",
            },
            {
                "symbol": "000002.SZ",
                "market": "cn",
                "name": "*ST Example",
                "exchange": "SZSE",
                "sector": "Industry",
                "list_date": "20010101",
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
    assert dict(zip(dropped["symbol"], dropped["drop_reason"])) == {
        "430047.BJ": "cn_exchange",
        "000002.SZ": "cn_special_treatment",
        "301000.SZ": "too_new",
    }


def test_apply_universe_prefilters_uses_cn_trading_days_instead_of_180_calendar_days():
    universe = pd.DataFrame(
        [
            {
                "symbol": "000001.SZ",
                "market": "cn",
                "name": "Ping An Bank",
                "exchange": "SZSE",
                "sector": "Banking",
                "list_date": "20230802",
            }
        ]
    )
    config = ScreenRunConfig(markets=["cn"], as_of_date="2024-01-25", top_k=20)

    kept, dropped = apply_universe_prefilters(universe, config)

    assert kept["symbol"].tolist() == ["000001.SZ"]
    assert dropped.empty


def test_apply_universe_prefilters_drops_non_common_us_rows_before_capping():
    universe = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "us",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "",
                "mktcap": 900,
            },
            {
                "symbol": "MSFT",
                "market": "us",
                "name": "Microsoft Corp.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "",
                "mktcap": 800,
            },
            {
                "symbol": "BRK.B",
                "market": "us",
                "name": "Berkshire Hathaway, Inc.",
                "exchange": "NYSE",
                "sector": "Insurance",
                "list_date": "",
                "mktcap": 700,
            },
            {
                "symbol": "QQQ",
                "market": "us",
                "name": "Invesco QQQ Trust, Series 1",
                "exchange": "NASDAQ",
                "sector": "Equity",
                "list_date": "",
                "mktcap": 2000,
            },
            {
                "symbol": "EADR",
                "market": "us",
                "name": "Example ADR",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
                "mktcap": 1900,
            },
            {
                "symbol": "EPRF",
                "market": "us",
                "name": "Example Preferred Stock",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
                "mktcap": 1800,
            },
            {
                "symbol": "CLACW",
                "market": "us",
                "name": "Capitol Acquisition Corp. V Warrant",
                "exchange": "NASDAQ",
                "sector": "",
                "list_date": "",
                "mktcap": 1700,
            },
            {
                "symbol": "OTCA",
                "market": "us",
                "name": "Example Off Exchange",
                "exchange": "AMEX",
                "sector": "",
                "list_date": "",
                "mktcap": 1600,
            },
            {
                "symbol": "ATEST.A",
                "market": "us",
                "name": "Tick Pilot Test Group 1",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
                "mktcap": 1500,
            },
            {
                "symbol": "MGR.L",
                "market": "us",
                "name": "MGR.L",
                "exchange": "NYSE",
                "sector": "",
                "list_date": "",
                "mktcap": 1400,
            },
        ]
    )
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_manifest_path="/tmp/us_manifest.csv",
        us_universe_cap=2,
    )

    kept, dropped = apply_universe_prefilters(universe, config)

    assert kept["symbol"].tolist() == ["AAPL", "MSFT"]
    assert dict(zip(dropped["symbol"], dropped["drop_reason"])) == {
        "QQQ": "us_fund_like",
        "EADR": "us_adr",
        "EPRF": "us_preferred",
        "CLACW": "us_non_primary_issue",
        "OTCA": "us_exchange",
        "ATEST.A": "us_test_listing",
        "MGR.L": "us_symbol_variant",
        "BRK.B": "us_cap",
    }
