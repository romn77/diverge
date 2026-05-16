from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from diverge.opportunity.radar import list_radar_runs, load_radar_artifact
from web.backend import app_config, auth, opportunity_models


def _assert_run_access(run_meta: dict[str, Any], current_user=None) -> None:
    if not auth.auth_enabled() or current_user is None:
        return
    run_tenant_id = run_meta.get("tenant_id")
    user_tenant_id = getattr(current_user, "tenant_id", None)
    if run_tenant_id is not None and run_tenant_id != user_tenant_id:
        raise HTTPException(
            status_code=404,
            detail=f"Opportunity run '{run_meta.get('run_id')}' not found",
        )


def list_runs(current_user=None) -> list[dict[str, Any]]:
    tenant_id = getattr(current_user, "tenant_id", None)
    runs = list_radar_runs(project_root=app_config.PROJECT_ROOT)
    if tenant_id is not None:
        runs = [run for run in runs if run.get("tenant_id") in {None, tenant_id}]
    return runs


def get_run(run_id: str, current_user=None) -> dict[str, Any]:
    try:
        run_meta = load_radar_artifact(
            run_id, "run_meta.json", project_root=app_config.PROJECT_ROOT
        )
        _assert_run_access(run_meta, current_user)
        return run_meta
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"Opportunity run '{run_id}' not found"
        ) from exc


def get_artifact(run_id: str, artifact_name: str, current_user=None) -> Any:
    filename_by_name = {
        "market_pulse": "market_pulse.json",
        "themes": "theme_radar.json",
        "events": "opportunity_events.ndjson",
        "candidates": "candidate_pool.json",
        "watchlist": "watchlist_snapshot.json",
        "backtest": "backtest_snapshot.json",
    }
    filename = filename_by_name.get(artifact_name, artifact_name)
    try:
        run_meta = load_radar_artifact(
            run_id, "run_meta.json", project_root=app_config.PROJECT_ROOT
        )
        _assert_run_access(run_meta, current_user)
        return load_radar_artifact(
            run_id, filename, project_root=app_config.PROJECT_ROOT
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"Opportunity artifact '{artifact_name}' not found"
        ) from exc


def _watchlist_file(owner_user_id: str | None) -> Path:
    owner = owner_user_id or "workspace"
    return app_config.OPPORTUNITY_TASKS_DIR / "watchlist" / f"{owner}.json"


def list_watchlist(current_user=None) -> list[dict[str, Any]]:
    if auth.auth_enabled() and current_user is not None:
        try:
            with auth.db_session() as db:
                rows = (
                    db.query(opportunity_models.WatchlistItem)
                    .filter(
                        opportunity_models.WatchlistItem.owner_user_id
                        == current_user.id
                    )
                    .order_by(opportunity_models.WatchlistItem.updated_at.desc())
                    .all()
                )
                return [
                    {
                        "id": row.id,
                        "symbol": row.symbol,
                        "market": row.market,
                        "name": row.name,
                        "theme_id": row.theme_id,
                        "status": row.status,
                        "reason": row.reason,
                        "source_run_id": row.source_run_id,
                        "metadata": row.metadata_json or {},
                        "updated_at": row.updated_at.isoformat(),
                    }
                    for row in rows
                ]
        except Exception as exc:
            raise auth.AuthError(str(exc)) from exc
    path = _watchlist_file(getattr(current_user, "id", None))
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_watchlist_item(payload: dict[str, Any], current_user=None) -> dict[str, Any]:
    owner_user_id = getattr(current_user, "id", None)
    tenant_id = getattr(current_user, "tenant_id", None)
    if auth.auth_enabled() and current_user is not None:
        with auth.db_session() as db:
            existing = (
                db.query(opportunity_models.WatchlistItem)
                .filter(
                    opportunity_models.WatchlistItem.owner_user_id == current_user.id,
                    opportunity_models.WatchlistItem.symbol == payload["symbol"],
                )
                .one_or_none()
            )
            row = existing or opportunity_models.WatchlistItem(
                id=uuid.uuid4().hex, owner_user_id=current_user.id
            )
            if existing is None:
                db.add(row)
            row.tenant_id = tenant_id
            row.symbol = payload["symbol"]
            row.market = payload.get("market") or "cn"
            row.name = payload.get("name")
            row.theme_id = payload.get("theme_id")
            row.status = payload.get("status") or "NEW"
            row.reason = payload.get("reason")
            row.source_run_id = payload.get("source_run_id")
            row.metadata_json = payload.get("metadata") or {}
            db.flush()
            return {"id": row.id, "symbol": row.symbol, "status": row.status}
    path = _watchlist_file(owner_user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    rows = [row for row in rows if row.get("symbol") != payload["symbol"]]
    payload = dict(payload)
    payload["id"] = payload.get("id") or uuid.uuid4().hex
    rows.insert(0, payload)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "id": payload["id"],
        "symbol": payload["symbol"],
        "status": payload.get("status"),
    }


def delete_watchlist_item(symbol: str, current_user=None) -> dict[str, Any]:
    owner_user_id = getattr(current_user, "id", None)
    if auth.auth_enabled() and current_user is not None:
        with auth.db_session() as db:
            row = (
                db.query(opportunity_models.WatchlistItem)
                .filter(
                    opportunity_models.WatchlistItem.owner_user_id == current_user.id,
                    opportunity_models.WatchlistItem.symbol == symbol,
                )
                .one_or_none()
            )
            if row is not None:
                db.delete(row)
        return {"deleted": True, "symbol": symbol}
    path = _watchlist_file(owner_user_id)
    if path.is_file():
        rows = [
            row
            for row in json.loads(path.read_text(encoding="utf-8"))
            if row.get("symbol") != symbol
        ]
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {"deleted": True, "symbol": symbol}


def build_candidate_opportunity_context(
    symbol: str, run_id: str | None, current_user=None
) -> dict[str, Any]:
    context: dict[str, Any] = {"symbol": symbol, "source": "opportunity_radar"}
    if not run_id:
        return context
    candidate_pool = get_artifact(run_id, "candidates", current_user)
    backtest_snapshot = get_artifact(run_id, "backtest", current_user)
    candidates = (
        candidate_pool.get("candidates") if isinstance(candidate_pool, dict) else []
    )
    match = next(
        (row for row in candidates or [] if str(row.get("symbol")) == symbol), None
    )
    if isinstance(match, dict):
        context.update(
            {
                "trigger": match.get("reason") or "Opportunity Radar candidate",
                "theme_id": match.get("theme_id"),
                "theme_name": match.get("theme_name"),
                "candidate_type": match.get("candidate_type"),
                "source_run_id": run_id,
                "backtest_summary": match.get("backtest_summary") or backtest_snapshot,
                "risk_flags": match.get("risk_flags") or [],
            }
        )
    else:
        context.update({"source_run_id": run_id, "backtest_summary": backtest_snapshot})
    return context
