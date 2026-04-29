from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from diverge.data_layout import (
    resolve_fundamentals_dir,
    resolve_history_dir,
    resolve_screener_cache_dir,
)
from diverge.dataflows.vendors.tushare.common import get_tushare_pro_client
from diverge.screener.market_data import fetch_history_for_universe
from diverge.screener.schema import ScreenRunConfig
from diverge.screener.stages import prepare_universe_stage


FUNDAMENTAL_FIELDS = [
    "market_cap",
    "pe_ttm",
    "ps_ttm",
    "pb",
    "peg",
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

TUSHARE_FIELD_MAP = {
    "roe": "roe",
    "roa": "roa",
    "grossprofit_margin": "gross_margin",
    "netprofit_margin": "net_margin",
    "current_ratio": "current_ratio",
    "debt_to_assets": "debt_to_assets",
    "ocfps": "operating_cashflow_quality",
}


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
    field_coverage: float | None = None
    missing_fields: list[str] = field(default_factory=list)
    failed_symbols: list[dict[str, str]] = field(default_factory=list)
    updated_at: str = ""


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _safe_numeric(value: Any) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return float(parsed)


def _snapshot_paths(
    *,
    base_dir: str | Path | None,
    market: str,
    source: str,
) -> tuple[Path, Path]:
    root = Path(base_dir) if base_dir is not None else resolve_fundamentals_dir()
    snapshot_dir = root / source / market
    return snapshot_dir / "snapshots.csv", snapshot_dir / "sync_meta.json"


def _save_fundamental_snapshot(
    frame: pd.DataFrame,
    *,
    base_dir: str | Path | None,
    market: str,
    source: str,
    sync_result: SyncResult,
) -> SyncResult:
    snapshot_path, meta_path = _snapshot_paths(
        base_dir=base_dir,
        market=market,
        source=source,
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(snapshot_path, index=False)

    present_fields = [
        field_name
        for field_name in FUNDAMENTAL_FIELDS
        if field_name in frame.columns and frame[field_name].notna().any()
    ]
    missing_fields = [
        field_name
        for field_name in FUNDAMENTAL_FIELDS
        if field_name not in present_fields
    ]
    sync_result.rows_written = int(len(frame))
    sync_result.snapshot_path = str(snapshot_path)
    sync_result.meta_path = str(meta_path)
    sync_result.field_coverage = len(present_fields) / len(FUNDAMENTAL_FIELDS)
    sync_result.missing_fields = missing_fields
    sync_result.updated_at = _utc_iso()
    _write_json(meta_path, asdict(sync_result))
    return sync_result


def _normalize_simfin_tickers(value: list[str] | tuple[str, ...] | str | None) -> list[str] | None:
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
    return working.groupby(working[ticker_col].astype(str).str.upper()).tail(1).reset_index(drop=True)


def _normalize_simfin_snapshot(frame: pd.DataFrame, *, as_of_date: str | None = None) -> pd.DataFrame:
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
        }
        for source_column, target_column in SIMFIN_FIELD_MAP.items():
            if source_column in latest.columns:
                payload[target_column] = _safe_numeric(row.get(source_column))
        missing = [
            field_name
            for field_name in FUNDAMENTAL_FIELDS
            if payload.get(field_name) is None
        ]
        payload["missing_fields"] = ",".join(missing)
        payload["data_status"] = "partial" if missing else "fresh"
        rows.append(payload)
    return pd.DataFrame(rows)


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
    return _save_fundamental_snapshot(
        snapshot,
        base_dir=output_dir,
        market="us",
        source="simfin",
        sync_result=result,
    )


def _normalize_tushare_indicator_frame(frame: pd.DataFrame, *, as_of_date: str | None = None) -> pd.DataFrame:
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
        }
        for source_column, target_column in TUSHARE_FIELD_MAP.items():
            if source_column in working.columns:
                payload[target_column] = _safe_numeric(row.get(source_column))
        missing = [
            field_name
            for field_name in FUNDAMENTAL_FIELDS
            if payload.get(field_name) is None
        ]
        payload["missing_fields"] = ",".join(missing)
        payload["data_status"] = "partial" if missing else "fresh"
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
    rows: list[pd.DataFrame] = []
    failed_symbols: list[dict[str, str]] = []
    normalized_symbols = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
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

    combined = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    snapshot = _normalize_tushare_indicator_frame(combined, as_of_date=as_of_date)
    result = SyncResult(
        sync_type="fundamentals",
        markets=["cn"],
        source="tushare",
        status="completed",
        symbols_total=len(normalized_symbols),
        symbols_success=int(len(snapshot)),
        symbols_failed=len(failed_symbols),
        failed_symbols=failed_symbols,
    )
    return _save_fundamental_snapshot(
        snapshot,
        base_dir=output_dir,
        market="cn",
        source="tushare",
        sync_result=result,
    )


def sync_ohlcv_cache(
    config: ScreenRunConfig,
    *,
    progress_callback: Callable[..., None] | None = None,
) -> SyncResult:
    cache_root = Path(config.cache_dir or resolve_screener_cache_dir())
    history_root = Path(config.history_dir or resolve_history_dir())
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
    meta_path = cache_root / "sync" / "ohlcv_sync_meta.json"
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
        symbols_success=int(len(histories)),
        symbols_failed=int(len(failures)),
        rows_written=int(sum(len(frame) for frame in histories.values())),
        snapshot_path=str(history_root),
        meta_path=str(meta_path),
        failed_symbols=failures.to_dict("records") if not failures.empty else [],
        updated_at=_utc_iso(),
    )
    _write_json(meta_path, asdict(result))
    return result
