from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pandas as pd

from .filters import apply_hard_filters
from .indicators import build_features_table
from .market_data import fetch_history_for_universe
from .ranker import score_candidates
from .schema import ScreenRunConfig, ScreenRunResult
from .storage import prepare_run_dir, write_run_artifacts
from .universe import load_universe
from .universe_prefilter import apply_universe_prefilters


def _select_candidates(ranked_df: pd.DataFrame, config: ScreenRunConfig) -> pd.DataFrame:
    if ranked_df.empty:
        return ranked_df.copy()

    if set(config.markets) != {"cn", "us"}:
        return ranked_df.head(config.top_k).reset_index(drop=True)

    per_market_floor = config.top_k // 2
    if per_market_floor <= 0:
        return ranked_df.head(config.top_k).reset_index(drop=True)

    selected_indices: list[int] = []
    for market in ("cn", "us"):
        market_rows = ranked_df[ranked_df["market"] == market].head(per_market_floor)
        selected_indices.extend(market_rows.index.tolist())

    remaining_slots = max(config.top_k - len(selected_indices), 0)
    if remaining_slots > 0:
        backfill = ranked_df.drop(index=selected_indices, errors="ignore").head(remaining_slots)
        selected_indices.extend(backfill.index.tolist())

    if not selected_indices:
        return ranked_df.head(config.top_k).reset_index(drop=True)

    return (
        ranked_df.loc[selected_indices]
        .sort_values(["global_rank", "symbol"], ascending=[True, True])
        .head(config.top_k)
        .reset_index(drop=True)
    )


def _emit(
    progress_callback: Callable[..., None] | None,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    *,
    status: str | None = None,
    detail: str | None = None,
) -> None:
    if progress_callback is not None:
        progress_callback(
            stage,
            current,
            total,
            symbol,
            status=status,
            detail=detail,
        )


def run_screen(
    config: ScreenRunConfig,
    progress_callback: Callable[..., None] | None = None,
) -> ScreenRunResult:
    started_at = time.perf_counter()
    cache_root = Path(config.output_dir) / ".cache"

    _emit(progress_callback, "universe", 0, 1)
    universe_df = load_universe(config, cache_dir=cache_root)
    filtered_universe_df, prefiltered_out_df = apply_universe_prefilters(universe_df, config)
    _emit(progress_callback, "universe", 1, 1)

    histories, fetch_failures = fetch_history_for_universe(
        filtered_universe_df,
        config.as_of_date,
        cn_data_source=config.cn_data_source,
        cn_data_source_fallbacks=config.cn_data_source_fallbacks,
        progress_callback=progress_callback,
        cache_dir=cache_root,
        checkpoint_dir=cache_root / "checkpoints",
    )

    _emit(progress_callback, "features", 0, 1)
    features_df = build_features_table(universe_df, histories, config.as_of_date)
    _emit(progress_callback, "features", 1, 1)

    _emit(progress_callback, "filters", 0, 1)
    kept_df, dropped_df = apply_hard_filters(features_df, config)
    combined_filtered_out = pd.concat(
        [prefiltered_out_df, fetch_failures, dropped_df],
        ignore_index=True,
        sort=False,
    )
    _emit(progress_callback, "filters", 1, 1)

    _emit(progress_callback, "ranking", 0, 1)
    ranked_df = score_candidates(kept_df) if not kept_df.empty else kept_df.copy()
    candidates_df = _select_candidates(ranked_df, config)
    _emit(progress_callback, "ranking", 1, 1)

    _emit(progress_callback, "export", 0, 1)
    run_dir = prepare_run_dir(config.output_dir, config.as_of_date)
    result = write_run_artifacts(
        run_dir=run_dir,
        config=config,
        universe_df=universe_df,
        features_df=features_df,
        filtered_out_df=combined_filtered_out,
        candidates_df=candidates_df,
        elapsed_seconds=round(time.perf_counter() - started_at, 4),
    )
    _emit(progress_callback, "export", 1, 1)

    return result
