from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from diverge.backtest.event_study import run_backtest_snapshot, summarize_by_horizon
from diverge.backtest.storage import write_backtest_artifacts
from diverge.opportunity.candidate_pool import (
    build_candidate_pool,
    opportunity_events_from_candidates,
)
from diverge.opportunity.config import load_cost_models, load_strategy_config
from diverge.opportunity.quality import quality_flag
from diverge.opportunity.storage import (
    artifact_manifest,
    opportunity_runs_dir,
    prepare_run_dir,
    read_ndjson,
    read_table,
    utc_timestamp,
    write_json,
    write_ndjson,
    write_table,
)
from diverge.opportunity.theme_builder import build_market_pulse, build_theme_radar
from diverge.opportunity.watchlist_monitor import build_watchlist_snapshot
from diverge.screener.dsl import evaluate_condition_tree
from diverge.screener.factor_snapshot import (
    load_factor_snapshot,
    normalize_factor_snapshot,
)
from diverge.screener.scoring import score_weighted_components
from diverge.screener.signal_builder import build_signal_events
from diverge.screener.strategy_config import parse_strategy_config


class OpportunityDataNotReady(RuntimeError):
    pass


def _hash_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _default_factor_snapshot_path(project_root: Path | None = None) -> Path | None:
    root = ((project_root or Path.cwd()) / "data" / "screener" / "runs").resolve()
    if not root.is_dir():
        return None
    for name in sorted(root.iterdir(), reverse=True):
        for filename in ("factor_snapshot.parquet", "features.csv", "candidates.csv"):
            candidate = name / filename
            if candidate.is_file():
                return candidate
    return None


