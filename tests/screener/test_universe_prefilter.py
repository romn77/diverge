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
