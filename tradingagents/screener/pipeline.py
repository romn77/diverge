from __future__ import annotations

import time
from typing import Callable

import pandas as pd

from .filters import apply_hard_filters
from .indicators import build_features_table
from .market_data import fetch_history_for_universe
from .ranker import score_candidates
from .schema import ScreenRunConfig, ScreenRunResult
from .storage import prepare_run_dir, write_run_artifacts
from .universe import load_universe


def _emit(progress_callback: Callable | None, stage: str, current: int, total: int, symbol: str | None = None) -> None:
    if progress_callback is not None:
        progress_callback(stage, current, total, symbol)


def run_screen(
    config: ScreenRunConfig,
    progress_callback: Callable | None = None,
) -> ScreenRunResult:
    started_at = time.perf_counter()

    _emit(progress_callback, "universe", 0, 1)
    universe_df = load_universe(config)
    _emit(progress_callback, "universe", 1, 1)

    histories, fetch_failures = fetch_history_for_universe(
        universe_df,
        config.as_of_date,
        progress_callback=progress_callback,
    )

    _emit(progress_callback, "features", 0, 1)
    features_df = build_features_table(universe_df, histories, config.as_of_date)
    _emit(progress_callback, "features", 1, 1)

    _emit(progress_callback, "filters", 0, 1)
    kept_df, dropped_df = apply_hard_filters(features_df, config)
    combined_filtered_out = pd.concat([fetch_failures, dropped_df], ignore_index=True, sort=False)
    _emit(progress_callback, "filters", 1, 1)

    _emit(progress_callback, "ranking", 0, 1)
    ranked_df = score_candidates(kept_df) if not kept_df.empty else kept_df.copy()
    candidates_df = ranked_df.head(config.top_k).reset_index(drop=True)
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
