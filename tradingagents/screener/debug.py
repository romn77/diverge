from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .schema import ScreenRunConfig


def load_universe(config: ScreenRunConfig, cache_dir: str | Path | None = None) -> pd.DataFrame:
    from .universe import load_universe as _load_universe

    return _load_universe(config, cache_dir=cache_dir)


def apply_universe_prefilters(
    universe_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from .universe_prefilter import apply_universe_prefilters as _apply_universe_prefilters

    return _apply_universe_prefilters(universe_df, config)


def fetch_history_for_universe(
    universe_df: pd.DataFrame,
    as_of_date: str,
    cn_data_source: str = "tushare",
    cn_data_source_fallbacks: list[str] | None = None,
    us_data_source: str = "yfinance",
    cache_dir: str | Path | None = None,
    checkpoint_dir: str | Path | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    from .market_data import fetch_history_for_universe as _fetch_history_for_universe

    return _fetch_history_for_universe(
        universe_df,
        as_of_date,
        cn_data_source=cn_data_source,
        cn_data_source_fallbacks=cn_data_source_fallbacks,
        us_data_source=us_data_source,
        cache_dir=cache_dir,
        checkpoint_dir=checkpoint_dir,
    )


def build_features_table(
    universe_df: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    as_of_date: str,
) -> pd.DataFrame:
    from .indicators import build_features_table as _build_features_table

    return _build_features_table(universe_df, histories, as_of_date)


def apply_hard_filters(
    features_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from .filters import apply_hard_filters as _apply_hard_filters

    return _apply_hard_filters(features_df, config)


def score_candidates(filtered_df: pd.DataFrame) -> pd.DataFrame:
    from .ranker import score_candidates as _score_candidates

    return _score_candidates(filtered_df)


@dataclass(slots=True)
class ScreenDebugResult:
    symbol: str
    market: str
    as_of_date: str
    universe_row: dict | None = None
    prefilter_drop_reason: str | None = None
    history_rows: int = 0
    history_start_date: str | None = None
    history_end_date: str | None = None
    fetch_drop_reason: str | None = None
    feature_row: dict | None = None
    hard_filter_drop_reason: str | None = None
    score_row: dict | None = None


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _normalize_market(market: str) -> str:
    return str(market or "").strip().lower()


def _select_target_rows(frame: pd.DataFrame, *, symbol: str, market: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=getattr(frame, "columns", []))

    symbols = frame["symbol"].fillna("").astype(str).str.upper()
    markets = frame["market"].fillna("").astype(str).str.lower()
    return frame.loc[(symbols == symbol) & (markets == market)].reset_index(drop=True)


def _row_dict(frame: pd.DataFrame) -> dict | None:
    if frame is None or frame.empty:
        return None
    return frame.iloc[0].to_dict()


def _history_bounds(history_df: pd.DataFrame) -> tuple[str | None, str | None]:
    if history_df is None or history_df.empty or "Date" not in history_df.columns:
        return None, None
    dates = history_df["Date"].astype(str)
    return str(dates.min()), str(dates.max())


def debug_screen_symbol(
    config: ScreenRunConfig,
    *,
    symbol: str,
    market: str,
) -> ScreenDebugResult:
    normalized_symbol = _normalize_symbol(symbol)
    normalized_market = _normalize_market(market)
    cache_root = Path(config.output_dir) / ".cache"
    result = ScreenDebugResult(
        symbol=normalized_symbol,
        market=normalized_market,
        as_of_date=config.as_of_date,
    )

    universe_df = load_universe(config, cache_dir=cache_root)
    target_universe_df = _select_target_rows(
        universe_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    result.universe_row = _row_dict(target_universe_df)
    if result.universe_row is None:
        return result

    prefiltered_df, prefilter_dropped_df = apply_universe_prefilters(universe_df, config)
    target_prefilter_drop_df = _select_target_rows(
        prefilter_dropped_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    target_prefilter_drop = _row_dict(target_prefilter_drop_df)
    if target_prefilter_drop is not None:
        result.prefilter_drop_reason = str(target_prefilter_drop.get("drop_reason") or "")
        return result

    target_prefiltered_df = _select_target_rows(
        prefiltered_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    histories, fetch_failures = fetch_history_for_universe(
        target_prefiltered_df,
        config.as_of_date,
        cn_data_source=config.cn_data_source,
        cn_data_source_fallbacks=config.cn_data_source_fallbacks,
        us_data_source=config.us_data_source,
        cache_dir=cache_root,
        checkpoint_dir=cache_root / "checkpoints",
    )
    target_fetch_failure_df = _select_target_rows(
        fetch_failures,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    target_fetch_failure = _row_dict(target_fetch_failure_df)
    if target_fetch_failure is not None:
        result.fetch_drop_reason = str(target_fetch_failure.get("drop_reason") or "fetch_failed")
        return result

    history_df = histories.get(str(target_prefiltered_df.iloc[0]["symbol"]))
    if history_df is None or history_df.empty:
        result.fetch_drop_reason = "fetch_failed"
        return result

    result.history_rows = len(history_df.index)
    result.history_start_date, result.history_end_date = _history_bounds(history_df)

    features_df = build_features_table(target_prefiltered_df, histories, config.as_of_date)
    target_feature_df = _select_target_rows(
        features_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    result.feature_row = _row_dict(target_feature_df)
    if result.feature_row is None:
        return result

    kept_df, dropped_df = apply_hard_filters(features_df, config)
    target_hard_drop_df = _select_target_rows(
        dropped_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    target_hard_drop = _row_dict(target_hard_drop_df)
    if target_hard_drop is not None:
        result.hard_filter_drop_reason = str(target_hard_drop.get("drop_reason") or "")
        return result

    ranked_df = score_candidates(kept_df)
    target_rank_df = _select_target_rows(
        ranked_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    result.score_row = _row_dict(target_rank_df)
    return result
