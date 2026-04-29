from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from .filters import apply_hard_filters
from .indicators import build_features_table
from .market_data import fetch_history_for_universe
from .ranker import score_candidates
from .schema import ScreenRunConfig
from .universe import load_universe
from .universe_prefilter import apply_universe_prefilters


@dataclass(slots=True)
class UniverseStageBundle:
    universe_df: pd.DataFrame
    prefiltered_df: pd.DataFrame
    prefiltered_out_df: pd.DataFrame


@dataclass(slots=True)
class EvaluationStageBundle:
    histories: dict[str, pd.DataFrame]
    fetch_failures: pd.DataFrame
    features_df: pd.DataFrame
    kept_df: pd.DataFrame
    dropped_df: pd.DataFrame
    ranked_df: pd.DataFrame


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


def prepare_universe_stage(
    config: ScreenRunConfig,
    cache_root: Path,
    *,
    progress_callback: Callable[..., None] | None = None,
) -> UniverseStageBundle:
    _emit(progress_callback, "universe", 0, 1)
    universe_df = load_universe(config, cache_dir=cache_root)
    prefiltered_df, prefiltered_out_df = apply_universe_prefilters(universe_df, config)
    _emit(progress_callback, "universe", 1, 1)
    return UniverseStageBundle(
        universe_df=universe_df,
        prefiltered_df=prefiltered_df,
        prefiltered_out_df=prefiltered_out_df,
    )


def evaluate_screen_stage(
    config: ScreenRunConfig,
    *,
    source_universe_df: pd.DataFrame,
    fetch_universe_df: pd.DataFrame,
    cache_root: Path,
    history_root: Path,
    progress_callback: Callable[..., None] | None = None,
) -> EvaluationStageBundle:
    histories, fetch_failures = fetch_history_for_universe(
        fetch_universe_df,
        config.as_of_date,
        cn_data_source=config.cn_data_source,
        cn_data_source_fallbacks=config.cn_data_source_fallbacks,
        us_data_source=config.us_data_source,
        us_data_source_fallbacks=config.us_data_source_fallbacks,
        progress_callback=progress_callback,
        history_dir=history_root,
        cache_dir=cache_root,
        checkpoint_dir=cache_root / "checkpoints",
        cache_only=config.history_cache_policy == "cache_only",
    )

    _emit(progress_callback, "features", 0, 1)
    features_df = build_features_table(source_universe_df, histories, config.as_of_date)
    if config.include_fundamentals:
        from .fundamentals import enrich_features_with_fundamentals

        features_df = enrich_features_with_fundamentals(features_df, config)
    _emit(progress_callback, "features", 1, 1)

    _emit(progress_callback, "filters", 0, 1)
    kept_df, dropped_df = apply_hard_filters(features_df, config)
    _emit(progress_callback, "filters", 1, 1)

    _emit(progress_callback, "ranking", 0, 1)
    ranked_df = score_candidates(kept_df, config) if not kept_df.empty else kept_df.copy()
    _emit(progress_callback, "ranking", 1, 1)

    return EvaluationStageBundle(
        histories=histories,
        fetch_failures=fetch_failures,
        features_df=features_df,
        kept_df=kept_df,
        dropped_df=dropped_df,
        ranked_df=ranked_df,
    )
