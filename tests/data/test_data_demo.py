from __future__ import annotations

from pathlib import Path

import pandas as pd

from tradingagents.data.data_demo import write_us_manifest


def test_write_us_manifest_maps_akshare_us_spot_to_manifest_csv(tmp_path):
    source_df = pd.DataFrame(
        [
            {
                "name": "NVIDIA Corp.",
                "cname": "英伟达公司",
                "category": "半导体",
                "symbol": "NVDA",
                "market": "NASDAQ",
            },
            {
                "name": "Apple, Inc.",
                "cname": "苹果公司",
                "category": "计算机",
                "symbol": "AAPL",
                "market": "NASDAQ",
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
            "symbol": "NVDA",
            "name": "NVIDIA Corp.",
            "exchange": "NASDAQ",
            "sector": "半导体",
            "list_date": "",
        }
    ]
    written_df = pd.read_csv(output_path, keep_default_na=False)
    assert written_df.to_dict("records") == manifest_df.to_dict("records")
