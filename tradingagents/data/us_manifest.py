from __future__ import annotations

from pathlib import Path

import akshare as ak
import pandas as pd

from tradingagents.data.manifest_schema import COMPARE_MANIFEST_COLUMNS


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().with_name("us_manifest_short.csv")
MANIFEST_COLUMNS = COMPARE_MANIFEST_COLUMNS


def build_us_manifest(source_df: pd.DataFrame, limit: int | None = 5500) -> pd.DataFrame:
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
    manifest_df = manifest_df.loc[manifest_df["symbol"] != "", MANIFEST_COLUMNS]
    manifest_df = (
        manifest_df.sort_values(["mktcap", "symbol"], ascending=[False, True])
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
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    limit: int | None = 4000,
) -> pd.DataFrame:
    if source_df is None:
        source_df = ak.stock_us_spot()

    manifest_df = build_us_manifest(source_df=source_df, limit=limit)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(output, index=False)
    return manifest_df


def main() -> None:
    manifest_df = write_us_manifest()
    print(f"Wrote {len(manifest_df)} rows to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
