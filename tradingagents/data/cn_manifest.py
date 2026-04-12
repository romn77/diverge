from __future__ import annotations

import argparse
from collections.abc import Collection
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd

from tradingagents.data.manifest_schema import COMMON_MANIFEST_COLUMNS, COMPARE_MANIFEST_COLUMNS
from tradingagents.screener.universe import load_cn_universe


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(PROJECT_ENV_FILE)

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().with_name("cn_manifest.csv")
DEFAULT_ALLOWED_EXCHANGES = ("SSE", "SZSE")
DEFAULT_DATA_SOURCE = "tushare"
DEFAULT_FALLBACK_DATA_SOURCES: tuple[str, ...] = ()
def build_cn_manifest(
    source_df: pd.DataFrame,
    allowed_exchanges: Collection[str] | None = DEFAULT_ALLOWED_EXCHANGES,
) -> pd.DataFrame:
    missing_columns = [column for column in COMMON_MANIFEST_COLUMNS if column not in source_df.columns]
    if missing_columns:
        raise ValueError(f"source_df is missing required columns: {', '.join(sorted(missing_columns))}")

    manifest_df = pd.DataFrame(
        {
            "symbol": source_df["symbol"].fillna("").astype(str).str.strip(),
            "name": source_df["name"].fillna("").astype(str).str.strip(),
            "exchange": source_df["exchange"].fillna("").astype(str).str.strip(),
            "sector": source_df["sector"].fillna("").astype(str).str.strip(),
            "list_date": source_df["list_date"].fillna("").astype(str).str.strip(),
            "mktcap": "",
        }
    )
    manifest_df = manifest_df.loc[manifest_df["symbol"] != ""]

    if allowed_exchanges is not None:
        normalized_allowed_exchanges = {
            str(exchange).strip().upper() for exchange in allowed_exchanges if str(exchange).strip()
        }
        manifest_df = manifest_df.loc[
            manifest_df["exchange"].str.upper().isin(normalized_allowed_exchanges)
        ]

    blank_list_date_mask = manifest_df["list_date"] == ""
    if blank_list_date_mask.any():
        raise ValueError(
            "CN manifest requires non-empty list_date values; use tushare stock metadata"
        )

    manifest_df = (
        manifest_df.sort_values(["symbol", "exchange"], ascending=[True, True])
        .drop_duplicates(subset=["symbol"], keep="first")
        .reset_index(drop=True)
    )
    return manifest_df.loc[:, COMPARE_MANIFEST_COLUMNS]


def write_cn_manifest(
    source_df: pd.DataFrame | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    data_source: str = DEFAULT_DATA_SOURCE,
    cache_dir: str | Path | None = None,
    fallback_data_sources: Collection[str] | None = DEFAULT_FALLBACK_DATA_SOURCES,
    allowed_exchanges: Collection[str] | None = DEFAULT_ALLOWED_EXCHANGES,
) -> pd.DataFrame:
    if source_df is None:
        source_df = load_cn_universe(
            data_source=data_source,
            cache_dir=cache_dir,
            fallback_data_sources=list(fallback_data_sources) if fallback_data_sources is not None else None,
        )

    manifest_df = build_cn_manifest(
        source_df=source_df,
        allowed_exchanges=allowed_exchanges,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(output, index=False)
    return manifest_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the CN screener universe to a CSV manifest.")
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Destination CSV path. Defaults to tradingagents/data/cn_manifest.csv.",
    )
    parser.add_argument(
        "--data-source",
        default=DEFAULT_DATA_SOURCE,
        choices=("akshare", "tushare"),
        help="Primary CN universe data source. Defaults to tushare.",
    )
    parser.add_argument(
        "--fallback-data-sources",
        default=",".join(DEFAULT_FALLBACK_DATA_SOURCES),
        help="Comma-separated CN source fallbacks, in order. Defaults to none.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional cache directory passed to the CN universe loader.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    fallback_data_sources = [
        source.strip()
        for source in str(args.fallback_data_sources or "").split(",")
        if source.strip()
    ]
    manifest_df = write_cn_manifest(
        output_path=args.output_path,
        data_source=args.data_source,
        cache_dir=args.cache_dir,
        fallback_data_sources=fallback_data_sources,
    )
    print(f"Wrote {len(manifest_df)} rows to {Path(args.output_path)}")


if __name__ == "__main__":
    main()
