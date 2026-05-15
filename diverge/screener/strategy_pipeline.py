from __future__ import annotations

import json
import time
from dataclasses import asdict

import pandas as pd

from diverge.screener.dsl import evaluate_condition_tree
from diverge.screener.factor_snapshot import (
    load_factor_snapshot,
    normalize_factor_snapshot,
)
from diverge.screener.scoring import score_weighted_components
from diverge.screener.signal_builder import build_signal_events
from diverge.screener.storage import prepare_run_dir
from diverge.screener.strategy_config import load_strategy_config, parse_strategy_config
from diverge.opportunity.storage import write_json, write_ndjson, write_table
from diverge.screener.schema import ScreenRunResult


def _candidate_type(row: pd.Series, config) -> str:
    candidate_types = (
        (config.output.get("candidate_types") or {})
        if isinstance(config.output, dict)
        else {}
    )
    row_frame = pd.DataFrame([row.to_dict()])
    for name, condition in candidate_types.items():
        try:
            if bool(evaluate_condition_tree(row_frame, condition).iloc[0]):
                return str(name)
        except Exception:
            continue
    return "watch"


def run_strategy_screen(config) -> ScreenRunResult:
    started = time.perf_counter()
    strategy = (
        parse_strategy_config(config.strategy_config)
        if config.strategy_config
        else load_strategy_config(config.strategy_id or "theme_capital_breakout_v1")
    )
    if config.factor_snapshot_path:
        factor_df = load_factor_snapshot(config.factor_snapshot_path)
    else:
        raise ValueError("factor_snapshot_path is required for strategy screener mode")
    factor_df = normalize_factor_snapshot(factor_df, trade_date=config.as_of_date)
    mask = evaluate_condition_tree(factor_df, strategy.filters).fillna(False)
    filtered = factor_df.loc[mask].copy()
    scored = score_weighted_components(filtered, strategy.score_components)
    if scored.empty:
        candidates = scored.copy()
    else:
        candidates = scored.sort_values(
            ["score", "symbol"], ascending=[False, True]
        ).reset_index(drop=True)
        candidates["rank"] = candidates.index + 1
        candidates["global_rank"] = candidates["rank"]
        candidates["strategy_id"] = strategy.strategy_id
        candidates["passed_filters"] = True
        candidates["candidate_type"] = candidates.apply(
            lambda row: _candidate_type(row, strategy), axis=1
        )
        candidates["matched_rules"] = json.dumps(
            strategy.filters, ensure_ascii=False, sort_keys=True
        )
        candidates["reason"] = (
            "Matched configured strategy filters and ranked by weighted factor score."
        )
        top_k = int((strategy.output or {}).get("top_k") or config.top_k)
        candidates = candidates.head(top_k).copy()
    run_dir = prepare_run_dir(config.output_dir, config.as_of_date)
    write_table(run_dir / "factor_snapshot.parquet", factor_df)
    write_table(run_dir / "screener_results.parquet", candidates)
    candidates.to_csv(run_dir / "candidates.csv", index=False)
    write_json(
        run_dir / "llm_pool.json",
        candidates.where(pd.notna(candidates), None).to_dict(orient="records"),
    )
    write_json(
        run_dir / "screener_explain.json",
        {
            "strategy_id": strategy.strategy_id,
            "filters": strategy.filters,
            "score_components": [
                asdict(component) for component in strategy.score_components
            ],
        },
    )
    signal_events = build_signal_events(
        candidates, strategy_id=strategy.strategy_id, trade_date=config.as_of_date
    )
    write_ndjson(run_dir / "signal_events.ndjson", signal_events)
    write_json(run_dir / "config_snapshot.json", strategy.raw)
    run_meta = {
        "run_timestamp": run_dir.name,
        "as_of_date": config.as_of_date,
        "mode": "strategy",
        "strategy_id": strategy.strategy_id,
        "markets": config.markets,
        "candidate_count": int(len(candidates)),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "artifact_paths": {
            "run_meta": str(run_dir / "run_meta.json"),
            "candidates": str(run_dir / "candidates.csv"),
            "llm_pool": str(run_dir / "llm_pool.json"),
            "factor_snapshot": str(run_dir / "factor_snapshot.parquet"),
            "screener_results": str(run_dir / "screener_results.parquet"),
            "screener_explain": str(run_dir / "screener_explain.json"),
            "signal_events": str(run_dir / "signal_events.ndjson"),
            "config_snapshot": str(run_dir / "config_snapshot.json"),
        },
        "filtered_count_by_reason": {},
        "universe_count_by_market": {
            market: int(count)
            for market, count in factor_df["market"].value_counts().to_dict().items()
        },
        "fetch_failed_count": 0,
        "config": asdict(config),
    }
    write_json(run_dir / "run_meta.json", run_meta)
    return ScreenRunResult(
        run_dir=run_dir,
        universe_count_by_market=run_meta["universe_count_by_market"],
        candidate_count=int(len(candidates)),
        candidate_preview=candidates.head(10)
        .where(pd.notna(candidates), None)
        .to_dict(orient="records"),
    )
