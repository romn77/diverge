from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from fastapi import HTTPException

from diverge.common.dates import offset_iso_date
from diverge.market_data.price_history import LOOKBACK_DAYS
from diverge.screener.schema import ScreenRunConfig
from diverge.screener.stages import (
    prepare_universe_stage,
    prune_universe_by_history_coverage,
)
from web.backend import app_config, auth, screener_results, screener_runs, storage

_READ_SERVICE = screener_results.ScreenerResultReadService()
_MAX_PREFLIGHT_EXAMPLES = 10


def relative_screener_storage_path(path: Path) -> str:
    resolved_root = app_config.SCREENER_RESULTS_DIR.resolve()
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(
            "Screener artifacts must stay under SCREENER_RESULTS_DIR"
        ) from exc
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
    if not run_dir.is_dir() and storage_backend_is_remote():
        storage.download_prefix(f"screener/runs/{run_id}", run_dir)
    if not run_dir.is_dir():
        raise HTTPException(
            status_code=404, detail=f"Screener run '{run_id}' not found"
        )
    return run_dir


def resolve_screener_run_dir_from_record(record: screener_runs.ScreenerRun) -> Path:
    run_dir = (app_config.SCREENER_RESULTS_DIR / record.storage_path).resolve()
    try:
        run_dir.relative_to(app_config.SCREENER_RESULTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Screener run not found") from exc
    if not run_dir.is_dir() and storage_backend_is_remote():
        storage.download_prefix(f"screener/runs/{record.storage_path}", run_dir)
    if not run_dir.is_dir():
        raise HTTPException(
            status_code=404, detail=f"Screener run '{record.id}' not found"
        )
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
        raise HTTPException(
            status_code=404, detail="Screener artifact not found"
        ) from exc
    if not artifact_path.is_file() and storage_backend_is_remote():
        run_dir = resolve_screener_run_dir_from_record(record)
        artifact_path = run_dir / Path(relative_path).name
    return artifact_path


def storage_backend_is_remote() -> bool:
    return storage.os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"


def _data_not_ready_error(
    *,
    config: ScreenRunConfig,
    symbols_checked: int,
    symbols_missing: int,
    missing_markets: list[str],
    examples: list[dict],
    universe_count_by_market: dict[str, int],
    reason: str | None = None,
) -> HTTPException:
    message = (
        f"Screener data is not ready for {config.as_of_date}. "
        "Only admins can refresh OHLCV data; run the admin data-sync job first."
    )
    detail = {
        "code": "screener_data_not_ready",
        "message": message,
        "as_of_date": config.as_of_date,
        "symbols_checked": symbols_checked,
        "symbols_missing": symbols_missing,
        "missing_markets": missing_markets,
        "examples": examples,
        "universe_count_by_market": universe_count_by_market,
        "required_history_start": offset_iso_date(config.as_of_date, -LOOKBACK_DAYS),
        "required_history_end": config.as_of_date,
    }
    if reason:
        detail["reason"] = reason
    return HTTPException(status_code=409, detail=detail)


def ensure_screener_cache_coverage(config: ScreenRunConfig) -> None:
    """Reject screener runs that would need live universe or OHLCV fetching."""
    cache_root = Path(config.cache_dir)
    history_root = Path(config.history_dir)

    try:
        universe_stage = prepare_universe_stage(config, cache_root)
    except Exception as exc:
        raise _data_not_ready_error(
            config=config,
            symbols_checked=0,
            symbols_missing=0,
            missing_markets=list(config.markets),
            examples=[],
            universe_count_by_market={},
            reason=str(exc),
        ) from exc

    prefiltered_df = universe_stage.prefiltered_df
    if prefiltered_df.empty:
        raise _data_not_ready_error(
            config=config,
            symbols_checked=0,
            symbols_missing=0,
            missing_markets=list(config.markets),
            examples=[],
            universe_count_by_market={},
            reason="No prefiltered universe symbols are available from the prepared cache.",
        )

    universe_count_by_market = {
        str(market): int(len(frame.index))
        for market, frame in prefiltered_df.groupby("market")
    }
    prune_bundle = prune_universe_by_history_coverage(
        prefiltered_df,
        config,
        history_root,
    )
    missing_count = int(len(prune_bundle.pruned_df.index))
    if missing_count and prune_bundle.kept_df.empty:
        missing_markets: Counter[str] = Counter(
            str(market).strip().lower()
            for market in prune_bundle.pruned_df["market"].tolist()
        )
        examples = [
            {
                "market": str(row.get("market") or ""),
                "symbol": str(row.get("symbol") or ""),
                "reason": str(row.get("drop_reason") or ""),
                "cache_span": row.get("cache_span"),
            }
            for row in prune_bundle.pruned_df.head(_MAX_PREFLIGHT_EXAMPLES).to_dict(
                orient="records"
            )
        ]
        raise _data_not_ready_error(
            config=config,
            symbols_checked=int(len(prefiltered_df.index)),
            symbols_missing=missing_count,
            missing_markets=sorted(missing_markets),
            examples=examples,
            universe_count_by_market=universe_count_by_market,
        )


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
    return _READ_SERVICE.list_recent_runs(current_user)


def get_screener_run(run_id: str, current_user: auth.User | None = None) -> dict:
    return _READ_SERVICE.get_run(run_id, current_user)


def get_screener_run_candidates(
    run_id: str,
    current_user: auth.User | None = None,
) -> list[dict]:
    return _READ_SERVICE.get_run_candidates(run_id, current_user)


def run_screener(task, result):
    return screener_results.run_screener(task, result)


def persist_screener_run(
    task,
    candidate=None,
    *,
    error_summary: str | None = None,
    source_run_id: str | None = None,
):
    return screener_results.persist_screener_run(
        task,
        candidate,
        error_summary=error_summary,
        source_run_id=source_run_id,
    )


def record_screener_run_metadata(task, result) -> None:
    screener_results.record_screener_run_metadata(task, result)
