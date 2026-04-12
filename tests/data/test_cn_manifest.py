from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents.data.cn_manifest import (
    DEFAULT_FALLBACK_DATA_SOURCES,
    build_cn_manifest,
    main,
    write_cn_manifest,
)


def test_build_cn_manifest_normalizes_shared_schema_and_excludes_bse(tmp_path):
    source_df = pd.DataFrame(
        [
            {
                "symbol": " 600519.SH ",
                "name": " Kweichow Moutai ",
                "exchange": " SSE ",
                "sector": " Liquor ",
                "list_date": " 20010827 ",
            },
            {
                "symbol": "430047.BJ",
                "name": "Example BSE",
                "exchange": "BSE",
                "sector": "Industry",
                "list_date": "20100101",
            },
            {
                "symbol": "",
                "name": "Missing Symbol",
                "exchange": "SZSE",
                "sector": "Finance",
                "list_date": "20110101",
            },
        ]
    )
    output_path = tmp_path / "cn_manifest.csv"

    manifest_df = write_cn_manifest(source_df=source_df, output_path=output_path)

    assert output_path.is_file()
    assert manifest_df.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
            "mktcap": "",
        }
    ]
    written_df = pd.read_csv(output_path, dtype=str, keep_default_na=False)
    assert written_df.to_dict("records") == [
        {
            "symbol": "600519.SH",
            "name": "Kweichow Moutai",
            "exchange": "SSE",
            "sector": "Liquor",
            "list_date": "20010827",
            "mktcap": "",
        }
    ]


def test_build_cn_manifest_requires_shared_columns():
    source_df = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "sector": "Liquor",
            }
        ]
    )

    with pytest.raises(ValueError, match="list_date"):
        build_cn_manifest(source_df=source_df)


def test_build_cn_manifest_rejects_blank_list_date_values():
    source_df = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "name": "Kweichow Moutai",
                "exchange": "SSE",
                "sector": "Liquor",
                "list_date": "",
            }
        ]
    )

    with pytest.raises(ValueError, match="non-empty list_date"):
        build_cn_manifest(source_df=source_df)


def test_write_cn_manifest_loads_cn_universe_with_defaults(tmp_path):
    source_df = pd.DataFrame(
        [
            {
                "symbol": "000001.SZ",
                "market": "cn",
                "name": "Ping An Bank",
                "exchange": "SZSE",
                "sector": "Banking",
                "list_date": "19910403",
            }
        ]
    )

    with patch(
        "tradingagents.data.cn_manifest.load_cn_universe",
        return_value=source_df,
    ) as mock_load:
        manifest_df = write_cn_manifest(output_path=tmp_path / "cn_manifest.csv")

    mock_load.assert_called_once_with(
        data_source="tushare",
        cache_dir=None,
        fallback_data_sources=list(DEFAULT_FALLBACK_DATA_SOURCES),
    )
    assert manifest_df.to_dict("records") == [
        {
            "symbol": "000001.SZ",
            "name": "Ping An Bank",
            "exchange": "SZSE",
            "sector": "Banking",
            "list_date": "19910403",
            "mktcap": "",
        }
    ]


def test_main_uses_cli_defaults_and_writes_requested_path(tmp_path, capsys):
    source_df = pd.DataFrame(
        [
            {
                "symbol": "000001.SZ",
                "market": "cn",
                "name": "Ping An Bank",
                "exchange": "SZSE",
                "sector": "Banking",
                "list_date": "19910403",
            }
        ]
    )
    output_path = tmp_path / "cli_cn_manifest.csv"

    with (
        patch(
            "tradingagents.data.cn_manifest.load_cn_universe",
            return_value=source_df,
        ) as mock_load,
        patch(
            "sys.argv",
            [
                "python",
                "--output-path",
                str(output_path),
            ],
        ),
    ):
        main()

    mock_load.assert_called_once_with(
        data_source="tushare",
        cache_dir=None,
        fallback_data_sources=list(DEFAULT_FALLBACK_DATA_SOURCES),
    )
    assert output_path.is_file()
    assert f"Wrote 1 rows to {output_path}" in capsys.readouterr().out
