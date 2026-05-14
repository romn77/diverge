from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from diverge.screener.market_data import fetch_history_for_universe


def test_fetch_history_for_universe_cache_only_does_not_call_external_vendor(tmp_path):
    universe = pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "market": "us",
                "name": "Microsoft",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19860313",
            }
        ]
    )

    with patch(
        "diverge.screener.market_data.fetch_price_history"
    ) as fetch_price_history:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-04-28",
            history_dir=tmp_path / "history",
            cache_dir=tmp_path / "cache",
            checkpoint_dir=tmp_path / "checkpoints",
            cache_only=True,
        )

    fetch_price_history.assert_not_called()
    assert histories == {}
    assert failures.to_dict("records") == [
        {"symbol": "MSFT", "market": "us", "drop_reason": "history_cache_miss"}
    ]
