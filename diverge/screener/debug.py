from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .schema import ScreenRunConfig
from .stages import evaluate_screen_stage, prepare_universe_stage


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


def _select_target_rows(
    frame: pd.DataFrame, *, symbol: str, market: str
) -> pd.DataFrame:
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
    cache_root = Path(config.cache_dir)
    history_root = Path(config.history_dir)
    result = ScreenDebugResult(
        symbol=normalized_symbol,
        market=normalized_market,
        as_of_date=config.as_of_date,
    )

    universe_stage = prepare_universe_stage(config, cache_root)
    target_universe_df = _select_target_rows(
        universe_stage.universe_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    result.universe_row = _row_dict(target_universe_df)
    if result.universe_row is None:
        return result

    target_prefilter_drop_df = _select_target_rows(
        universe_stage.prefiltered_out_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    target_prefilter_drop = _row_dict(target_prefilter_drop_df)
    if target_prefilter_drop is not None:
        result.prefilter_drop_reason = str(
            target_prefilter_drop.get("drop_reason") or ""
        )
        return result

    target_prefiltered_df = _select_target_rows(
        universe_stage.prefiltered_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    if target_prefiltered_df.empty:
        return result

    evaluation_stage = evaluate_screen_stage(
        config,
        source_universe_df=target_prefiltered_df,
        fetch_universe_df=target_prefiltered_df,
        cache_root=cache_root,
        history_root=history_root,
    )
    target_fetch_failure_df = _select_target_rows(
        evaluation_stage.fetch_failures,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    target_fetch_failure = _row_dict(target_fetch_failure_df)
    if target_fetch_failure is not None:
        result.fetch_drop_reason = str(
            target_fetch_failure.get("drop_reason") or "fetch_failed"
        )
        return result

    history_df = evaluation_stage.histories.get(
        str(target_prefiltered_df.iloc[0]["symbol"])
    )
    if history_df is None or history_df.empty:
        result.fetch_drop_reason = "fetch_failed"
        return result

    result.history_rows = len(history_df.index)
    result.history_start_date, result.history_end_date = _history_bounds(history_df)

    target_feature_df = _select_target_rows(
        evaluation_stage.features_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    result.feature_row = _row_dict(target_feature_df)
    if result.feature_row is None:
        return result

    target_hard_drop_df = _select_target_rows(
        evaluation_stage.dropped_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    target_hard_drop = _row_dict(target_hard_drop_df)
    if target_hard_drop is not None:
        result.hard_filter_drop_reason = str(target_hard_drop.get("drop_reason") or "")
        return result

    target_rank_df = _select_target_rows(
        evaluation_stage.ranked_df,
        symbol=normalized_symbol,
        market=normalized_market,
    )
    result.score_row = _row_dict(target_rank_df)
    return result
