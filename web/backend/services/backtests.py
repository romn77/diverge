from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from diverge.backtest.event_study import run_backtest_snapshot
from diverge.backtest.storage import write_backtest_artifacts
from diverge.opportunity.storage import read_ndjson, read_table, write_json
from web.backend import app_config
from web.backend.services import opportunities


def _run_dir(run_id: str) -> Path:
    return app_config.BACKTEST_RUNS_DIR / run_id


def _table_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    frame = read_table(path)
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def run_snapshot(payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    opportunities.require_enabled()
    signals_path = payload.get("signal_events_path")
    price_path = payload.get("price_history_path")
    if not signals_path or not price_path:
        snapshot = {
            "strategy_id": payload.get("strategy_id") or "theme_capital_breakout_v1",
            "run_id": run_id,
            "engine": "event_study",
            "status": "unavailable",
            "sample_size": 0,
            "holding_periods": {},
            "risk_notes": ["Backtest input paths are required."],
            "data_quality_notes": ["insufficient_sample"],
        }
    else:
        signals = read_ndjson(Path(signals_path))
        prices = read_table(Path(price_path))
        snapshot = run_backtest_snapshot(
            strategy_id=payload.get("strategy_id") or "theme_capital_breakout_v1",
            signal_events=signals,
            price_history=prices,
            cost_model=payload.get("cost_model"),
            horizons=tuple(payload.get("horizons") or [1, 3, 5, 10, 20]),
            run_id=run_id,
        )
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    if signals_path:
        try:
            signals_for_artifact = read_ndjson(Path(signals_path))
            if signals_for_artifact:
                from diverge.opportunity.storage import write_table

                write_table(
                    run_dir / "signal_events.parquet",
                    pd.DataFrame(signals_for_artifact),
                )
        except Exception:
            pass
    manifest = write_backtest_artifacts(run_dir, snapshot)
    write_json(
        run_dir / "run_meta.json",
        {
            "run_id": run_id,
            "strategy_id": snapshot.get("strategy_id"),
            "status": snapshot.get("status"),
            "sample_size": snapshot.get("sample_size"),
            "artifact_manifest": manifest,
        },
    )
    return snapshot


def get_snapshot(run_id: str) -> dict[str, Any]:
    path = _run_dir(run_id) / "backtest_snapshot.json"
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Backtest run '{run_id}' not found"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def get_metrics(run_id: str) -> dict[str, Any]:
    path = _run_dir(run_id) / "backtest_metrics.json"
    if not path.is_file():
        return get_snapshot(run_id).get("holding_periods") or {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_signals(run_id: str) -> list[dict[str, Any]]:
    run_dir = _run_dir(run_id)
    return _table_records(run_dir / "signal_events.parquet") or []


def get_outcomes(run_id: str) -> list[dict[str, Any]]:
    run_dir = _run_dir(run_id)
    parquet_path = run_dir / "signal_outcomes.parquet"
    csv_path = run_dir / "signal_outcomes.csv"
    return _table_records(parquet_path if parquet_path.is_file() else csv_path)


def get_parameter_scan(run_id: str) -> list[dict[str, Any]]:
    run_dir = _run_dir(run_id)
    parquet_path = run_dir / "parameter_scan.parquet"
    csv_path = run_dir / "parameter_scan.csv"
    return _table_records(parquet_path if parquet_path.is_file() else csv_path)
