from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .schema import ScreenRunConfig
from .sync import (
    FINANCIAL_SNAPSHOT_FIELDS,
    FUNDAMENTAL_FIELDS,
    MARKET_SNAPSHOT_FIELDS,
)


MARKET_SNAPSHOT_SOURCE_PRIORITY = {
    "cn": ["tushare"],
    "us": ["simfin", "yfinance"],
}

FINANCIAL_SNAPSHOT_SOURCE_PRIORITY = {
    "cn": ["tushare"],
    "us": ["simfin", "yfinance"],
}

MARKET_COVERAGE_FIELDS = [
    "market_cap",
    "pe_ttm",
    "ps_ttm",
    "pb",
    "peg",
    "price",
    "volume",
    "turnover_value",
]

FINANCIAL_COVERAGE_FIELDS = list(FINANCIAL_SNAPSHOT_FIELDS)

FUNDAMENTAL_METADATA_COLUMNS = {
    "symbol",
    "market",
    "source",
    "as_of_date",
    "report_period",
    "updated_at",
    "missing_fields",
    "data_status",
    "market_snapshot_coverage",
    "financial_snapshot_coverage",
    "fundamental_coverage",
    "market_snapshot_freshness_status",
    "financial_snapshot_freshness_status",
    "market_snapshot_source",
    "financial_snapshot_source",
    "market_snapshot_as_of_date",
    "financial_report_period",
    "fundamental_source",
    "fundamental_as_of_date",
    "fundamental_report_period",
    "fundamental_updated_at",
    "fundamental_missing_fields",
    "fundamental_data_status",
}

RAW_SNAPSHOT_METADATA_COLUMNS = {
    "source",
    "as_of_date",
    "report_period",
    "updated_at",
    "missing_fields",
    "data_status",
}


def _configured_source(config: ScreenRunConfig, market: str) -> str:
    return (
        config.cn_fundamental_source if market == "cn" else config.us_fundamental_source
    )


def _source_priority(
    config: ScreenRunConfig,
    market: str,
    snapshot_type: str,
) -> list[str]:
    configured = _configured_source(config, market)
    priorities = (
        MARKET_SNAPSHOT_SOURCE_PRIORITY
        if snapshot_type == "market"
        else FINANCIAL_SNAPSHOT_SOURCE_PRIORITY
    )
    sources: list[str] = []
    for source in [*priorities.get(market, []), configured]:
        normalized = str(source).strip().lower()
        if normalized and normalized not in sources:
            sources.append(normalized)
    return sources


def _snapshot_path(
    config: ScreenRunConfig,
    market: str,
    source: str,
    snapshot_type: str,
) -> Path:
    filename = (
        "market_snapshots.csv"
        if snapshot_type == "market"
        else "financial_snapshots.csv"
    )
    return Path(config.fundamental_dir) / source / market / filename


def _legacy_snapshot_path(config: ScreenRunConfig, market: str, source: str) -> Path:
    return Path(config.fundamental_dir) / source / market / "snapshots.csv"


def _empty_snapshot_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "market", *FUNDAMENTAL_FIELDS])


def _parse_date(value: Any) -> datetime | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if hasattr(parsed, "to_pydatetime"):
        return parsed.to_pydatetime()
    return parsed


def _month_delta(later: datetime, earlier: datetime) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def _market_freshness(as_of_date: str, row: pd.Series) -> str:
    run_date = _parse_date(as_of_date)
    snapshot_date = _parse_date(row.get("as_of_date"))
    if run_date is None or snapshot_date is None:
        return "unknown"
    age_days = (run_date.date() - snapshot_date.date()).days
    if age_days <= 0:
        return "fresh"
    if age_days <= 3:
        return "stale"
    return "expired"


def _financial_freshness(as_of_date: str, row: pd.Series) -> str:
    run_date = _parse_date(as_of_date)
    report_period = _parse_date(row.get("report_period"))
    if run_date is None or report_period is None:
        return "unknown"
    age_months = _month_delta(run_date, report_period)
    if age_months <= 6:
        return "fresh"
    if age_months <= 18:
        return "stale"
    return "expired"


