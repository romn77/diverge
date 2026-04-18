from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pandas as pd

from .schema import ScreenRunConfig, ScreenRunResult
from .stages import evaluate_screen_stage, prepare_universe_stage
from .storage import prepare_run_dir, write_run_artifacts


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
    universe_stage = prepare_universe_stage(
        config,
        cache_root,
        progress_callback=progress_callback,
    )
    evaluation_stage = evaluate_screen_stage(
        config,
        source_universe_df=universe_stage.universe_df,
        fetch_universe_df=universe_stage.prefiltered_df,
        cache_root=cache_root,
        progress_callback=progress_callback,
    )
    combined_filtered_out = pd.concat(
        [
            universe_stage.prefiltered_out_df,
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
    )
    _emit(progress_callback, "export", 1, 1)

    return result
