from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


HISTORY_CACHE_DIRNAME = "history"
HISTORY_FAILURE_CACHE_DIRNAME = "history_failures"


def _normalize_history_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount"])

    normalized = df.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    normalized = normalized.dropna(subset=["Date"])
    normalized = normalized.drop_duplicates(subset=["Date"], keep="last")
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    return normalized.loc[:, ["Date", "Open", "High", "Low", "Close", "Volume", "Amount"]]


def history_cache_path(cache_dir: str | Path, market: str, symbol: str) -> Path:
    safe_symbol = symbol.replace("/", "_").replace("\\", "_")
    return Path(cache_dir) / HISTORY_CACHE_DIRNAME / market / f"{safe_symbol}.csv"


def load_history_cache(cache_dir: str | Path, market: str, symbol: str) -> pd.DataFrame:
    path = history_cache_path(cache_dir, market, symbol)
    if not path.is_file():
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount"])
    return _normalize_history_frame(pd.read_csv(path))


def save_history_cache(cache_dir: str | Path, market: str, symbol: str, frame: pd.DataFrame) -> Path:
    path = history_cache_path(cache_dir, market, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    _normalize_history_frame(frame).to_csv(path, index=False)
    return path


def history_failure_cache_path(cache_dir: str | Path, market: str, symbol: str) -> Path:
    safe_symbol = symbol.replace("/", "_").replace("\\", "_")
    return Path(cache_dir) / HISTORY_FAILURE_CACHE_DIRNAME / market / f"{safe_symbol}.json"


def load_history_failure_cache(
    cache_dir: str | Path,
    market: str,
    symbol: str,
    *,
    max_age: timedelta | None = None,
) -> dict | None:
    path = history_failure_cache_path(cache_dir, market, symbol)
    if not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    updated_at_raw = payload.get("updated_at")
    if max_age is not None and isinstance(updated_at_raw, str):
        try:
            updated_at = datetime.fromisoformat(updated_at_raw)
        except ValueError:
            updated_at = None
        if updated_at is not None and datetime.now(timezone.utc) - updated_at > max_age:
            try:
                path.unlink()
            except OSError:
                pass
            return None

    return payload


def save_history_failure_cache(
    cache_dir: str | Path,
    market: str,
    symbol: str,
    *,
    drop_reason: str,
) -> Path:
    path = history_failure_cache_path(cache_dir, market, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "market": market,
        "drop_reason": drop_reason,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def delete_history_failure_cache(cache_dir: str | Path, market: str, symbol: str) -> None:
    path = history_failure_cache_path(cache_dir, market, symbol)
    if path.exists():
        path.unlink()

    for parent in (path.parent, path.parent.parent):
        try:
            parent.rmdir()
        except OSError:
            break


def slice_history_window(frame: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    normalized = _normalize_history_frame(frame)
    if normalized.empty:
        return normalized
    window = normalized[(normalized["Date"] >= start_date) & (normalized["Date"] <= end_date)]
    return window.reset_index(drop=True)


def merge_history_frames(existing_frame: pd.DataFrame, new_frame: pd.DataFrame) -> pd.DataFrame:
    if existing_frame.empty:
        return _normalize_history_frame(new_frame)
    if new_frame.empty:
        return _normalize_history_frame(existing_frame)
    combined = pd.concat([existing_frame, new_frame], ignore_index=True)
    return _normalize_history_frame(combined)


def resolve_incremental_fetch_start(
    cached_frame: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> str | None:
    normalized = _normalize_history_frame(cached_frame)
    if normalized.empty:
        return start_date

    cached_start = str(normalized["Date"].min())
    cached_end = str(normalized["Date"].max())
    if cached_start <= start_date and cached_end >= end_date:
        return None
    if cached_start <= start_date and cached_end < end_date:
        next_date = datetime.strptime(cached_end, "%Y-%m-%d") + timedelta(days=1)
        return max(start_date, next_date.strftime("%Y-%m-%d"))
    return start_date


def checkpoint_path(
    checkpoint_dir: str | Path,
    universe_df: pd.DataFrame,
    as_of_date: str,
    cn_data_source: str,
) -> Path:
    symbols = [
        f"{row.market}:{row.symbol}"
        for row in universe_df.loc[:, ["market", "symbol"]].itertuples(index=False)
    ]
    payload = {
        "as_of_date": as_of_date,
        "cn_data_source": cn_data_source,
        "symbols": symbols,
    }
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return Path(checkpoint_dir) / digest / "history.json"


def load_checkpoint(path: str | Path) -> dict | None:
    checkpoint_file = Path(path)
    if not checkpoint_file.is_file():
        return None

    return json.loads(checkpoint_file.read_text(encoding="utf-8"))


def save_checkpoint(
    path: str | Path,
    *,
    as_of_date: str,
    start_date: str,
    processed_symbols: list[str],
    fetch_failed_symbols: list[str],
    failed_symbols: list[dict] | None,
    universe_total: int,
    last_symbol: str | None,
) -> None:
    checkpoint_file = Path(path)
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of_date": as_of_date,
        "start_date": start_date,
        "processed_symbols": processed_symbols,
        "fetch_failed_symbols": fetch_failed_symbols,
        "failed_symbols": failed_symbols or [],
        "universe_total": universe_total,
        "last_symbol": last_symbol,
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
