from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tradingagents.data.us_manifest import build_us_manifest, write_us_manifest


def test_write_us_manifest_maps_akshare_us_spot_to_manifest_csv(tmp_path):
    source_df = pd.DataFrame(
        [
            {
                "name": "NVIDIA Corp.",
                "cname": "英伟达公司",
                "category": "半导体",
                "symbol": "NVDA",
                "market": "NASDAQ",
                "mktcap": "2.0e12",
            },
            {
                "name": "Apple, Inc.",
                "cname": "苹果公司",
                "category": "计算机",
                "symbol": "AAPL",
                "market": "NASDAQ",
                "mktcap": "3.0e12",
            },
        ]
    )
    output_path = tmp_path / "us_manifest.csv"

    manifest_df = write_us_manifest(
        source_df=source_df,
        output_path=output_path,
        limit=1,
    )

    assert output_path.is_file()
    assert manifest_df.to_dict("records") == [
        {
            "symbol": "AAPL",
            "name": "Apple, Inc.",
            "exchange": "NASDAQ",
            "sector": "计算机",
            "list_date": "",
            "mktcap": 3_000_000_000_000.0,
        }
    ]
    written_df = pd.read_csv(output_path, keep_default_na=False)
    assert written_df.to_dict("records") == [
        {
            "symbol": "AAPL",
            "name": "Apple, Inc.",
            "exchange": "NASDAQ",
            "sector": "计算机",
            "list_date": "",
            "mktcap": 3_000_000_000_000.0,
        }
    ]


def test_build_us_manifest_sorts_by_market_cap_before_dedup_and_limit():
    source_df = pd.DataFrame(
        [
            {
                "name": "Small Duplicate",
                "category": "软件",
                "symbol": "DUP",
                "market": "NASDAQ",
                "mktcap": "10",
            },
            {
                "name": "Large Duplicate",
                "category": "软件",
                "symbol": "DUP",
                "market": "NASDAQ",
                "mktcap": "100",
            },
            {
                "name": "Largest",
                "category": "半导体",
                "symbol": "TOP",
                "market": "NASDAQ",
                "mktcap": "1000",
            },
        ]
    )

    manifest_df = build_us_manifest(source_df=source_df, limit=2)

    assert manifest_df.to_dict("records") == [
        {
            "symbol": "TOP",
            "name": "Largest",
            "exchange": "NASDAQ",
            "sector": "半导体",
            "list_date": "",
            "mktcap": 1000.0,
        },
        {
            "symbol": "DUP",
            "name": "Large Duplicate",
            "exchange": "NASDAQ",
            "sector": "软件",
            "list_date": "",
            "mktcap": 100.0,
        },
    ]


def test_build_us_manifest_requires_market_cap_field():
    source_df = pd.DataFrame(
        [
            {
                "name": "NVIDIA Corp.",
                "category": "半导体",
                "symbol": "NVDA",
                "market": "NASDAQ",
            }
        ]
    )

    with pytest.raises(ValueError, match="mktcap"):
        build_us_manifest(source_df=source_df, limit=1)


def test_build_us_manifest_filters_non_common_stock_rows_before_limit():
    source_df = pd.DataFrame(
        [
            {
                "name": "Invesco QQQ Trust, Series 1",
                "category": "ETF",
                "symbol": "QQQ",
                "market": "NASDAQ",
                "mktcap": "5000",
            },
            {
                "name": "Example ADR",
                "category": "Finance",
                "symbol": "EADR",
                "market": "NYSE",
                "mktcap": "4000",
            },
            {
                "name": "Example Preferred Stock",
                "category": "Finance",
                "symbol": "EPRF",
                "market": "NYSE",
                "mktcap": "3000",
            },
            {
                "name": "Apple, Inc.",
                "category": "计算机",
                "symbol": "AAPL",
                "market": "NASDAQ",
                "mktcap": "2000",
            },
            {
                "name": "Microsoft Corp.",
                "category": "软件",
                "symbol": "MSFT",
                "market": "NASDAQ",
                "mktcap": "1000",
            },
        ]
    )

    manifest_df = build_us_manifest(source_df=source_df, limit=1)

    assert manifest_df.to_dict("records") == [
        {
            "symbol": "AAPL",
            "name": "Apple, Inc.",
            "exchange": "NASDAQ",
            "sector": "计算机",
            "list_date": "",
            "mktcap": 2000.0,
        }
    ]
