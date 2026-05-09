from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from diverge.screener.market_data import LOOKBACK_DAYS, fetch_ticker_history
from diverge.screener.history_cache import history_cache_path
from web.backend import app_config, storage
from web.backend.schemas.ticker_history import TickerHistoryBatchPayload


def normalize_history_symbol(symbol: str) -> str:
    candidate = str(symbol or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="symbol is required")
    return candidate


def normalize_history_as_of_date(value: str | None) -> str:
    if value is None or not value.strip():
        return datetime.now().strftime("%Y-%m-%d")

    candidate = value.strip()
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="as_of_date must use YYYY-MM-DD format",
        ) from exc
    return candidate


def normalize_history_days(value: int | None) -> int:
    resolved = LOOKBACK_DAYS if value is None else int(value)
    if resolved <= 0:
        raise HTTPException(status_code=400, detail="days must be positive")
    return resolved


def history_cache_dir() -> Path:
    return app_config.STOCK_HISTORY_DIR


def storage_backend_is_remote() -> bool:
    return storage.os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"


def _json_number(value):
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def serialize_history_frame(df, *, include_ohlcv: bool) -> list[dict]:
    if df is None or df.empty:
        return []

    points: list[dict] = []
    for row in df.itertuples(index=False):
        point = {
            "date": getattr(row, "Date"),
            "close": _json_number(getattr(row, "Close", None)),
        }
        if include_ohlcv:
            point.update(
                {
                    "open": _json_number(getattr(row, "Open", None)),
                    "high": _json_number(getattr(row, "High", None)),
                    "low": _json_number(getattr(row, "Low", None)),
                    "volume": _json_number(getattr(row, "Volume", None)),
                }
            )
        points.append(point)
    return points


def ticker_history_response(
    *,
    symbol: str,
    market: str,
    as_of_date: str,
    lookback_days: int,
    frame,
    include_ohlcv: bool,
) -> dict:
    points = serialize_history_frame(frame, include_ohlcv=include_ohlcv)
    return {
        "symbol": symbol,
        "market": market,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "start_date": points[0]["date"] if points else None,
        "end_date": points[-1]["date"] if points else None,
        "points": points,
    }


def get_ticker_history_payload(
    symbol: str,
    *,
    market: str | None = None,
    as_of_date: str | None = None,
    days: int | None = None,
    include_ohlcv: bool = True,
) -> dict:
    normalized_symbol = normalize_history_symbol(symbol)
    normalized_as_of_date = normalize_history_as_of_date(as_of_date)
    normalized_days = normalize_history_days(days)

    try:
        if storage_backend_is_remote() and market:
            target = history_cache_path(history_cache_dir(), market, normalized_symbol)
            if not target.is_file():
                key = f"history/{market}/{target.name}"
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(storage.get_storage().get_bytes(key))
                except Exception:
                    pass
        resolved_market, frame = fetch_ticker_history(
            normalized_symbol,
            market=market,
            as_of_date=normalized_as_of_date,
            lookback_days=normalized_days,
            cache_dir=history_cache_dir(),
        )
        if storage_backend_is_remote():
            target = history_cache_path(
                history_cache_dir(), resolved_market, normalized_symbol
            )
            if target.is_file():
                storage.get_storage().put_bytes(
                    f"history/{resolved_market}/{target.name}",
                    target.read_bytes(),
                    content_type="text/csv",
                )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to load ticker history: {exc}"
        ) from exc

    return ticker_history_response(
        symbol=normalized_symbol,
        market=resolved_market,
        as_of_date=normalized_as_of_date,
        lookback_days=normalized_days,
        frame=frame,
        include_ohlcv=include_ohlcv,
    )


def get_batch_ticker_history_payload(payload: TickerHistoryBatchPayload) -> dict:
    normalized_as_of_date = normalize_history_as_of_date(payload.as_of_date)
    normalized_days = normalize_history_days(payload.days)
    tickers = payload.tickers or []
    if not tickers:
        raise HTTPException(
            status_code=400, detail="tickers must include at least one item"
        )
    if len(tickers) > 50:
        raise HTTPException(status_code=400, detail="tickers must not exceed 50 items")

    items: list[dict] = []
    for ticker in tickers:
        items.append(
            get_ticker_history_payload(
                ticker.symbol,
                market=ticker.market,
                as_of_date=normalized_as_of_date,
                days=normalized_days,
                include_ohlcv=False,
            )
        )

    return {
        "as_of_date": normalized_as_of_date,
        "lookback_days": normalized_days,
        "items": items,
    }
