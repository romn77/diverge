from __future__ import annotations

from pathlib import Path

import akshare as ak
import pandas as pd


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().with_name("us_manifest.csv")
MANIFEST_COLUMNS = ["symbol", "name", "exchange", "sector", "list_date"]


def build_us_manifest(source_df: pd.DataFrame, limit: int | None = 500) -> pd.DataFrame:
    required_columns = {"symbol", "name", "market", "category"}
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
        }
    )
    manifest_df = manifest_df.loc[manifest_df["symbol"] != "", MANIFEST_COLUMNS]
    if limit is not None:
        manifest_df = (
            manifest_df.drop_duplicates(subset=["symbol"])
            .head(limit)
            .reset_index(drop=True)
        )
    else:
        manifest_df = manifest_df.drop_duplicates(subset=["symbol"]).reset_index(
            drop=True
        )
    return manifest_df


def write_us_manifest(
    source_df: pd.DataFrame | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    limit: int | None = 500,
) -> pd.DataFrame:
    if source_df is None:
        source_df = ak.stock_us_spot()

    manifest_df = build_us_manifest(source_df=source_df, limit=limit)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(output, index=False)
    return manifest_df


def main() -> None:
    manifest_df = write_us_manifest(limit=None)
    print(f"Wrote {len(manifest_df)} rows to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
