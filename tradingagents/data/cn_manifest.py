from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

import pandas as pd

from tradingagents.data.manifest_schema import COMMON_MANIFEST_COLUMNS, COMPARE_MANIFEST_COLUMNS
from tradingagents.screener.universe import load_cn_universe


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().with_name("cn_manifest.csv")
DEFAULT_ALLOWED_EXCHANGES = ("SSE", "SZSE")


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

    manifest_df = (
        manifest_df.sort_values(["symbol", "exchange"], ascending=[True, True])
        .drop_duplicates(subset=["symbol"], keep="first")
        .reset_index(drop=True)
    )
    return manifest_df.loc[:, COMPARE_MANIFEST_COLUMNS]


def write_cn_manifest(
    source_df: pd.DataFrame | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    data_source: str = "tushare",
    cache_dir: str | Path | None = None,
    fallback_data_sources: list[str] | None = None,
    allowed_exchanges: Collection[str] | None = DEFAULT_ALLOWED_EXCHANGES,
) -> pd.DataFrame:
    if source_df is None:
        source_df = load_cn_universe(
            data_source=data_source,
            cache_dir=cache_dir,
            fallback_data_sources=fallback_data_sources,
        )

    manifest_df = build_cn_manifest(
        source_df=source_df,
        allowed_exchanges=allowed_exchanges,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(output, index=False)
    return manifest_df


def main() -> None:
    manifest_df = write_cn_manifest()
    print(f"Wrote {len(manifest_df)} rows to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
