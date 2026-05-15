from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pandas as pd

from .schema import ScreenRunConfig, ScreenRunResult
from .strategy_pipeline import run_strategy_screen
from .stages import (
    evaluate_screen_stage,
    prepare_universe_stage,
    prune_universe_by_history_coverage,
)
from .storage import prepare_run_dir, write_run_artifacts


def _filter_selected_breakouts(
    ranked_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> pd.DataFrame:
    if ranked_df.empty or not config.breakout_types:
        return ranked_df
    selected_breakouts = set(config.breakout_types)
    return ranked_df.loc[
        ranked_df["breakout_hit"].eq(True)
        & ranked_df["breakout_type"].isin(selected_breakouts)
    ]


def _select_candidates(
    ranked_df: pd.DataFrame, config: ScreenRunConfig
) -> pd.DataFrame:
    candidate_pool = _filter_selected_breakouts(ranked_df, config)
    if candidate_pool.empty:
        return candidate_pool.copy()

    if set(config.markets) != {"cn", "us"}:
        return candidate_pool.head(config.top_k).reset_index(drop=True)

    per_market_floor = config.top_k // 2
    if per_market_floor <= 0:
        return candidate_pool.head(config.top_k).reset_index(drop=True)

    selected_indices: list[int] = []
    for market in ("cn", "us"):
        market_rows = candidate_pool[candidate_pool["market"] == market].head(
            per_market_floor
        )
        selected_indices.extend(market_rows.index.tolist())

    remaining_slots = max(config.top_k - len(selected_indices), 0)
    if remaining_slots > 0:
        backfill = candidate_pool.drop(index=selected_indices, errors="ignore").head(
            remaining_slots
        )
        selected_indices.extend(backfill.index.tolist())

    if not selected_indices:
        return candidate_pool.head(config.top_k).reset_index(drop=True)

    return (
        candidate_pool.loc[selected_indices]
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
    if getattr(config, "mode", "preset") == "strategy":
        return run_strategy_screen(config)
    started_at = time.perf_counter()
    cache_root = Path(config.cache_dir)
    history_root = Path(config.history_dir)
    universe_stage = prepare_universe_stage(
        config,
        cache_root,
        progress_callback=progress_callback,
    )
    fetch_universe_df = universe_stage.prefiltered_df
    pruned_history_df = pd.DataFrame()
    if config.history_cache_policy == "cache_only":
        history_prune = prune_universe_by_history_coverage(
            universe_stage.prefiltered_df,
            config,
            history_root,
        )
        fetch_universe_df = history_prune.kept_df
        pruned_history_df = history_prune.pruned_df

    evaluation_stage = evaluate_screen_stage(
        config,
        source_universe_df=universe_stage.universe_df,
        fetch_universe_df=fetch_universe_df,
        cache_root=cache_root,
        history_root=history_root,
        progress_callback=progress_callback,
    )
    combined_filtered_out = pd.concat(
        [
            universe_stage.prefiltered_out_df,
            pruned_history_df,
            evaluation_stage.fetch_failures,
            evaluation_stage.dropped_df,
        ],
        ignore_index=True,
        sort=False,
    )
    candidates_df = _select_candidates(evaluation_stage.ranked_df, config)

    _emit(progress_callback, "export", 0, 1)
    run_dir = prepare_run_dir(config.output_dir, config.as_of_date)
    result = write_run_artifacts(
        run_dir=run_dir,
        config=config,
        universe_df=universe_stage.universe_df,
        features_df=evaluation_stage.features_df,
        filtered_out_df=combined_filtered_out,
        candidates_df=candidates_df,
        elapsed_seconds=round(time.perf_counter() - started_at, 4),
        pruned_symbols_df=pruned_history_df,
    )
    _emit(progress_callback, "export", 1, 1)

    return result
