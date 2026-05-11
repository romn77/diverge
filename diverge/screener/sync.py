from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from diverge.common.dates import offset_iso_date
from diverge.common.json_io import write_json_atomic
from diverge.data_layout import (
    resolve_fundamentals_dir,
    resolve_history_dir,
    resolve_screener_cache_dir,
)
from diverge.dataflows.vendors.tushare.common import get_tushare_pro_client
from diverge.dataflows.vendors.fmp.screener import (
    fetch_key_metrics_ttm_bulk,
    fetch_profile_bulk,
    fetch_ratios_ttm_bulk,
)
from diverge.dataflows.vendors.tencent.quote import fetch_us_quote_rows
from diverge.market_data.history_cache import (
    classify_history_cache_coverage,
    load_history_cache,
)
from diverge.market_data.price_history import LOOKBACK_DAYS
from diverge.screener.market_data import fetch_history_for_universe
from diverge.screener.schema import ScreenRunConfig
from diverge.screener.stages import prepare_universe_stage


MARKET_SNAPSHOT_FIELDS = [
    "market_cap",
    "free_float_market_cap",
    "pe_ttm",
    "ps_ttm",
    "pb",
    "peg",
    "price",
    "prev_close",
    "open",
    "high",
    "low",
    "volume",
    "turnover_value",
    "change_pct",
    "avg_volume_20d",
    "avg_turnover_value_20d",
    "turnover_rate",
    "free_float_turnover_rate",
    "volume_ratio",
]

FINANCIAL_SNAPSHOT_FIELDS = [
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "revenue_growth_yoy",
    "net_income_growth_yoy",
    "debt_to_assets",
    "current_ratio",
    "free_cashflow",
    "operating_cashflow_quality",
]

FUNDAMENTAL_FIELDS = [
    *MARKET_SNAPSHOT_FIELDS,
    *FINANCIAL_SNAPSHOT_FIELDS,
]

SNAPSHOT_TYPE_FIELDS = {
    "market": MARKET_SNAPSHOT_FIELDS,
    "financial": FINANCIAL_SNAPSHOT_FIELDS,
    "legacy": FUNDAMENTAL_FIELDS,
}

SNAPSHOT_SCHEMA_VERSION = "fundamental_snapshot.v1"

FIELD_UNITS = {
    "market_cap": "native_currency",
    "free_float_market_cap": "native_currency",
    "price": "native_currency",
    "prev_close": "native_currency",
    "open": "native_currency",
    "high": "native_currency",
    "low": "native_currency",
    "turnover_value": "native_currency",
    "avg_turnover_value_20d": "native_currency",
    "free_cashflow": "native_currency",
    "pe_ttm": "multiple",
    "ps_ttm": "multiple",
    "pb": "multiple",
    "peg": "multiple",
    "volume": "shares",
    "avg_volume_20d": "shares",
    "change_pct": "decimal",
    "turnover_rate": "decimal",
    "free_float_turnover_rate": "decimal",
    "volume_ratio": "ratio",
    "roe": "decimal",
    "roa": "decimal",
    "gross_margin": "decimal",
    "net_margin": "decimal",
    "revenue_growth_yoy": "decimal",
    "net_income_growth_yoy": "decimal",
    "debt_to_assets": "decimal",
    "current_ratio": "ratio",
    "operating_cashflow_quality": "ratio",
}

SIMFIN_FIELD_MAP = {
    "Market-Cap": "market_cap",
    "P/E": "pe_ttm",
    "P/Sales": "ps_ttm",
    "P/Book": "pb",
    "PEG": "peg",
    "Return on Equity": "roe",
    "Return on Assets": "roa",
    "Gross Profit Margin": "gross_margin",
    "Net Profit Margin": "net_margin",
    "Sales Growth": "revenue_growth_yoy",
    "Earnings Growth": "net_income_growth_yoy",
    "Debt Ratio": "debt_to_assets",
    "Current Ratio": "current_ratio",
    "Free Cash Flow": "free_cashflow",
    "Operating Cash Flow / Net Income": "operating_cashflow_quality",
}

FMP_RATIO_FIELD_MAP = {
    "peRatioTTM": "pe_ttm",
    "priceEarningsRatioTTM": "pe_ttm",
    "priceToSalesRatioTTM": "ps_ttm",
    "priceToBookRatioTTM": "pb",
    "priceEarningsToGrowthRatioTTM": "peg",
    "pegRatioTTM": "peg",
    "returnOnEquityTTM": "roe",
    "returnOnAssetsTTM": "roa",
    "grossProfitMarginTTM": "gross_margin",
    "netProfitMarginTTM": "net_margin",
    "debtRatioTTM": "debt_to_assets",
    "currentRatioTTM": "current_ratio",
}

