from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from web.backend import access, app_config, auth, screener_runs


def relative_screener_storage_path(path: Path) -> str:
    resolved_root = app_config.SCREENER_RESULTS_DIR.resolve()
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError("Screener artifacts must stay under SCREENER_RESULTS_DIR") from exc
    return relative_path.as_posix()


def build_screener_artifact_manifest(run_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for artifact_key, filename in app_config.SCREENER_ARTIFACT_FILENAMES.items():
        artifact_path = run_dir / filename
        if artifact_path.is_file():
            manifest[artifact_key] = relative_screener_storage_path(artifact_path)
    return manifest


def resolve_screener_run_dir(run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="Screener run not found")
    run_dir = app_config.SCREENER_RESULTS_DIR / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
    return run_dir


def resolve_screener_run_dir_from_record(record: screener_runs.ScreenerRun) -> Path:
    run_dir = (app_config.SCREENER_RESULTS_DIR / record.storage_path).resolve()
    try:
        run_dir.relative_to(app_config.SCREENER_RESULTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Screener run not found") from exc
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Screener run '{record.id}' not found")
    return run_dir


def resolve_screener_artifact_path(
    record: screener_runs.ScreenerRun,
    artifact_key: str,
    default_filename: str,
) -> Path:
    relative_path = (record.artifact_manifest or {}).get(artifact_key)
    if not relative_path:
        relative_path = f"{record.storage_path}/{default_filename}"
    artifact_path = (app_config.SCREENER_RESULTS_DIR / relative_path).resolve()
    try:
        artifact_path.relative_to(app_config.SCREENER_RESULTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Screener artifact not found") from exc
    return artifact_path


def list_screener_runs_from_disk() -> list[dict]:
    if not app_config.SCREENER_RESULTS_DIR.is_dir():
        return []

    runs: list[dict] = []
    for entry in app_config.SCREENER_RESULTS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        meta_path = entry / "run_meta.json"
        if not meta_path.is_file():
            continue
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        runs.append(
            {
                "id": entry.name,
                "as_of_date": payload.get("as_of_date"),
                "markets": payload.get("config", {}).get("markets", []),
                "candidate_count": payload.get("candidate_count", 0),
                "generated_at": payload.get("run_timestamp", entry.name),
            }
        )

    runs.sort(key=lambda row: row["generated_at"] or "", reverse=True)
    return runs


def list_screener_runs(current_user: auth.User | None = None) -> list[dict]:
    if not auth.get_auth_settings().enabled:
        return list_screener_runs_from_disk()
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    with auth.db_session() as db:
        owner_scope = access.owner_scope_for_user(current_user)
        return [
            screener_runs.serialize_screener_run_summary(record)
            for record in screener_runs.list_screener_run_records(db, owner_user_id=owner_scope)
        ]


def get_screener_run(run_id: str, current_user: auth.User | None = None) -> dict:
    if auth.get_auth_settings().enabled:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            with auth.db_session() as db:
                owner_scope = access.owner_scope_for_user(current_user)
                record = screener_runs.get_screener_run_record(
                    db,
                    run_id,
                    owner_user_id=owner_scope,
                )
                payload = screener_runs.serialize_screener_run_detail(record)
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

        resolve_screener_run_dir_from_record(record)
        meta_path = resolve_screener_artifact_path(record, "run_meta", "run_meta.json")
        if not meta_path.is_file():
            raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
        try:
            file_payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read screener run: {exc}") from exc

        payload["filtered_count_by_reason"] = file_payload.get("filtered_count_by_reason", {})
        return payload

    run_dir = resolve_screener_run_dir(run_id)
    meta_path = run_dir / "run_meta.json"
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read screener run: {exc}") from exc

    return {
        "id": run_id,
        "as_of_date": payload.get("as_of_date"),
        "markets": payload.get("config", {}).get("markets", []),
        "candidate_count": payload.get("candidate_count", 0),
        "generated_at": payload.get("run_timestamp"),
        "filtered_count_by_reason": payload.get("filtered_count_by_reason", {}),
        "artifact_paths": payload.get("artifact_paths", {}),
    }


def get_screener_run_candidates(
    run_id: str,
    current_user: auth.User | None = None,
) -> list[dict]:
    if auth.get_auth_settings().enabled:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            with auth.db_session() as db:
                owner_scope = access.owner_scope_for_user(current_user)
                record = screener_runs.get_screener_run_record(
                    db,
                    run_id,
                    owner_user_id=owner_scope,
                )
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

        candidates_path = resolve_screener_artifact_path(record, "candidates", "candidates.csv")
    else:
        run_dir = resolve_screener_run_dir(run_id)
        candidates_path = run_dir / "candidates.csv"

    if not candidates_path.is_file():
        raise HTTPException(status_code=404, detail=f"Candidates for run '{run_id}' not found")
    try:
        import pandas as pd

        df = pd.read_csv(candidates_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read candidates: {exc}") from exc
    return df.where(pd.notna(df), None).to_dict(orient="records")


def record_screener_run_metadata(task, result) -> None:
    if not auth.get_auth_settings().enabled:
        return
    if not task.owner_user_id:
        raise RuntimeError("Screener task owner is required when auth is enabled")

    run_dir = Path(result.run_dir).resolve()
    run_id = run_dir.name
    with auth.db_session() as db:
        screener_runs.upsert_screener_run(
            db,
            run_id=run_id,
            owner_user_id=task.owner_user_id,
            as_of_date=str(task.request_payload.get("as_of_date") or "").strip() or None,
            markets=list(task.request_payload.get("markets") or []),
            candidate_count=int(getattr(result, "candidate_count", 0) or 0),
            generated_at=run_id,
            storage_path=relative_screener_storage_path(run_dir),
            artifact_manifest=build_screener_artifact_manifest(run_dir),
        )
