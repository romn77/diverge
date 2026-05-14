from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd

from diverge.data_layout import default_manifest_path
from diverge.data.manifest_schema import COMPARE_MANIFEST_COLUMNS
from diverge.dataflows.akshare_rate_limit import call_akshare_api
from diverge.screener.universe_rules import (
    US_UNIVERSE_CAP_DEFAULT,
    filter_us_common_stock_rows,
    sort_rows_by_mktcap,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(PROJECT_ENV_FILE)

MANIFEST_COLUMNS = COMPARE_MANIFEST_COLUMNS
DEFAULT_LIMIT = US_UNIVERSE_CAP_DEFAULT


def _import_akshare():
    import akshare as ak

    return ak


def build_us_manifest(
    source_df: pd.DataFrame, limit: int | None = DEFAULT_LIMIT
) -> pd.DataFrame:
    required_columns = {"symbol", "name", "market", "category", "mktcap"}
    missing_columns = required_columns.difference(source_df.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        raise ValueError(f"source_df is missing required columns: {missing_list}")

    manifest_df = pd.DataFrame(
        {
            "symbol": source_df["symbol"].fillna("").astype(str).str.strip(),
            "name": source_df["name"].fillna("").astype(str).str.strip(),
            "exchange": source_df["market"].fillna("").astype(str).str.strip(),
            "sector": source_df["category"].fillna("").astype(str).str.strip(),
            "list_date": "",
            "mktcap": pd.to_numeric(source_df["mktcap"], errors="coerce").fillna(0.0),
        }
    )
    manifest_df = manifest_df.loc[
        manifest_df["symbol"] != "", MANIFEST_COLUMNS
    ].reset_index(drop=True)
    manifest_df, _ = filter_us_common_stock_rows(manifest_df.assign(market="us"))
    manifest_df = (
        sort_rows_by_mktcap(
            manifest_df.drop(columns=["market"], errors="ignore").loc[
                :, MANIFEST_COLUMNS
            ]
        )
        .drop_duplicates(subset=["symbol"], keep="first")
        .reset_index(drop=True)
    )
    if limit is not None:
        manifest_df = manifest_df.head(limit).reset_index(drop=True)
    else:
        manifest_df = manifest_df.reset_index(drop=True)
    return manifest_df


def write_us_manifest(
    source_df: pd.DataFrame | None = None,
    output_path: str | Path | None = None,
    limit: int | None = DEFAULT_LIMIT,
) -> pd.DataFrame:
    if source_df is None:
        ak = _import_akshare()
        source_df = call_akshare_api(ak.stock_us_spot)

    manifest_df = build_us_manifest(source_df=source_df, limit=limit)
    output = (
        Path(output_path)
        if output_path is not None
        else default_manifest_path("us", PROJECT_ROOT)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(output, index=False)
    return manifest_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the US screener universe to a CSV manifest."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Destination directory. Defaults to DATA_DIR/manifest and writes us.csv.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum rows to write. Defaults to {DEFAULT_LIMIT}.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_path = (
        Path(args.output_dir) / "us.csv"
        if args.output_dir
        else default_manifest_path("us", PROJECT_ROOT)
    )
    manifest_df = write_us_manifest(output_path=output_path, limit=args.limit)
    print(f"Wrote {len(manifest_df)} rows to {output_path}")


if __name__ == "__main__":
    main()