def _load_snapshot_file(
    path: Path,
    *,
    market: str,
    source: str,
    fields: list[str],
) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=["symbol", "market", *fields])
    frame = pd.read_csv(path)
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "market", *fields])
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["market"] = frame.get("market", market).astype(str).str.strip().str.lower()
    frame["source"] = frame.get("source", source).astype(str).str.strip().str.lower()
    for column in fields:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _latest_by_symbol(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    sort_columns = []
    for column in ("updated_at", "as_of_date", "report_period"):
        if column in working.columns:
            parsed_column = f"__parsed_{column}"
            working[parsed_column] = pd.to_datetime(working[column], errors="coerce")
            sort_columns.append(parsed_column)
    if sort_columns:
        working = working.sort_values(sort_columns)
    latest = working.groupby(["market", "symbol"], as_index=False).tail(1)
    return latest.drop(columns=sort_columns, errors="ignore").reset_index(drop=True)


def _load_source_snapshot(
    config: ScreenRunConfig,
    *,
    market: str,
    source: str,
    snapshot_type: str,
) -> pd.DataFrame:
    fields = (
        MARKET_SNAPSHOT_FIELDS
        if snapshot_type == "market"
        else FINANCIAL_SNAPSHOT_FIELDS
    )
    frame = _load_snapshot_file(
        _snapshot_path(config, market, source, snapshot_type),
        market=market,
        source=source,
        fields=fields,
    )
    return _latest_by_symbol(frame)


def _load_legacy_snapshot(
    config: ScreenRunConfig,
    *,
    market: str,
    source: str,
) -> pd.DataFrame:
    frame = _load_snapshot_file(
        _legacy_snapshot_path(config, market, source),
        market=market,
        source=source,
        fields=FUNDAMENTAL_FIELDS,
    )
    return _latest_by_symbol(frame)


def _coverage(row: pd.Series, fields: list[str]) -> float:
    if not fields:
        return 0.0
    present = sum(1 for field in fields if pd.notna(row.get(field)))
    return present / len(fields)


def _data_status(coverage: float) -> str:
    if coverage >= 1.0:
        return "complete"
    if coverage > 0:
        return "partial"
    return "missing"


def _field_sources(row: pd.Series, fields: list[str]) -> list[str]:
    sources: list[str] = []
    for field in fields:
        source = row.get(f"{field}_source")
        if pd.notna(source) and str(source) not in sources:
            sources.append(str(source))
    return sources


def _merge_snapshot_type(
    frames_by_source: dict[str, pd.DataFrame],
    *,
    market: str,
    as_of_date: str,
    snapshot_type: str,
    fields: list[str],
) -> pd.DataFrame:
    usable_sources = [
        source for source, frame in frames_by_source.items() if not frame.empty
    ]
    if not usable_sources:
        return pd.DataFrame(columns=["symbol", "market", *fields])

    keys = (
        pd.concat(
            [
                frames_by_source[source].loc[:, ["market", "symbol"]]
                for source in usable_sources
            ],
            ignore_index=True,
            sort=False,
        )
        .drop_duplicates()
        .reset_index(drop=True)
    )
    rows: list[dict[str, Any]] = []
    freshness_column = f"{snapshot_type}_snapshot_freshness_status"
    date_column = (
        "market_snapshot_as_of_date"
        if snapshot_type == "market"
        else "financial_report_period"
    )
    source_column = f"{snapshot_type}_snapshot_source"
    freshness_fn = (
        _market_freshness if snapshot_type == "market" else _financial_freshness
    )

    indexed = {
        source: frame.set_index(["market", "symbol"], drop=False)
        for source, frame in frames_by_source.items()
        if not frame.empty
    }
    for key in keys.itertuples(index=False):
        row_payload: dict[str, Any] = {
            "symbol": str(key.symbol),
            "market": market,
        }
        field_sources: list[str] = []
        selected_statuses: list[str] = []
        selected_dates: list[str] = []
        for field in fields:
            for source in frames_by_source:
                frame = indexed.get(source)
                if frame is None:
                    continue
                try:
                    source_row = frame.loc[(key.market, key.symbol)]
                except KeyError:
                    continue
                if isinstance(source_row, pd.DataFrame):
                    source_row = source_row.iloc[-1]
                freshness = freshness_fn(as_of_date, source_row)
                if freshness == "expired":
                    continue
                value = source_row.get(field)
                if pd.isna(value):
                    continue
                row_payload[field] = value
                row_payload[f"{field}_source"] = source
                if source not in field_sources:
                    field_sources.append(source)
                selected_statuses.append(freshness)
                date_value = (
                    source_row.get("as_of_date")
                    if snapshot_type == "market"
                    else source_row.get("report_period")
                )
                if pd.notna(date_value) and str(date_value) not in selected_dates:
                    selected_dates.append(str(date_value)[:10])
                break
        row_payload[source_column] = ",".join(field_sources)
        row_payload[date_column] = ",".join(selected_dates)
        if "fresh" in selected_statuses:
            row_payload[freshness_column] = "fresh"
        elif "stale" in selected_statuses:
            row_payload[freshness_column] = "stale"
        elif "unknown" in selected_statuses:
            row_payload[freshness_column] = "unknown"
        else:
            row_payload[freshness_column] = "missing"
        rows.append(row_payload)
    return pd.DataFrame(rows)


def _load_split_market_snapshot(config: ScreenRunConfig, market: str) -> pd.DataFrame:
    frames_by_source = {
        source: _load_source_snapshot(
            config, market=market, source=source, snapshot_type="market"
        )
        for source in _source_priority(config, market, "market")
    }
    return _merge_snapshot_type(
        frames_by_source,
        market=market,
        as_of_date=config.as_of_date,
        snapshot_type="market",
        fields=MARKET_SNAPSHOT_FIELDS,
    )


def _load_split_financial_snapshot(
    config: ScreenRunConfig, market: str
) -> pd.DataFrame:
    frames_by_source = {
        source: _load_source_snapshot(
            config, market=market, source=source, snapshot_type="financial"
        )
        for source in _source_priority(config, market, "financial")
    }
    return _merge_snapshot_type(
        frames_by_source,
        market=market,
        as_of_date=config.as_of_date,
        snapshot_type="financial",
        fields=FINANCIAL_SNAPSHOT_FIELDS,
    )


def _combine_market_financial(
    market_frame: pd.DataFrame,
    financial_frame: pd.DataFrame,
) -> pd.DataFrame:
    if market_frame.empty and financial_frame.empty:
        return _empty_snapshot_frame()
    if market_frame.empty:
        combined = financial_frame.copy()
    elif financial_frame.empty:
        combined = market_frame.copy()
    else:
        combined = market_frame.merge(
            financial_frame,
            on=["symbol", "market"],
            how="outer",
            suffixes=("", "_financial"),
        )
    for field in FUNDAMENTAL_FIELDS:
        if field not in combined.columns:
            combined[field] = pd.NA
    combined["market_snapshot_coverage"] = combined.apply(
        lambda row: _coverage(row, MARKET_COVERAGE_FIELDS), axis=1
    )
    combined["financial_snapshot_coverage"] = combined.apply(
        lambda row: _coverage(row, FINANCIAL_COVERAGE_FIELDS), axis=1
    )
    combined["fundamental_coverage"] = combined.apply(
        lambda row: _coverage(
            row, [*MARKET_COVERAGE_FIELDS, *FINANCIAL_COVERAGE_FIELDS]
        ),
        axis=1,
    )
    combined["fundamental_data_status"] = combined["fundamental_coverage"].map(
        _data_status
    )
    combined["fundamental_source"] = combined.apply(
        lambda row: ",".join(_field_sources(row, FUNDAMENTAL_FIELDS)),
        axis=1,
    )
    combined["fundamental_as_of_date"] = combined.get("market_snapshot_as_of_date", "")
    combined["fundamental_report_period"] = combined.get("financial_report_period", "")
    combined["fundamental_updated_at"] = ""
    combined["fundamental_missing_fields"] = combined.apply(
        lambda row: ",".join(
            field for field in FUNDAMENTAL_FIELDS if pd.isna(row.get(field))
        ),
        axis=1,
    )
    return combined


def _load_legacy_market_snapshot(config: ScreenRunConfig, market: str) -> pd.DataFrame:
    frames = [
        _load_legacy_snapshot(config, market=market, source=source)
        for source in _source_priority(config, market, "financial")
    ]
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        return _empty_snapshot_frame()
    combined = pd.concat(usable, ignore_index=True, sort=False)
    combined = _latest_by_symbol(combined)
    for field in FUNDAMENTAL_FIELDS:
        if field not in combined.columns:
            combined[field] = pd.NA
    combined["fundamental_source"] = combined.get("source", "")
    combined["fundamental_as_of_date"] = combined.get("as_of_date", "")
    combined["fundamental_report_period"] = combined.get("report_period", "")
    combined["fundamental_updated_at"] = combined.get("updated_at", "")
    combined["fundamental_missing_fields"] = combined.get("missing_fields", "")
    combined["fundamental_data_status"] = combined.get("data_status", "partial")
    combined["market_snapshot_coverage"] = combined.apply(
        lambda row: _coverage(row, MARKET_COVERAGE_FIELDS), axis=1
    )
    combined["financial_snapshot_coverage"] = combined.apply(
        lambda row: _coverage(row, FINANCIAL_COVERAGE_FIELDS), axis=1
    )
    combined["fundamental_coverage"] = combined.apply(
        lambda row: _coverage(
            row, [*MARKET_COVERAGE_FIELDS, *FINANCIAL_COVERAGE_FIELDS]
        ),
        axis=1,
    )
    return combined


def load_fundamental_snapshots(config: ScreenRunConfig) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for market in config.markets:
        market_frame = _load_split_market_snapshot(config, market)
        financial_frame = _load_split_financial_snapshot(config, market)
        if market_frame.empty and financial_frame.empty:
            frames.append(_load_legacy_market_snapshot(config, market))
        else:
            frames.append(_combine_market_financial(market_frame, financial_frame))
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        return _empty_snapshot_frame()
    combined = pd.concat(usable, ignore_index=True, sort=False)
    return combined.groupby(["market", "symbol"], as_index=False).tail(1)


def enrich_features_with_fundamentals(
    features_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> pd.DataFrame:
    if features_df.empty:
        return features_df

    fundamentals = load_fundamental_snapshots(config)
    if fundamentals.empty:
        result = features_df.copy()
        for column in FUNDAMENTAL_FIELDS:
            if column not in result.columns:
                result[column] = pd.NA
        result["fundamental_data_status"] = "missing_snapshot"
        result["market_snapshot_coverage"] = 0.0
        result["financial_snapshot_coverage"] = 0.0
        result["fundamental_coverage"] = 0.0
        return result

    fundamental_columns = [
        column
        for column in fundamentals.columns
        if column not in RAW_SNAPSHOT_METADATA_COLUMNS
        and (
            column in FUNDAMENTAL_FIELDS
            or column in FUNDAMENTAL_METADATA_COLUMNS
            or column.endswith("_source")
        )
    ]
    right = fundamentals.loc[:, fundamental_columns]
    result = features_df.merge(right, on=["symbol", "market"], how="left")
    for column in FUNDAMENTAL_FIELDS:
        if column not in result.columns:
            result[column] = pd.NA
    for column in (
        "market_snapshot_coverage",
        "financial_snapshot_coverage",
        "fundamental_coverage",
    ):
        if column not in result.columns:
            result[column] = 0.0
        result[column] = result[column].fillna(0.0)
    result["fundamental_data_status"] = result["fundamental_data_status"].fillna(
        "missing"
    )
    return result