def _load_factor_frame(
    payload: dict[str, Any], trade_date: str, *, project_root: Path | None = None
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    flags: list[dict[str, Any]] = []
    raw_path = payload.get("factor_snapshot_path") or payload.get("features_path")
    path = (
        Path(str(raw_path)).expanduser()
        if raw_path
        else _default_factor_snapshot_path(project_root)
    )
    if path is not None and not path.is_absolute() and project_root is not None:
        path = (project_root / path).resolve()
    if path is None or not path.is_file():
        flags.append(
            quality_flag(
                "required_factor_snapshot_missing",
                severity="error",
                source="radar",
                message="No factor snapshot or compatible screener feature artifact was found.",
            )
        )
        return pd.DataFrame(), flags
    frame = load_factor_snapshot(path)
    return normalize_factor_snapshot(frame, trade_date=trade_date), flags


def _run_strategy(
    factor_df: pd.DataFrame, strategy_payload: dict[str, Any], trade_date: str
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    strategy = parse_strategy_config(strategy_payload)
    if factor_df.empty:
        return pd.DataFrame(), []
    mask = evaluate_condition_tree(factor_df, strategy.filters).fillna(False)
    filtered = factor_df.loc[mask].copy()
    scored = score_weighted_components(filtered, strategy.score_components)
    if scored.empty:
        return scored, []
    scored = scored.sort_values(
        ["score", "symbol"], ascending=[False, True]
    ).reset_index(drop=True)
    scored["rank"] = scored.index + 1
    scored["global_rank"] = scored["rank"]
    scored["strategy_id"] = strategy.strategy_id
    scored["passed_filters"] = True
    scored["matched_rules"] = json.dumps(
        strategy.filters, ensure_ascii=False, sort_keys=True
    )
    scored["candidate_type"] = "watch"
    candidate_types = (strategy.output or {}).get("candidate_types") or {}
    for candidate_type, condition in candidate_types.items():
        try:
            matched = evaluate_condition_tree(scored, condition).fillna(False)
            scored.loc[matched, "candidate_type"] = str(candidate_type)
        except Exception:
            continue
    scored["reason"] = (
        "Matched configured strategy filters and ranked by weighted factor score."
    )
    top_k = int((strategy.output or {}).get("top_k") or 50)
    return scored.head(top_k).copy(), build_signal_events(
        scored.head(top_k), strategy_id=strategy.strategy_id, trade_date=trade_date
    )


def _load_price_history(
    payload: dict[str, Any], *, project_root: Path | None = None
) -> pd.DataFrame:
    raw_path = payload.get("price_history_path")
    if not raw_path:
        return pd.DataFrame()
    path = Path(str(raw_path)).expanduser()
    if not path.is_absolute() and project_root is not None:
        path = (project_root / path).resolve()
    if not path.is_file():
        return pd.DataFrame()
    return read_table(path)


def plan_radar_run_id(
    payload: dict[str, Any] | None = None,
) -> tuple[str, str, str, list[str], str]:
    request = dict(payload or {})
    trade_date = str(
        request.get("trade_date")
        or request.get("as_of_date")
        or pd.Timestamp.utcnow().date().isoformat()
    )
    market = str(request.get("market") or "cn").strip().lower()
    strategy_ids = [
        str(item)
        for item in request.get("strategy_ids") or ["theme_capital_breakout_v1"]
    ]
    config_hash = _hash_payload(
        {
            "tenant_id": request.get("tenant_id"),
            "trade_date": trade_date,
            "market": market,
            "strategy_ids": strategy_ids,
            "factor_snapshot_path": request.get("factor_snapshot_path"),
        }
    )
    run_id = str(
        request.get("run_id")
        or f"radar_{market}_{trade_date.replace('-', '')}_{config_hash}"
    )
    return run_id, trade_date, market, strategy_ids, config_hash


def _run_dir_matches_tenant(run_dir: Path, tenant_id: str | None) -> bool:
    if tenant_id is None:
        return True
    meta_path = run_dir / "run_meta.json"
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return meta.get("tenant_id") in {None, tenant_id}


def _revision_run_dir(
    base_run_id: str,
    *,
    force: bool,
    project_root: Path | None = None,
    tenant_id: str | None = None,
) -> tuple[str, Path, int, bool]:
    base_dir = opportunity_runs_dir(project_root)
    run_dir = base_dir / base_run_id
    if not (run_dir / "run_meta.json").is_file():
        return (
            base_run_id,
            prepare_run_dir(base_run_id, project_root=project_root),
            1,
            False,
        )
    if not force and _run_dir_matches_tenant(run_dir, tenant_id):
        return base_run_id, run_dir, 1, True
    revision = 2
    while True:
        candidate_id = f"{base_run_id}_r{revision}"
        candidate_dir = base_dir / candidate_id
        if not (candidate_dir / "run_meta.json").is_file():
            return (
                candidate_id,
                prepare_run_dir(candidate_id, project_root=project_root),
                revision,
                False,
            )
        if not force and _run_dir_matches_tenant(candidate_dir, tenant_id):
            return candidate_id, candidate_dir, revision, True
        revision += 1


def run_opportunity_radar(
    payload: dict[str, Any] | None = None,
    *,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    request = dict(payload or {})
    if tenant_id is not None and not request.get("tenant_id"):
        request["tenant_id"] = tenant_id
    base_run_id, trade_date, market, strategy_ids, config_hash = plan_radar_run_id(
        request
    )
    run_id, run_dir, revision, cached = _revision_run_dir(
        base_run_id,
        force=bool(request.get("force")),
        project_root=project_root,
        tenant_id=tenant_id,
    )
    if cached:
        return {
            "run_id": run_id,
            "status": "completed",
            "cached": True,
            "run_dir": str(run_dir),
        }

    factor_df, quality_flags = _load_factor_frame(
        request, trade_date, project_root=project_root
    )
    strategy_payloads = [
        load_strategy_config(strategy_id) for strategy_id in strategy_ids
    ]
    result_frames: list[pd.DataFrame] = []
    signal_events: list[dict[str, Any]] = []
    for strategy_payload in strategy_payloads:
        results, events = _run_strategy(factor_df, strategy_payload, trade_date)
        result_frames.append(results)
        signal_events.extend(events)
    results_df = (
        pd.concat(result_frames, ignore_index=True, sort=False)
        if result_frames
        else pd.DataFrame()
    )

    backtest_snapshot: dict[str, Any] | None = None
    price_history = _load_price_history(request, project_root=project_root)
    if not price_history.empty and signal_events:
        cost_models = load_cost_models().get("models", {})
        cost_model = cost_models.get(
            str(request.get("cost_model_id") or "cn_a_share_default"), {}
        )
        backtest_snapshot = run_backtest_snapshot(
            strategy_id=strategy_ids[0],
            signal_events=signal_events,
            price_history=price_history,
            cost_model=cost_model,
            run_id=f"bt_{run_id}",
        )
        write_backtest_artifacts(run_dir, backtest_snapshot)
    else:
        backtest_snapshot = {
            "strategy_id": strategy_ids[0],
            "run_id": f"bt_{run_id}",
            "engine": "event_study",
            "status": "unavailable",
            "sample_size": 0,
            "holding_periods": {},
            "risk_notes": ["Backtest Snapshot unavailable."],
            "data_quality_notes": ["insufficient_sample"],
        }
        write_json(run_dir / "backtest_snapshot.json", backtest_snapshot)
        write_json(run_dir / "backtest_metrics.json", {})

    if not results_df.empty:
        results_df["backtest_summary"] = json.dumps(
            summarize_by_horizon(backtest_snapshot), ensure_ascii=False, sort_keys=True
        )
    candidate_pool = build_candidate_pool(
        results_df, trade_date=trade_date, market=market, strategy_ids=strategy_ids
    )
    theme_radar = build_theme_radar(results_df, trade_date=trade_date, market=market)
    for theme in theme_radar.get("themes", []):
        theme["backtest_summary"] = summarize_by_horizon(backtest_snapshot)
    market_pulse = build_market_pulse(theme_radar, trade_date=trade_date, market=market)
    if quality_flags:
        market_pulse["data_quality_notes"] = [flag["message"] for flag in quality_flags]
    opportunity_events = opportunity_events_from_candidates(
        candidate_pool, source_run_id=run_id
    )
    watchlist_snapshot = build_watchlist_snapshot(candidate_pool)

    write_table(run_dir / "factor_snapshot.parquet", factor_df)
    write_table(run_dir / "screener_results.parquet", results_df)
    if not results_df.empty:
        results_df.to_csv(run_dir / "screener_results.csv", index=False)
    write_ndjson(run_dir / "signal_events.ndjson", signal_events)
    write_json(run_dir / "market_pulse.json", market_pulse)
    write_json(run_dir / "theme_radar.json", theme_radar)
    write_json(run_dir / "candidate_pool.json", candidate_pool)
    write_json(run_dir / "watchlist_snapshot.json", watchlist_snapshot)
    write_ndjson(run_dir / "opportunity_events.ndjson", opportunity_events)
    write_json(
        run_dir / "config_snapshot.json",
        {"strategies": strategy_payloads, "request": request},
    )
    summary_lines = [
        f"# Opportunity Radar {trade_date}",
        "",
        market_pulse.get("summary") or "",
    ]
    for theme in theme_radar.get("themes", [])[:5]:
        summary_lines.append(
            f"- {theme.get('theme_name')}: hot {theme.get('hot_score')}, capital {theme.get('capital_score')}"
        )
    (run_dir / "radar_summary.md").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    run_meta = {
        "run_id": run_id,
        "run_type": "opportunity_radar",
        "status": "completed"
        if not any(flag.get("severity") == "error" for flag in quality_flags)
        else "completed_with_data_gaps",
        "trade_date": trade_date,
        "market": market,
        "tenant_id": tenant_id,
        "owner_user_id": owner_user_id,
        "strategy_ids": strategy_ids,
        "config_hash": config_hash,
        "revision": revision,
        "generated_at": utc_timestamp(),
        "candidate_count": len(candidate_pool.get("candidates") or []),
        "quality_flags": quality_flags,
        "artifact_manifest": artifact_manifest(run_dir),
    }
    write_json(run_dir / "run_meta.json", run_meta)
    return {
        "run_id": run_id,
        "status": run_meta["status"],
        "cached": False,
        "run_dir": str(run_dir),
        "candidate_count": run_meta["candidate_count"],
    }


def list_radar_runs(*, project_root: Path | None = None) -> list[dict[str, Any]]:
    root = opportunity_runs_dir(project_root)
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.iterdir(), reverse=True):
        meta = path / "run_meta.json"
        if not meta.is_file():
            continue
        try:
            rows.append(json.loads(meta.read_text(encoding="utf-8")))
        except Exception:
            continue
    return rows


def load_radar_artifact(
    run_id: str, name: str, *, project_root: Path | None = None
) -> Any:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise FileNotFoundError(run_id)
    run_dir = opportunity_runs_dir(project_root) / run_id
    path = run_dir / name
    if path.suffix == ".ndjson":
        return read_ndjson(path)
    if path.suffix == ".parquet" or path.suffix == ".csv":
        table = read_table(path)
        return table.where(pd.notna(table), None).to_dict(orient="records")
    return json.loads(path.read_text(encoding="utf-8"))