FMP_KEY_METRICS_FIELD_MAP = {
    "marketCapTTM": "market_cap",
    "enterpriseValueTTM": "enterprise_value",
    "peRatioTTM": "pe_ttm",
    "priceToSalesRatioTTM": "ps_ttm",
    "pbRatioTTM": "pb",
    "ptbRatioTTM": "pb",
    "freeCashFlowPerShareTTM": "free_cashflow_per_share",
    "operatingCashFlowPerShareTTM": "operating_cashflow_per_share",
}

FMP_PROFILE_FIELD_MAP = {
    "price": "price",
    "marketCap": "market_cap",
    "volAvg": "avg_volume_20d",
    "companyName": "name",
    "exchangeShortName": "exchange",
    "sector": "sector",
    "industry": "industry",
}

TUSHARE_FIELD_MAP = {
    "roe": "roe",
    "roa": "roa",
    "grossprofit_margin": "gross_margin",
    "netprofit_margin": "net_margin",
    "current_ratio": "current_ratio",
    "debt_to_assets": "debt_to_assets",
    "ocfps": "operating_cashflow_quality",
}

TUSHARE_PERCENT_FIELD_MAP = {
    "roe",
    "roa",
    "grossprofit_margin",
    "netprofit_margin",
    "debt_to_assets",
}

TUSHARE_DAILY_BASIC_FIELD_MAP = {
    "pe_ttm": "pe_ttm",
    "ps_ttm": "ps_ttm",
    "pb": "pb",
    "total_mv": "market_cap",
    "circ_mv": "free_float_market_cap",
    "turnover_rate": "turnover_rate",
    "turnover_rate_f": "free_float_turnover_rate",
    "volume_ratio": "volume_ratio",
}

TUSHARE_DAILY_BASIC_PERCENT_FIELDS = {
    "turnover_rate",
    "turnover_rate_f",
}

OHLCV_SYNC_RETRY_ROUNDS = 3
OHLCV_READY_STATUS = "ready"


@dataclass(slots=True)
class SyncResult:
    sync_type: str
    markets: list[str]
    source: str
    status: str
    symbols_total: int = 0
    symbols_success: int = 0
    symbols_failed: int = 0
    rows_written: int = 0
    snapshot_path: str | None = None
    meta_path: str | None = None
    snapshot_paths: dict[str, str] = field(default_factory=dict)
    meta_paths: dict[str, str] = field(default_factory=dict)
    field_coverage: float | None = None
    missing_fields: list[str] = field(default_factory=list)
    failed_symbols: list[dict[str, str]] = field(default_factory=list)
    quality_artifact_path: str | None = None
    quality_reason_counts: dict[str, int] = field(default_factory=dict)
    symbols_missing_as_of_bar: int = 0
    symbols_pruned_from_screener: int = 0
    missing_as_of_bar_symbols: list[dict[str, str]] = field(default_factory=list)
    updated_at: str = ""


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ohlcv_history_start(as_of_date: str) -> str:
    return offset_iso_date(as_of_date, -LOOKBACK_DAYS)


def _quality_artifact_path(cache_root: Path, config: ScreenRunConfig) -> Path:
    market_slug = "-".join(config.markets)
    source_slug = f"cn-{config.cn_data_source}_us-{config.us_data_source}"
    safe_slug = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in f"{config.as_of_date}_{market_slug}_{source_slug}"
    )
    return cache_root / "sync" / f"ohlcv_quality_{safe_slug}.json"


def _quality_row_for_symbol(
    *,
    history_root: Path,
    market: str,
    symbol: str,
    start_date: str,
    as_of_date: str,
) -> dict[str, str | None]:
    coverage = classify_history_cache_coverage(
        load_history_cache(history_root, market, symbol),
        start_date=start_date,
        as_of_date=as_of_date,
    )
    return {
        "symbol": symbol,
        "market": market,
        "status": coverage["status"],
        "cache_span": coverage["cache_span"],
        "cache_start": coverage["cache_start"],
        "cache_end": coverage["cache_end"],
        "as_of_date": as_of_date,
    }


def _build_ohlcv_quality_rows(
    universe_df: pd.DataFrame,
    *,
    history_root: Path,
    start_date: str,
    as_of_date: str,
) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    if universe_df.empty:
        return rows
    for row in universe_df.loc[:, ["market", "symbol"]].itertuples(index=False):
        rows.append(
            _quality_row_for_symbol(
                history_root=history_root,
                market=str(row.market).strip().lower(),
                symbol=str(row.symbol).strip(),
                start_date=start_date,
                as_of_date=as_of_date,
            )
        )
    return rows


