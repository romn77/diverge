from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from diverge.common.dates import offset_iso_date


REQUIRED_PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Amount"]
NUMERIC_PRICE_COLUMNS = REQUIRED_PRICE_COLUMNS[1:]
HISTORY_READY_STATUS = "ready"
HISTORY_CACHE_MISS_STATUS = "history_cache_miss"
HISTORY_MISSING_AS_OF_BAR_STATUS = "missing_as_of_bar"
HISTORY_CACHE_NO_WINDOW_STATUS = "history_cache_no_window"


def empty_history_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_PRICE_COLUMNS)


def normalize_history_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_history_frame()

    normalized = df.copy()
    for column in REQUIRED_PRICE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA

    # Normalize mixed naive/tz-aware timestamps onto one UTC timeline before stringifying.
    normalized["Date"] = pd.to_datetime(
        normalized["Date"],
        errors="coerce",
        utc=True,
    ).dt.strftime("%Y-%m-%d")
    normalized = normalized.dropna(subset=["Date"])

    for column in NUMERIC_PRICE_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized["Amount"] = normalized["Amount"].where(
        normalized["Amount"].notna(),
        normalized["Close"] * normalized["Volume"],
    )
    normalized = normalized.drop_duplicates(subset=["Date"], keep="last")
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    return normalized.loc[:, REQUIRED_PRICE_COLUMNS]


def prepare_history_frame_for_indicators(df: pd.DataFrame) -> pd.DataFrame:
    working = normalize_history_frame(df)
    if working.empty:
        return working

    working = working.copy()
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    working = working.dropna(subset=["Date"])
    working = working.dropna(subset=NUMERIC_PRICE_COLUMNS).reset_index(drop=True)
    return working


def history_cache_path(history_dir: str | Path, market: str, symbol: str) -> Path:
    safe_symbol = symbol.replace("/", "_").replace("\\", "_")
    return Path(history_dir) / market / f"{safe_symbol}.csv"


def load_history_cache(
    history_dir: str | Path, market: str, symbol: str
) -> pd.DataFrame:
    path = history_cache_path(history_dir, market, symbol)
    if not path.is_file():
        return empty_history_frame()
    return normalize_history_frame(pd.read_csv(path))


def save_history_cache(
    history_dir: str | Path, market: str, symbol: str, frame: pd.DataFrame
) -> Path:
    path = history_cache_path(history_dir, market, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalize_history_frame(frame).to_csv(path, index=False)
    return path


def slice_history_window(
    frame: pd.DataFrame, start_date: str, end_date: str
) -> pd.DataFrame:
    normalized = normalize_history_frame(frame)
    if normalized.empty:
        return normalized
    window = normalized[
        (normalized["Date"] >= start_date) & (normalized["Date"] <= end_date)
    ]
    return window.reset_index(drop=True)


def history_cache_span(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    normalized = normalize_history_frame(frame)
    if normalized.empty:
        return None, None
    return str(normalized["Date"].min()), str(normalized["Date"].max())


def classify_history_cache_coverage(
    frame: pd.DataFrame,
    *,
    start_date: str,
    as_of_date: str,
) -> dict[str, str | None]:
    normalized = normalize_history_frame(frame)
    cache_start, cache_end = history_cache_span(normalized)
    cache_span = (
        f"{cache_start}..{cache_end}"
        if cache_start is not None and cache_end is not None
        else None
    )

    if normalized.empty:
        status = HISTORY_CACHE_MISS_STATUS
    elif cache_end is None or cache_end < as_of_date:
        status = HISTORY_MISSING_AS_OF_BAR_STATUS
    else:
        cached_window = slice_history_window(normalized, start_date, as_of_date)
        status = (
            HISTORY_READY_STATUS
            if not cached_window.empty
            else HISTORY_CACHE_NO_WINDOW_STATUS
        )

    return {
        "status": status,
        "cache_start": cache_start,
        "cache_end": cache_end,
        "cache_span": cache_span,
    }


def merge_history_frames(
    existing_frame: pd.DataFrame, new_frame: pd.DataFrame
) -> pd.DataFrame:
    if existing_frame.empty:
        return normalize_history_frame(new_frame)
    if new_frame.empty:
        return normalize_history_frame(existing_frame)
    combined = pd.concat([existing_frame, new_frame], ignore_index=True)
    return normalize_history_frame(combined)


def resolve_incremental_fetch_start(
    cached_frame: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> str | None:
    normalized = normalize_history_frame(cached_frame)
    if normalized.empty:
        return start_date

    cached_start = str(normalized["Date"].min())
    cached_end = str(normalized["Date"].max())
    if cached_start <= start_date and cached_end >= end_date:
        return None
    if cached_start <= start_date and cached_end < end_date:
        return max(start_date, offset_iso_date(cached_end, 1))
    return start_date


def checkpoint_path(
    checkpoint_dir: str | Path,
    universe_df: pd.DataFrame,
    as_of_date: str,
    cn_data_source: str,
    *,
    cn_data_source_fallbacks: list[str] | None = None,
    us_data_source: str | None = None,
    us_data_source_fallbacks: list[str] | None = None,
) -> Path:
    symbols = [
        f"{row.market}:{row.symbol}"
        for row in universe_df.loc[:, ["market", "symbol"]].itertuples(index=False)
    ]
    payload = {
        "as_of_date": as_of_date,
        "cn_data_source": cn_data_source,
        "cn_data_source_fallbacks": list(cn_data_source_fallbacks or []),
        "symbols": symbols,
        "us_data_source": us_data_source,
        "us_data_source_fallbacks": list(us_data_source_fallbacks or []),
    }
    digest = hashlib.sha1(
        json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()[:16]
    return Path(checkpoint_dir) / digest / "history.json"


def load_checkpoint(
    path: str | Path, *, max_age: timedelta | None = None
) -> dict | None:
    checkpoint_file = Path(path)
    if not checkpoint_file.is_file():
        return None

    try:
        payload = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    updated_at_raw = payload.get("updated_at")
    if max_age is not None and isinstance(updated_at_raw, str):
        try:
            updated_at = datetime.fromisoformat(updated_at_raw)
        except ValueError:
            updated_at = None
        if updated_at is not None and datetime.now(timezone.utc) - updated_at > max_age:
            delete_checkpoint(checkpoint_file)
            return None

    return payload


def save_checkpoint(
    path: str | Path,
    *,
    start_date: str,
    failed_symbols: list[dict],
) -> None:
    checkpoint_file = Path(path)
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "start_date": start_date,
        "failed_symbols": failed_symbols,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    checkpoint_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_checkpoint(path: str | Path) -> None:
    checkpoint_file = Path(path)
    if checkpoint_file.exists():
        checkpoint_file.unlink()

    for parent in (checkpoint_file.parent, checkpoint_file.parent.parent):
        try:
            parent.rmdir()
        except OSError:
            break
