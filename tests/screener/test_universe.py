from __future__ import annotations

from unittest.mock import Mock, patch

import os
import pandas as pd
import pytest
from requests.exceptions import ConnectionError

from diverge.dataflows.vendor_errors import VendorAuthError, VendorRetryableError
from diverge.screener.schema import ScreenRunConfig
from diverge.screener.universe import (
    load_cn_universe,
    load_universe,
    load_us_universe,
)


def test_load_cn_universe_maps_tushare_stock_basic_to_shared_shape():
    mock_client = Mock()
    mock_client.stock_basic.return_value = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "industry": "Liquor",
                "list_date": "20010827",
            },
            {
                "ts_code": "430047.BJ",
                "name": "Example BSE",
                "exchange": "BSE",
                "industry": "Industry",
                "list_date": "20200101",
            },
        ]
    )

    with patch(
        "diverge.screener.universe.get_tushare_pro_client",
        return_value=mock_client,
    ):
        result = load_cn_universe()

    assert result.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
        }
    ]


def test_load_cn_universe_maps_akshare_stock_list_to_shared_shape():
    akshare_df = pd.DataFrame(
        [
            {
                "code": "600519",
                "name": "Kweichow Moutai",
            },
            {
                "code": "430047",
                "name": "Example BSE",
            },
        ]
    )

    with patch(
        "diverge.screener.universe._load_akshare_cn_universe_rows",
        return_value=akshare_df,
    ):
        result = load_cn_universe(data_source="akshare")

    assert result.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "",
            "list_date": "",
        }
    ]


def test_load_cn_universe_retries_akshare_universe_fetch_before_succeeding():
    akshare_client = Mock()
    akshare_client.stock_info_a_code_name.side_effect = [
        ConnectionError("connection aborted"),
        pd.DataFrame(
            [
                {
                    "code": "600519",
                    "name": "Kweichow Moutai",
                }
            ]
        ),
    ]

    with (
        patch(
            "diverge.screener.universe._import_akshare",
            return_value=akshare_client,
        ),
        patch("diverge.screener.universe.time.sleep") as mock_sleep,
    ):
        result = load_cn_universe(data_source="akshare")

    assert result["symbol"].tolist() == ["600519.SH"]
    assert akshare_client.stock_info_a_code_name.call_count == 2
    sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
    assert 0.5 in sleep_values


def test_load_akshare_cn_universe_rows_uses_rate_limiter():
    akshare_client = Mock()
    akshare_df = pd.DataFrame(
        [
            {
                "code": "600519",
                "name": "Kweichow Moutai",
            }
        ]
    )

    with (
        patch("diverge.screener.universe._import_akshare", return_value=akshare_client),
        patch(
            "diverge.screener.universe.call_akshare_api", return_value=akshare_df
        ) as mock_rate_limit,
    ):
        result = load_cn_universe(data_source="akshare")

    assert result["symbol"].tolist() == ["600519.SH"]
    mock_rate_limit.assert_called_once_with(akshare_client.stock_info_a_code_name)


def test_load_cn_universe_reraises_raw_akshare_error_after_retries_exhausted():
    akshare_client = Mock()
    akshare_client.stock_info_a_code_name.side_effect = RuntimeError("akshare boom")

    with (
        patch(
            "diverge.screener.universe._import_akshare",
            return_value=akshare_client,
        ),
        patch("diverge.screener.universe.time.sleep"),
    ):
        with pytest.raises(RuntimeError, match="akshare boom"):
            load_cn_universe(data_source="akshare")


def test_load_cn_universe_reuses_fresh_akshare_cache_without_refetch(tmp_path):
    cache_dir = tmp_path / "cache"
    akshare_df = pd.DataFrame(
        [
            {
                "code": "600519",
                "name": "Kweichow Moutai",
            }
        ]
    )

    with patch(
        "diverge.screener.universe._load_akshare_cn_universe_rows",
        return_value=akshare_df,
    ) as mock_fetch:
        first_result = load_cn_universe(data_source="akshare", cache_dir=cache_dir)

    assert mock_fetch.call_count == 1
    assert first_result["symbol"].tolist() == ["600519.SH"]

    with patch(
        "diverge.screener.universe._load_akshare_cn_universe_rows",
        side_effect=AssertionError("fresh universe cache should avoid refetch"),
    ):
        second_result = load_cn_universe(data_source="akshare", cache_dir=cache_dir)

    assert second_result["symbol"].tolist() == ["600519.SH"]


def test_load_cn_universe_falls_back_to_stale_akshare_cache_on_retryable_failure(
    tmp_path,
):
    cache_dir = tmp_path / "cache"
    akshare_df = pd.DataFrame(
        [
            {
                "code": "600519",
                "name": "Kweichow Moutai",
            }
        ]
    )

    with patch(
        "diverge.screener.universe._load_akshare_cn_universe_rows",
        return_value=akshare_df,
    ):
        cached_result = load_cn_universe(data_source="akshare", cache_dir=cache_dir)

    cache_file = cache_dir / "universe" / "cn_akshare.csv"
    assert cache_file.is_file()
    stale_timestamp = cache_file.stat().st_mtime - (60 * 60 * 25)
    os.utime(cache_file, (stale_timestamp, stale_timestamp))

    with patch(
        "diverge.screener.universe._load_akshare_cn_universe_rows",
        side_effect=VendorRetryableError("akshare down"),
    ):
        fallback_result = load_cn_universe(data_source="akshare", cache_dir=cache_dir)

    assert fallback_result.to_dict("records") == cached_result.to_dict("records")


