from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from .schema import ScreenRunConfig, ScreenRunResult


def _json_ready_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    safe_df = df.where(pd.notna(df), None)
    return safe_df.to_dict(orient="records")


def prepare_run_dir(base_output_dir: str, as_of_date: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for candidate_name in (timestamp, f"{timestamp}_{uuid.uuid4().hex[:8]}"):
        run_dir = output_dir / candidate_name
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            continue
    run_dir = output_dir / f"{timestamp}_{uuid.uuid4().hex}"
    run_dir.mkdir()
    return run_dir


def write_run_artifacts(
    run_dir: Path,
    config: ScreenRunConfig,
    universe_df: pd.DataFrame,
    features_df: pd.DataFrame,
    filtered_out_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    elapsed_seconds: float,
    pruned_symbols_df: pd.DataFrame | None = None,
) -> ScreenRunResult:
    universe_path = run_dir / "universe.csv"
    features_path = run_dir / "features.csv"
    filtered_out_path = run_dir / "filtered_out.csv"
    pruned_symbols_path = run_dir / "pruned_symbols.csv"
    candidates_path = run_dir / "candidates.csv"
    llm_pool_path = run_dir / "llm_pool.json"
    run_meta_path = run_dir / "run_meta.json"

    universe_df.to_csv(universe_path, index=False)
    features_df.to_csv(features_path, index=False)
    filtered_out_df.to_csv(filtered_out_path, index=False)
    resolved_pruned_symbols_df = (
        pruned_symbols_df if pruned_symbols_df is not None else pd.DataFrame()
    )
    resolved_pruned_symbols_df.to_csv(pruned_symbols_path, index=False)
    candidates_df.to_csv(candidates_path, index=False)
    llm_pool_path.write_text(
        json.dumps(_json_ready_records(candidates_df), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    universe_count_by_market = (
        {
            str(key): int(value)
            for key, value in universe_df["market"]
            .value_counts()
            .sort_index()
            .to_dict()
            .items()
        }
        if not universe_df.empty
        else {}
    )
    filtered_count_by_reason = (
        {
            str(key): int(value)
            for key, value in filtered_out_df["drop_reason"]
            .value_counts()
            .sort_index()
            .to_dict()
            .items()
        }
        if not filtered_out_df.empty and "drop_reason" in filtered_out_df.columns
        else {}
    )
    fetch_failed_count = int(filtered_count_by_reason.get("fetch_failed", 0))
    candidate_count = int(len(candidates_df))

    artifact_paths = {
        "run_meta": str(run_meta_path),
        "universe": str(universe_path),
        "features": str(features_path),
        "filtered_out": str(filtered_out_path),
        "pruned_symbols": str(pruned_symbols_path),
        "candidates": str(candidates_path),
        "llm_pool": str(llm_pool_path),
    }

    run_meta = {
        "run_timestamp": run_dir.name,
        "as_of_date": config.as_of_date,
        "config": asdict(config),
        "universe_count_by_market": universe_count_by_market,
        "fetch_failed_count": fetch_failed_count,
        "filtered_count_by_reason": filtered_count_by_reason,
        "pruned_symbol_count": int(len(resolved_pruned_symbols_df)),
        "candidate_count": candidate_count,
        "elapsed_seconds": elapsed_seconds,
        "artifact_paths": artifact_paths,
    }
    run_meta_path.write_text(
        json.dumps(run_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    preview_columns = [
        "symbol",
        "market",
        "global_rank",
        "total_score",
        "breakout_type",
        "breakout_with_volume",
    ]
    available_preview_columns = [
        column for column in preview_columns if column in candidates_df.columns
    ]
    candidate_preview = (
        _json_ready_records(candidates_df.loc[:, available_preview_columns].head(10))
        if not candidates_df.empty
        else []
    )
    return ScreenRunResult(
        run_dir=run_dir,
        universe_count_by_market=universe_count_by_market,
        fetch_failed_count=fetch_failed_count,
        filtered_count_by_reason=filtered_count_by_reason,
        candidate_count=candidate_count,
        candidate_preview=candidate_preview,
    )