def _retry_universe_from_quality_rows(
    universe_df: pd.DataFrame,
    quality_rows: list[dict[str, str | None]],
) -> pd.DataFrame:
    retry_keys = {
        (str(row["market"]), str(row["symbol"]))
        for row in quality_rows
        if row.get("status") != OHLCV_READY_STATUS
    }
    if not retry_keys or universe_df.empty:
        return universe_df.iloc[0:0].copy()
    mask = [
        (str(row.market).strip().lower(), str(row.symbol).strip()) in retry_keys
        for row in universe_df.loc[:, ["market", "symbol"]].itertuples(index=False)
    ]
    return universe_df.loc[mask].reset_index(drop=True)


def _quality_reason_counts(quality_rows: list[dict[str, str | None]]) -> dict[str, int]:
    return dict(Counter(str(row.get("status") or "unknown") for row in quality_rows))


def _failed_symbols_from_quality_rows(
    quality_rows: list[dict[str, str | None]],
) -> list[dict[str, str]]:
    return [
        {
            "symbol": str(row["symbol"]),
            "market": str(row["market"]),
            "drop_reason": str(row.get("status") or "unknown"),
        }
        for row in quality_rows
        if row.get("status") != OHLCV_READY_STATUS
    ]


def _missing_as_of_bar_symbols(
    quality_rows: list[dict[str, str | None]],
    *,
    limit: int = 20,
) -> list[dict[str, str]]:
    rows = []
    for row in quality_rows:
        if row.get("status") != "missing_as_of_bar":
            continue
        rows.append(
            {
                "symbol": str(row["symbol"]),
                "market": str(row["market"]),
                "cache_span": str(row.get("cache_span") or ""),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _ready_symbol_set(quality_rows: list[dict[str, str | None]]) -> set[str]:
    return {
        str(row["symbol"])
        for row in quality_rows
        if row.get("status") == OHLCV_READY_STATUS
    }


def _write_ohlcv_quality_artifact(
    path: Path,
    *,
    config: ScreenRunConfig,
    quality_rows: list[dict[str, str | None]],
) -> None:
    write_json_atomic(
        path,
        {
            "sync_type": "ohlcv",
            "markets": list(config.markets),
            "as_of_date": config.as_of_date,
            "source": {
                "cn": config.cn_data_source,
                "us": config.us_data_source,
            },
            "reason_counts": _quality_reason_counts(quality_rows),
            "symbols_total": len(quality_rows),
            "symbols_ready": sum(
                1 for row in quality_rows if row.get("status") == OHLCV_READY_STATUS
            ),
            "symbols_not_ready": sum(
                1 for row in quality_rows if row.get("status") != OHLCV_READY_STATUS
            ),
            "rows": quality_rows,
            "updated_at": _utc_iso(),
        },
    )


def _safe_numeric(value: Any) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return float(parsed)


def _safe_decimal_percent(value: Any) -> float | None:
    parsed = _safe_numeric(value)
    if parsed is None:
        return None
    return parsed / 100


def _finalize_fundamental_row(
    payload: dict[str, Any],
    *,
    fields: list[str] | None = None,
) -> None:
    field_names = fields or FUNDAMENTAL_FIELDS
    missing = [
        field_name for field_name in field_names if payload.get(field_name) is None
    ]
    payload["missing_fields"] = ",".join(missing)
    payload["data_status"] = "partial" if missing else "fresh"


def _snapshot_paths(
    *,
    base_dir: str | Path | None,
    market: str,
    source: str,
    snapshot_type: str = "legacy",
) -> tuple[Path, Path]:
    root = Path(base_dir) if base_dir is not None else resolve_fundamentals_dir()
    snapshot_dir = root / source / market
    if snapshot_type == "market":
        return (
            snapshot_dir / "market_snapshots.csv",
            snapshot_dir / "market_snapshots_meta.json",
        )
    if snapshot_type == "financial":
        return (
            snapshot_dir / "financial_snapshots.csv",
            snapshot_dir / "financial_snapshots_meta.json",
        )
    return snapshot_dir / "snapshots.csv", snapshot_dir / "sync_meta.json"


def _save_fundamental_snapshot(
    frame: pd.DataFrame,
    *,
    base_dir: str | Path | None,
    market: str,
    source: str,
    sync_result: SyncResult,
    snapshot_type: str = "legacy",
) -> SyncResult:
    field_names = SNAPSHOT_TYPE_FIELDS.get(snapshot_type, FUNDAMENTAL_FIELDS)
    snapshot_path, meta_path = _snapshot_paths(
        base_dir=base_dir,
        market=market,
        source=source,
        snapshot_type=snapshot_type,
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(snapshot_path, index=False)

    present_fields = [
        field_name
        for field_name in field_names
        if field_name in frame.columns and frame[field_name].notna().any()
    ]
    missing_fields = [
        field_name for field_name in field_names if field_name not in present_fields
    ]
    sync_result.rows_written = int(len(frame))
    sync_result.snapshot_path = str(snapshot_path)
    sync_result.meta_path = str(meta_path)
    sync_result.snapshot_paths[snapshot_type] = str(snapshot_path)
    sync_result.meta_paths[snapshot_type] = str(meta_path)
    sync_result.field_coverage = len(present_fields) / len(field_names)
    sync_result.missing_fields = missing_fields
    sync_result.updated_at = _utc_iso()
    meta_payload = asdict(sync_result)
    meta_payload.update(
        {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "snapshot_type": snapshot_type,
            "field_units": {
                field_name: FIELD_UNITS.get(field_name, "unknown")
                for field_name in field_names
            },
        }
    )
    write_json_atomic(meta_path, meta_payload)
    return sync_result


def _snapshot_subset(frame: pd.DataFrame, *, snapshot_type: str) -> pd.DataFrame:
    fields = SNAPSHOT_TYPE_FIELDS[snapshot_type]
    metadata = [
        "symbol",
        "market",
        "source",
        "as_of_date",
        "report_period",
        "updated_at",
        "currency",
        "name",
        "exchange",
        "sector",
        "industry",
        "listing_date",
        "missing_fields",
        "data_status",
    ]
    if frame.empty:
        return pd.DataFrame(columns=[*metadata, *fields])
    columns = [column for column in [*metadata, *fields] if column in frame.columns]
    subset = frame.loc[:, columns].copy() if columns else pd.DataFrame()
    if subset.empty:
        return subset
    for row_index, row in subset.iterrows():
        payload = row.to_dict()
        _finalize_fundamental_row(payload, fields=fields)
        for column, value in payload.items():
            subset.at[row_index, column] = value
    return subset


def _normalize_simfin_tickers(
    value: list[str] | tuple[str, ...] | str | None,
) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        tickers = [item.strip().upper() for item in value.split(",") if item.strip()]
    else:
        tickers = [str(item).strip().upper() for item in value if str(item).strip()]
    return tickers or None


def _load_simfin_signal_frame(hub: Any, loader_name: str) -> pd.DataFrame:
    loader = getattr(hub, loader_name)
    try:
        frame = loader(variant="daily")
    except TypeError:
        frame = loader()
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    if isinstance(frame.index, pd.MultiIndex):
        frame = frame.reset_index()
    return frame.dropna(axis=1, how="all")


def _combine_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        return pd.DataFrame()
    combined = pd.concat(usable, axis=1)
    return combined.loc[:, ~combined.columns.duplicated()]


def _column(frame: pd.DataFrame, *names: str) -> str | None:
    normalized = {
        str(column).strip().lower().replace("_", " "): str(column)
        for column in frame.columns
    }
    for name in names:
        match = normalized.get(name.strip().lower().replace("_", " "))
        if match:
            return match
    return None


def _latest_by_ticker(frame: pd.DataFrame) -> pd.DataFrame:
    ticker_col = _column(frame, "Ticker", "Symbol")
    if ticker_col is None:
        return pd.DataFrame()
    date_col = _column(frame, "Date", "Report Date", "Publish Date", "Fiscal Year")
    working = frame.copy()
    if date_col is not None:
        working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
        working = working.sort_values(date_col)
    return (
        working.groupby(working[ticker_col].astype(str).str.upper())
        .tail(1)
        .reset_index(drop=True)
    )


def _normalize_simfin_snapshot(
    frame: pd.DataFrame, *, as_of_date: str | None = None
) -> pd.DataFrame:
    latest = _latest_by_ticker(frame)
    if latest.empty:
        return pd.DataFrame(columns=["symbol", "market", "source", *FUNDAMENTAL_FIELDS])

    ticker_col = _column(latest, "Ticker", "Symbol")
    date_col = _column(latest, "Date", "Report Date", "Publish Date", "Fiscal Year")
    rows: list[dict[str, Any]] = []
    for _, row in latest.iterrows():
        payload: dict[str, Any] = {
            "symbol": str(row.get(ticker_col) or "").upper(),
            "market": "us",
            "source": "simfin",
            "as_of_date": as_of_date or _utc_iso()[:10],
            "report_period": str(row.get(date_col) or "")[:10] if date_col else "",
            "updated_at": _utc_iso(),
            "currency": "USD",
        }
        for source_column, target_column in SIMFIN_FIELD_MAP.items():
            if source_column in latest.columns:
                payload[target_column] = _safe_numeric(row.get(source_column))
        _finalize_fundamental_row(payload)
        rows.append(payload)
    return pd.DataFrame(rows)


def _frame_from_records(
    records: list[dict[str, Any]], symbol_key: str = "symbol"
) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    if symbol_key not in frame.columns:
        return pd.DataFrame()
    frame = frame.copy()
    frame[symbol_key] = frame[symbol_key].astype(str).str.strip().str.upper()
    return frame


def _latest_fmp_rows(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    frame = _frame_from_records(records)
    if frame.empty:
        return {}
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.sort_values("date")
    return {
        str(symbol): group.iloc[-1].to_dict()
        for symbol, group in frame.groupby(frame["symbol"].astype(str))
    }


def _fmp_row_date(row: dict[str, Any], as_of_date: str | None) -> str:
    value = row.get("date") or row.get("calendarYear") or row.get("fiscalDateEnding")
    if hasattr(value, "strftime") and not pd.isna(value):
        return value.strftime("%Y-%m-%d")
    if value:
        return str(value)[:10]
    return as_of_date or _utc_iso()[:10]


def _normalize_fmp_bulk_snapshots(
    *,
    ratios: list[dict[str, Any]],
    key_metrics: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    symbols: list[str] | None = None,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    ratio_rows = _latest_fmp_rows(ratios)
    metric_rows = _latest_fmp_rows(key_metrics)
    profile_rows = _latest_fmp_rows(profiles)
    symbol_set = {symbol.strip().upper() for symbol in symbols or [] if symbol.strip()}
    all_symbols = sorted(set(ratio_rows) | set(metric_rows) | set(profile_rows))
    if symbol_set:
        all_symbols = [symbol for symbol in all_symbols if symbol in symbol_set]

    rows: list[dict[str, Any]] = []
    for symbol in all_symbols:
        ratio_row = ratio_rows.get(symbol, {})
        metric_row = metric_rows.get(symbol, {})
        profile_row = profile_rows.get(symbol, {})
        report_period = _fmp_row_date(ratio_row or metric_row, as_of_date)
        payload: dict[str, Any] = {
            "symbol": symbol,
            "market": "us",
            "source": "fmp",
            "as_of_date": as_of_date or _utc_iso()[:10],
            "report_period": report_period,
            "updated_at": _utc_iso(),
            "currency": str(profile_row.get("currency") or "USD").upper(),
        }
        for source_column, target_column in FMP_RATIO_FIELD_MAP.items():
            if source_column in ratio_row:
                payload[target_column] = _safe_numeric(ratio_row.get(source_column))
        for source_column, target_column in FMP_KEY_METRICS_FIELD_MAP.items():
            if source_column in metric_row:
                payload[target_column] = _safe_numeric(metric_row.get(source_column))
        for source_column, target_column in FMP_PROFILE_FIELD_MAP.items():
            if source_column in profile_row:
                value = profile_row.get(source_column)
                payload[target_column] = (
                    _safe_numeric(value)
                    if target_column in MARKET_SNAPSHOT_FIELDS
                    else value
                )
        _finalize_fundamental_row(payload)
        rows.append(payload)
    return pd.DataFrame(rows)


def _normalize_tencent_quote_snapshot(
    rows: list[dict[str, Any]], *, as_of_date: str | None = None
) -> pd.DataFrame:
    snapshot_rows: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        payload: dict[str, Any] = {
            "symbol": symbol,
            "market": "us",
            "source": "tencent",
            "as_of_date": as_of_date or _utc_iso()[:10],
            "updated_at": _utc_iso(),
            "currency": str(row.get("currency") or "USD").upper(),
        }
        for field_name in [
            "name",
            "exchange",
            "sector",
            "industry",
            *MARKET_SNAPSHOT_FIELDS,
        ]:
            if field_name in row:
                payload[field_name] = row.get(field_name)
        _finalize_fundamental_row(payload, fields=MARKET_SNAPSHOT_FIELDS)
        snapshot_rows.append(payload)
    return pd.DataFrame(snapshot_rows)


def sync_us_simfin_fundamentals(
    *,
    api_key: str,
    tickers: list[str] | tuple[str, ...] | str | None = None,
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    as_of_date: str | None = None,
) -> SyncResult:
    simfin = import_module("simfin")
    simfin.set_api_key(api_key)
    if data_dir is not None:
        simfin.set_data_dir(str(data_dir))
    normalized_tickers = _normalize_simfin_tickers(tickers)
    hub = simfin.StockHub(market="us", tickers=normalized_tickers)
    combined = _combine_frames(
        [
            _load_simfin_signal_frame(hub, "val_signals"),
            _load_simfin_signal_frame(hub, "fin_signals"),
            _load_simfin_signal_frame(hub, "growth_signals"),
        ]
    )
    snapshot = _normalize_simfin_snapshot(combined, as_of_date=as_of_date)
    result = SyncResult(
        sync_type="fundamentals",
        markets=["us"],
        source="simfin",
        status="completed",
        symbols_total=len(normalized_tickers or snapshot.index),
        symbols_success=int(len(snapshot)),
    )
    result.symbols_failed = max(result.symbols_total - result.symbols_success, 0)
    market_snapshot = _snapshot_subset(snapshot, snapshot_type="market")
    financial_snapshot = _snapshot_subset(snapshot, snapshot_type="financial")
    market_rows = int(len(market_snapshot))
    financial_rows = int(len(financial_snapshot))
    _save_fundamental_snapshot(
        market_snapshot,
        base_dir=output_dir,
        market="us",
        source="simfin",
        sync_result=result,
        snapshot_type="market",
    )
    _save_fundamental_snapshot(
        financial_snapshot,
        base_dir=output_dir,
        market="us",
        source="simfin",
        sync_result=result,
        snapshot_type="financial",
    )
    result.rows_written = market_rows + financial_rows
    return result


def sync_us_fmp_fundamentals(
    *,
    symbols: list[str] | tuple[str, ...] | str | None = None,
    output_dir: str | Path | None = None,
    as_of_date: str | None = None,
    include_profile: bool = True,
    profile_parts: int = 1,
) -> SyncResult:
    normalized_symbols = _normalize_simfin_tickers(symbols) or []
    ratios = fetch_ratios_ttm_bulk()
    key_metrics = fetch_key_metrics_ttm_bulk()
    profiles: list[dict[str, Any]] = []
    if include_profile:
        for part in range(max(int(profile_parts), 0)):
            profiles.extend(fetch_profile_bulk(part=part))
    snapshot = _normalize_fmp_bulk_snapshots(
        ratios=ratios,
        key_metrics=key_metrics,
        profiles=profiles,
        symbols=normalized_symbols or None,
        as_of_date=as_of_date,
    )
    result = SyncResult(
        sync_type="fundamentals",
        markets=["us"],
        source="fmp",
        status="completed",
        symbols_total=len(normalized_symbols or snapshot.index),
        symbols_success=int(len(snapshot)),
    )
    result.symbols_failed = max(result.symbols_total - result.symbols_success, 0)
    market_snapshot = _snapshot_subset(snapshot, snapshot_type="market")
    financial_snapshot = _snapshot_subset(snapshot, snapshot_type="financial")
    market_rows = int(len(market_snapshot))
    financial_rows = int(len(financial_snapshot))
    _save_fundamental_snapshot(
        market_snapshot,
        base_dir=output_dir,
        market="us",
        source="fmp",
        sync_result=result,
        snapshot_type="market",
    )
    _save_fundamental_snapshot(
        financial_snapshot,
        base_dir=output_dir,
        market="us",
        source="fmp",
        sync_result=result,
        snapshot_type="financial",
    )
    result.rows_written = market_rows + financial_rows
    return result


def sync_us_tencent_market_snapshot(
    *,
    symbols: list[str] | tuple[str, ...] | str,
    output_dir: str | Path | None = None,
    as_of_date: str | None = None,
    batch_size: int = 60,
    request_interval_seconds: float = 0.12,
) -> SyncResult:
    normalized_symbols = _normalize_simfin_tickers(symbols) or []
    rows = fetch_us_quote_rows(
        normalized_symbols,
        batch_size=batch_size,
        request_interval_seconds=request_interval_seconds,
    )
    snapshot = _normalize_tencent_quote_snapshot(rows, as_of_date=as_of_date)
    result = SyncResult(
        sync_type="fundamentals",
        markets=["us"],
        source="tencent",
        status="completed",
        symbols_total=len(normalized_symbols),
        symbols_success=int(len(snapshot)),
        symbols_failed=max(len(normalized_symbols) - int(len(snapshot)), 0),
    )
    _save_fundamental_snapshot(
        snapshot,
        base_dir=output_dir,
        market="us",
        source="tencent",
        sync_result=result,
        snapshot_type="market",
    )
    return result


def _normalize_tushare_indicator_frame(
    frame: pd.DataFrame, *, as_of_date: str | None = None
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "market", "source", *FUNDAMENTAL_FIELDS])
    working = frame.copy()
    if "end_date" in working.columns:
        working["end_date"] = pd.to_datetime(working["end_date"], errors="coerce")
        working = working.sort_values("end_date")
    symbol_col = "ts_code" if "ts_code" in working.columns else "symbol"
    rows: list[dict[str, Any]] = []
    for symbol, group in working.groupby(working[symbol_col].astype(str)):
        row = group.iloc[-1]
        payload: dict[str, Any] = {
            "symbol": str(symbol),
            "market": "cn",
            "source": "tushare",
            "as_of_date": as_of_date or _utc_iso()[:10],
            "report_period": str(row.get("end_date") or "")[:10],
            "updated_at": _utc_iso(),
            "currency": "CNY",
        }
        for source_column, target_column in TUSHARE_FIELD_MAP.items():
            if source_column in working.columns:
                if source_column in TUSHARE_PERCENT_FIELD_MAP:
                    payload[target_column] = _safe_decimal_percent(
                        row.get(source_column)
                    )
                else:
                    payload[target_column] = _safe_numeric(row.get(source_column))
        _finalize_fundamental_row(payload, fields=FINANCIAL_SNAPSHOT_FIELDS)
        rows.append(payload)
    return pd.DataFrame(rows)


def _normalize_tushare_daily_basic_frame(
    frame: pd.DataFrame, *, as_of_date: str | None = None
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "market", "source", *FUNDAMENTAL_FIELDS])
    working = frame.copy()
    if "trade_date" in working.columns:
        working["trade_date"] = pd.to_datetime(
            working["trade_date"].astype(str),
            format="%Y%m%d",
            errors="coerce",
        )
        working = working.sort_values("trade_date")
    symbol_col = "ts_code" if "ts_code" in working.columns else "symbol"
    rows: list[dict[str, Any]] = []
    for symbol, group in working.groupby(working[symbol_col].astype(str)):
        row = group.iloc[-1]
        trade_date = row.get("trade_date")
        report_period = (
            trade_date.strftime("%Y-%m-%d")
            if hasattr(trade_date, "strftime") and not pd.isna(trade_date)
            else str(trade_date or "")[:10]
        )
        payload: dict[str, Any] = {
            "symbol": str(symbol),
            "market": "cn",
            "source": "tushare",
            "as_of_date": as_of_date or report_period or _utc_iso()[:10],
            "report_period": report_period,
            "updated_at": _utc_iso(),
            "currency": "CNY",
        }
        for source_column, target_column in TUSHARE_DAILY_BASIC_FIELD_MAP.items():
            if source_column in working.columns:
                value = (
                    _safe_decimal_percent(row.get(source_column))
                    if source_column in TUSHARE_DAILY_BASIC_PERCENT_FIELDS
                    else _safe_numeric(row.get(source_column))
                )
                if source_column in {"total_mv", "circ_mv"} and value is not None:
                    value *= 10_000
                payload[target_column] = value
        _finalize_fundamental_row(payload, fields=MARKET_SNAPSHOT_FIELDS)
        rows.append(payload)
    return pd.DataFrame(rows)


def sync_cn_tushare_fundamentals(
    *,
    symbols: list[str] | tuple[str, ...],
    output_dir: str | Path | None = None,
    as_of_date: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> SyncResult:
    pro = get_tushare_pro_client()
    normalized_symbols = [
        str(symbol).strip() for symbol in symbols if str(symbol).strip()
    ]
    result = SyncResult(
        sync_type="fundamentals",
        markets=["cn"],
        source="tushare",
        status="completed",
        symbols_total=len(normalized_symbols),
    )
    market_snapshot = pd.DataFrame()
    if as_of_date:
        trade_date = as_of_date.replace("-", "")
        try:
            daily_basic = pro.daily_basic(
                trade_date=trade_date,
                fields=(
                    "ts_code,trade_date,turnover_rate,turnover_rate_f,volume_ratio,"
                    "pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,"
                    "free_share,total_mv,circ_mv"
                ),
            )
        except Exception:
            daily_basic = pd.DataFrame()
        if daily_basic is not None and not daily_basic.empty:
            symbol_set = set(normalized_symbols)
            market_snapshot = _normalize_tushare_daily_basic_frame(
                daily_basic.loc[daily_basic["ts_code"].astype(str).isin(symbol_set)],
                as_of_date=as_of_date,
            )
            _save_fundamental_snapshot(
                market_snapshot,
                base_dir=output_dir,
                market="cn",
                source="tushare",
                sync_result=result,
                snapshot_type="market",
            )

    rows: list[pd.DataFrame] = []
    failed_symbols: list[dict[str, str]] = []
    for index, symbol in enumerate(normalized_symbols, start=1):
        try:
            frame = pro.fina_indicator(ts_code=symbol)
            if frame is None or frame.empty:
                failed_symbols.append({"symbol": symbol, "reason": "empty"})
                continue
            rows.append(frame)
        except Exception as exc:
            failed_symbols.append({"symbol": symbol, "reason": str(exc)})
        finally:
            if progress_callback is not None:
                progress_callback(index, len(normalized_symbols), symbol)

    combined = (
        pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    )
    financial_snapshot = _normalize_tushare_indicator_frame(
        combined, as_of_date=as_of_date
    )
    _save_fundamental_snapshot(
        financial_snapshot,
        base_dir=output_dir,
        market="cn",
        source="tushare",
        sync_result=result,
        snapshot_type="financial",
    )
    successful_symbols = {
        str(symbol)
        for frame in (market_snapshot, financial_snapshot)
        if not frame.empty and "symbol" in frame.columns
        for symbol in frame["symbol"].dropna().tolist()
    }
    result.symbols_success = len(successful_symbols)
    result.symbols_failed = max(len(normalized_symbols) - result.symbols_success, 0)
    if failed_symbols:
        result.failed_symbols = failed_symbols
    result.rows_written = int(len(market_snapshot) + len(financial_snapshot))
    return result


def sync_ohlcv_cache(
    config: ScreenRunConfig,
    *,
    progress_callback: Callable[..., None] | None = None,
) -> SyncResult:
    cache_root = Path(config.cache_dir or resolve_screener_cache_dir())
    history_root = Path(config.history_dir or resolve_history_dir())
    start_date = _ohlcv_history_start(config.as_of_date)
    universe_stage = prepare_universe_stage(
        config,
        cache_root,
        progress_callback=progress_callback,
    )
    histories, failures = fetch_history_for_universe(
        universe_stage.prefiltered_df,
        config.as_of_date,
        cn_data_source=config.cn_data_source,
        cn_data_source_fallbacks=config.cn_data_source_fallbacks,
        us_data_source=config.us_data_source,
        us_data_source_fallbacks=config.us_data_source_fallbacks,
        progress_callback=progress_callback,
        history_dir=history_root,
        cache_dir=cache_root,
        checkpoint_dir=cache_root / "checkpoints",
    )
    quality_rows = _build_ohlcv_quality_rows(
        universe_stage.prefiltered_df,
        history_root=history_root,
        start_date=start_date,
        as_of_date=config.as_of_date,
    )
    for retry_index in range(1, OHLCV_SYNC_RETRY_ROUNDS + 1):
        retry_universe_df = _retry_universe_from_quality_rows(
            universe_stage.prefiltered_df,
            quality_rows,
        )
        if retry_universe_df.empty:
            break
        retry_histories, failures = fetch_history_for_universe(
            retry_universe_df,
            config.as_of_date,
            cn_data_source=config.cn_data_source,
            cn_data_source_fallbacks=config.cn_data_source_fallbacks,
            us_data_source=config.us_data_source,
            us_data_source_fallbacks=config.us_data_source_fallbacks,
            progress_callback=progress_callback,
            history_dir=history_root,
            cache_dir=cache_root,
            checkpoint_dir=cache_root / "checkpoints" / f"retry_{retry_index}",
        )
        histories.update(retry_histories)
        quality_rows = _build_ohlcv_quality_rows(
            universe_stage.prefiltered_df,
            history_root=history_root,
            start_date=start_date,
            as_of_date=config.as_of_date,
        )

    meta_path = cache_root / "sync" / "ohlcv_sync_meta.json"
    quality_path = _quality_artifact_path(cache_root, config)
    _write_ohlcv_quality_artifact(
        quality_path,
        config=config,
        quality_rows=quality_rows,
    )
    ready_symbols = _ready_symbol_set(quality_rows)
    ready_histories = {
        symbol: frame for symbol, frame in histories.items() if symbol in ready_symbols
    }
    failed_symbols = _failed_symbols_from_quality_rows(quality_rows)
    reason_counts = _quality_reason_counts(quality_rows)
    missing_as_of_bar_count = int(reason_counts.get("missing_as_of_bar", 0))
    result = SyncResult(
        sync_type="ohlcv",
        markets=list(config.markets),
        source=",".join(
            [
                f"cn:{config.cn_data_source}",
                f"us:{config.us_data_source}",
            ]
        ),
        status="completed",
        symbols_total=int(len(universe_stage.prefiltered_df)),
        symbols_success=int(len(ready_histories)),
        symbols_failed=int(len(failed_symbols)),
        rows_written=int(sum(len(frame) for frame in ready_histories.values())),
        snapshot_path=str(history_root),
        meta_path=str(meta_path),
        failed_symbols=failed_symbols,
        quality_artifact_path=str(quality_path),
        quality_reason_counts=reason_counts,
        symbols_missing_as_of_bar=missing_as_of_bar_count,
        symbols_pruned_from_screener=int(len(failed_symbols)),
        missing_as_of_bar_symbols=_missing_as_of_bar_symbols(quality_rows),
        updated_at=_utc_iso(),
    )
    write_json_atomic(meta_path, asdict(result))
    return result