def test_load_cn_universe_falls_back_to_secondary_source_when_primary_retries_fail():
    mock_client = Mock()
    mock_client.stock_basic.return_value = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "industry": "Liquor",
                "list_date": "20010827",
            }
        ]
    )

    with (
        patch(
            "diverge.screener.universe._load_akshare_cn_universe_rows",
            side_effect=VendorRetryableError("akshare down"),
        ),
        patch(
            "diverge.screener.universe.get_tushare_pro_client",
            return_value=mock_client,
        ),
    ):
        result = load_cn_universe(
            data_source="akshare",
            fallback_data_sources=["tushare"],
        )

    assert result.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
        }
    ]


def test_load_cn_universe_falls_back_to_secondary_source_when_primary_auth_fails():
    akshare_df = pd.DataFrame(
        [
            {
                "code": "600519",
                "name": "Kweichow Moutai",
            }
        ]
    )

    with (
        patch(
            "diverge.screener.universe.get_tushare_pro_client",
            side_effect=VendorAuthError("TUSHARE_TOKEN is not configured."),
        ),
        patch(
            "diverge.screener.universe._load_akshare_cn_universe_rows",
            return_value=akshare_df,
        ),
    ):
        result = load_cn_universe(
            data_source="tushare",
            fallback_data_sources=["akshare"],
        )

    assert result.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "",
            "list_date": "",
        }
    ]


def test_load_us_universe_requires_manifest_columns(tmp_path):
    manifest_path = tmp_path / "us_manifest.csv"
    pd.DataFrame([{"symbol": "AAPL", "name": "Apple", "exchange": "NASDAQ"}]).to_csv(
        manifest_path, index=False
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        load_us_universe(str(manifest_path))


def test_load_us_universe_allows_blank_optional_values(tmp_path):
    manifest_path = tmp_path / "us_manifest.csv"
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "",
                "list_date": "",
                "mktcap": "",
            }
        ]
    ).to_csv(manifest_path, index=False)

    result = load_us_universe(str(manifest_path))

    assert result.to_dict("records") == [
        {
            "symbol": "AAPL",
            "market": "us",
            "name": "Apple",
            "exchange": "NASDAQ",
            "sector": "",
            "list_date": "",
            "mktcap": 0.0,
        }
    ]


def test_load_cn_universe_from_manifest_normalizes_rows_and_filters_bse_and_st(
    tmp_path,
):
    manifest_path = tmp_path / "cn_manifest.csv"
    pd.DataFrame(
        [
            {
                "symbol": " 600519.SH ",
                "name": " Kweichow Moutai ",
                "exchange": " SSE ",
                "sector": " Liquor ",
                "list_date": " 20010827 ",
                "mktcap": "",
            },
            {
                "symbol": "430047.BJ",
                "name": "Example BSE",
                "exchange": "BSE",
                "sector": "Industry",
                "list_date": "20100101",
                "mktcap": "",
            },
            {
                "symbol": "000002.SZ",
                "name": "*ST Example",
                "exchange": "SZSE",
                "sector": "Industry",
                "list_date": "19910129",
                "mktcap": "",
            },
        ]
    ).to_csv(manifest_path, index=False)

    result = load_cn_universe(manifest_path=str(manifest_path))

    assert result.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
        }
    ]


def test_load_cn_universe_from_manifest_requires_generated_schema_columns(tmp_path):
    manifest_path = tmp_path / "cn_manifest.csv"
    pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "sector": "Liquor",
                "list_date": "20010827",
            }
        ]
    ).to_csv(manifest_path, index=False)

    with pytest.raises(
        ValueError, match="Missing required CN manifest columns: mktcap"
    ):
        load_cn_universe(manifest_path=str(manifest_path))


def test_load_cn_universe_surfaces_clear_tushare_auth_errors():
    with patch(
        "diverge.screener.universe.get_tushare_pro_client",
        side_effect=VendorAuthError("TUSHARE_TOKEN is not configured."),
    ):
        with pytest.raises(VendorAuthError, match="TUSHARE_TOKEN"):
            load_cn_universe()


def test_load_universe_concatenates_sources_without_truncation(tmp_path):
    manifest_path = tmp_path / "us_manifest.csv"
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "name": "Apple",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19801212",
                "mktcap": "300",
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "list_date": "19860313",
                "mktcap": "200",
            },
        ]
    ).to_csv(manifest_path, index=False)

    mock_client = Mock()
    mock_client.stock_basic.return_value = pd.DataFrame(
        [
            {
                "ts_code": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "industry": "Liquor",
                "list_date": "20010827",
            },
            {
                "ts_code": "000001.SZ",
                "name": "Ping An Bank",
                "exchange": "SZSE",
                "industry": "Banking",
                "list_date": "19910403",
            },
        ]
    )

    config = ScreenRunConfig(
        markets=["cn", "us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_manifest_path=str(manifest_path),
    )

    with patch(
        "diverge.screener.universe.get_tushare_pro_client",
        return_value=mock_client,
    ):
        result = load_universe(config)

    assert list(result["symbol"]) == ["600519.SH", "000001.SZ", "AAPL", "MSFT"]
    assert list(result["market"]) == ["cn", "cn", "us", "us"]


def test_load_universe_uses_cn_manifest_when_configured(tmp_path):
    manifest_path = tmp_path / "cn_manifest.csv"
    pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "sector": "Liquor",
                "list_date": "20010827",
                "mktcap": "",
            }
        ]
    ).to_csv(manifest_path, index=False)

    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=20,
        cn_manifest_path=str(manifest_path),
    )

    with patch(
        "diverge.screener.universe.get_tushare_pro_client",
        side_effect=AssertionError(
            "CN manifest path should bypass live universe loading"
        ),
    ):
        result = load_universe(config)

    assert result.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "market": "cn",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
        }
    ]
