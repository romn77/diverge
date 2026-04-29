from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException

from diverge.screener.schema import ScreenRunConfig
from diverge.screener.sync import (
    sync_cn_tushare_fundamentals,
    sync_ohlcv_cache,
    sync_us_simfin_fundamentals,
)
from diverge.screener.stages import prepare_universe_stage
from diverge.screener.universe import (
    load_cn_universe_from_manifest,
    load_universe,
    load_us_universe,
)
from web.backend import app_config
from web.backend.runtime import task_store


@dataclass
class DataSyncTask:
    id: str
    sync_type: str
    request_payload: dict[str, Any]
    owner_user_id: str | None = None
    tenant_id: str | None = None
    status: str = "pending"
    latest_progress: dict[str, Any] | None = None
    progress_events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    queue_position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sync_type": self.sync_type,
            "request_payload": self.request_payload,
            "owner_user_id": self.owner_user_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "progress_events": self.progress_events,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "queue_position": self.queue_position,
        }


data_sync_tasks: dict[str, DataSyncTask] = {}
data_sync_tasks_lock = threading.Lock()
DEFAULT_SIMFIN_DAILY_TICKER_LIMIT = 2500


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_dir() -> Path:
    return app_config.SCREENER_STATE_DIR / "data_sync"


def _task_path(task_id: str) -> Path:
    return _state_dir() / f"{task_id}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _save_task(task: DataSyncTask) -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("data_sync", task.id, task.to_dict())
        return
    with data_sync_tasks_lock:
        data_sync_tasks[task.id] = task
    if task.status in app_config.TERMINAL_TASK_STATUSES:
        return
    _write_json(_task_path(task.id), task.to_dict())


def _append_progress(task_id: str, message: str, **extra: Any) -> None:
    progress = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        **extra,
    }
    if task_store.redis_task_backend_enabled():
        task = get_data_sync_task(task_id)
        task.latest_progress = progress
        task.progress_events.append(progress)
        _save_task(task)
        task_store.get_task_store().append_event("data_sync", task_id, progress)
        return
    with data_sync_tasks_lock:
        task = data_sync_tasks[task_id]
        task.latest_progress = progress
        task.progress_events.append(progress)
    _save_task(task)


def get_data_sync_task(task_id: str) -> DataSyncTask:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        payload = store.get_task("data_sync", task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Data sync task '{task_id}' not found")
        task = data_sync_task_from_payload(payload)
        task.queue_position = store.queue_position("data_sync", task.id)
        return task

    with data_sync_tasks_lock:
        task = data_sync_tasks.get(task_id)
    if task is not None:
        return task

    path = _task_path(task_id)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return data_sync_task_from_payload(payload)
    raise HTTPException(status_code=404, detail=f"Data sync task '{task_id}' not found")


def list_data_sync_tasks() -> list[DataSyncTask]:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        tasks = []
        for payload in store.list_tasks("data_sync"):
            task = data_sync_task_from_payload(payload)
            task.queue_position = store.queue_position("data_sync", task.id)
            tasks.append(task)
        return sorted(tasks, key=lambda task: task.created_at or "", reverse=True)

    with data_sync_tasks_lock:
        tasks = list(data_sync_tasks.values())
    for path in sorted(_state_dir().glob("*.json")) if _state_dir().is_dir() else []:
        if any(task.id == path.stem for task in tasks):
            continue
        try:
            tasks.append(data_sync_task_from_payload(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return sorted(tasks, key=lambda task: task.created_at or "", reverse=True)


def data_sync_task_from_payload(payload: dict[str, Any]) -> DataSyncTask:
    return DataSyncTask(
        id=str(payload["id"]),
        sync_type=str(payload["sync_type"]),
        request_payload=dict(payload.get("request_payload") or {}),
        owner_user_id=payload.get("owner_user_id"),
        tenant_id=payload.get("tenant_id"),
        status=str(payload.get("status") or "pending"),
        latest_progress=payload.get("latest_progress"),
        progress_events=list(payload.get("progress_events") or []),
        result=payload.get("result"),
        error=payload.get("error"),
        created_at=payload.get("created_at"),
        queued_at=payload.get("queued_at"),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        queue_position=payload.get("queue_position"),
    )


def build_ohlcv_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    top_k = int(payload.get("top_k") or 100)
    config_payload = {
        "markets": payload["markets"],
        "as_of_date": payload["as_of_date"],
        "top_k": min(max(top_k, 1), 100),
        "output_dir": str(app_config.SCREENER_RESULTS_DIR),
        "cache_dir": str(app_config.SCREENER_CACHE_DIR),
        "history_dir": str(app_config.STOCK_HISTORY_DIR),
        "cn_data_source": payload.get("cn_data_source") or "tushare",
        "cn_data_source_fallbacks": payload.get("cn_data_source_fallbacks") or [],
        "us_data_source": payload.get("us_data_source") or "yfinance",
        "us_data_source_fallbacks": payload.get("us_data_source_fallbacks") or [],
        "cn_manifest_path": payload.get("cn_manifest_path"),
        "us_manifest_path": payload.get("us_manifest_path"),
    }
    if "cn" in payload["markets"] and not config_payload["cn_manifest_path"]:
        config_payload["cn_manifest_path"] = os.environ.get("SCREEN_CN_MANIFEST_PATH")
    if "us" in payload["markets"] and not config_payload["us_manifest_path"]:
        config_payload["us_manifest_path"] = os.environ.get("SCREEN_US_MANIFEST_PATH")
    return config_payload


def run_ohlcv_sync_payload(
    payload: dict[str, Any],
    *,
    progress_callback: Callable[..., None] | None = None,
) -> dict[str, Any]:
    config_payload = build_ohlcv_config_payload(payload)
    result = sync_ohlcv_cache(
        ScreenRunConfig(**config_payload),
        progress_callback=progress_callback,
    )
    return asdict(result)


def resolve_prefiltered_symbols(payload: dict[str, Any]) -> dict[str, list[str]]:
    config_payload = build_ohlcv_config_payload(payload)
    config = ScreenRunConfig(**config_payload)
    universe_stage = prepare_universe_stage(config, Path(config.cache_dir))
    symbols_by_market: dict[str, list[str]] = {}
    if universe_stage.prefiltered_df.empty:
        return symbols_by_market
    for market, frame in universe_stage.prefiltered_df.groupby("market"):
        symbols = [
            str(symbol).strip()
            for symbol in frame["symbol"].tolist()
            if str(symbol).strip()
        ]
        symbols_by_market[str(market).strip().lower()] = symbols
    return symbols_by_market


def resolve_universe_symbols(payload: dict[str, Any]) -> dict[str, list[str]]:
    config_payload = build_ohlcv_config_payload(payload)
    config = ScreenRunConfig(**config_payload)
    universe_df = load_universe(config, cache_dir=Path(config.cache_dir))
    symbols_by_market: dict[str, list[str]] = {}
    if universe_df.empty:
        return symbols_by_market
    for market, frame in universe_df.groupby("market"):
        symbols = [
            str(symbol).strip()
            for symbol in frame["symbol"].tolist()
            if str(symbol).strip()
        ]
        symbols_by_market[str(market).strip().lower()] = list(dict.fromkeys(symbols))
    return symbols_by_market


def _simfin_daily_ticker_limit() -> int:
    raw_value = os.environ.get("SIMFIN_DAILY_TICKER_LIMIT")
    if raw_value is None:
        return DEFAULT_SIMFIN_DAILY_TICKER_LIMIT
    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise RuntimeError("SIMFIN_DAILY_TICKER_LIMIT must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError("SIMFIN_DAILY_TICKER_LIMIT must be greater than zero")
    return parsed


def _dedupe_symbols(symbols: list[Any]) -> list[str]:
    return list(
        dict.fromkeys(
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        )
    )


def resolve_fundamental_symbols(payload: dict[str, Any]) -> list[str]:
    symbols = _dedupe_symbols(payload.get("symbols") or [])
    if symbols:
        return symbols

    market = str(payload["market"]).strip().lower()
    manifest_path = payload.get("manifest_path")
    if market == "us":
        manifest_path = manifest_path or os.environ.get("SCREEN_US_MANIFEST_PATH")
        if not manifest_path:
            return []
        universe_df = load_us_universe(str(manifest_path))
    elif market == "cn":
        manifest_path = manifest_path or os.environ.get("SCREEN_CN_MANIFEST_PATH")
        if not manifest_path:
            return []
        universe_df = load_cn_universe_from_manifest(str(manifest_path))
    else:
        return []
    if universe_df.empty or "symbol" not in universe_df.columns:
        return []
    return _dedupe_symbols(universe_df["symbol"].tolist())


def _run_ohlcv_task(task: DataSyncTask) -> dict[str, Any]:
    payload = task.request_payload

    def progress_callback(
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        *,
        status: str | None = None,
        detail: str | None = None,
    ) -> None:
        message = f"{stage} {current}/{total}"
        if symbol:
            message += f" {symbol}"
        if status:
            message += f" [{status}]"
        if detail:
            message += f" {detail}"
        _append_progress(task.id, message, stage=stage, current=current, total=total, symbol=symbol)

    result = run_ohlcv_sync_payload(
        payload,
        progress_callback=progress_callback,
    )
    if payload.get("run_screener_prewarm"):
        from web.backend.runtime import screener_prewarm

        prewarm_summary = screener_prewarm.run_screener_prewarm_after_ohlcv(
            payload["markets"],
            payload["as_of_date"],
            ohlcv_payload=payload,
        )
        result["screener_prewarm"] = prewarm_summary
        _append_progress(
            task.id,
            f"screener prewarm enqueued after ohlcv sync: {prewarm_summary}",
            stage="prewarm",
            current=1,
            total=1,
        )
    return result


def run_fundamental_sync_payload(
    payload: dict[str, Any],
    *,
    progress_callback: Callable[..., None] | None = None,
) -> dict[str, Any]:
    market = str(payload["market"]).strip().lower()
    source = str(payload["source"]).strip().lower()
    symbols = resolve_fundamental_symbols(payload)
    if market == "us" and source == "simfin":
        ticker_limit = _simfin_daily_ticker_limit()
        if not symbols:
            raise RuntimeError(
                "symbols are required for US SimFin fundamental sync. "
                "Pass symbols, manifest_path, or set SCREEN_US_MANIFEST_PATH."
            )
        if len(symbols) > ticker_limit:
            raise RuntimeError(
                f"US SimFin fundamental sync requested {len(symbols)} symbols, "
                f"which exceeds SIMFIN_DAILY_TICKER_LIMIT={ticker_limit}. "
                "Reduce SCREEN_US_MANIFEST_PATH or raise the limit only if your SimFin plan allows it."
            )
        api_key = os.environ.get("SIMFIN_API_KEY")
        if not api_key:
            raise RuntimeError("SIMFIN_API_KEY is required for US SimFin fundamental sync.")
        result = sync_us_simfin_fundamentals(
            api_key=api_key,
            tickers=symbols or None,
            data_dir=payload.get("data_dir"),
            output_dir=str(app_config.FUNDAMENTALS_DIR),
            as_of_date=payload.get("as_of_date"),
        )
        return asdict(result)
    if market == "cn" and source == "tushare":
        if not symbols:
            raise RuntimeError("symbols are required for CN Tushare fundamental sync.")

        def cn_progress(current: int, total: int, symbol: str) -> None:
            if progress_callback is not None:
                progress_callback("fundamentals", current, total, symbol)

        result = sync_cn_tushare_fundamentals(
            symbols=symbols,
            output_dir=str(app_config.FUNDAMENTALS_DIR),
            as_of_date=payload.get("as_of_date"),
            progress_callback=cn_progress,
        )
        return asdict(result)
    raise RuntimeError(f"Unsupported fundamental sync route: {market}/{source}")


def _run_fundamental_task(task: DataSyncTask) -> dict[str, Any]:
    def progress_callback(
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        **_: Any,
    ) -> None:
        message = f"{stage} {current}/{total}"
        if symbol:
            message += f" {symbol}"
        _append_progress(
            task.id,
            message,
            stage=stage,
            current=current,
            total=total,
            symbol=symbol,
        )

    return run_fundamental_sync_payload(
        task.request_payload,
        progress_callback=progress_callback,
    )


def run_data_sync_task(task_id: str) -> None:
    task = get_data_sync_task(task_id)
    task.status = "running"
    task.started_at = _utc_iso()
    _save_task(task)
    try:
        _append_progress(task_id, f"{task.sync_type} sync started.")
        result = _run_ohlcv_task(task) if task.sync_type == "ohlcv" else _run_fundamental_task(task)
        task = get_data_sync_task(task_id)
        task.status = "completed"
        task.finished_at = _utc_iso()
        task.result = result
        _append_progress(task_id, f"{task.sync_type} sync completed.")
        _save_task(task)
    except Exception as exc:
        task = get_data_sync_task(task_id)
        task.status = "failed"
        task.finished_at = _utc_iso()
        task.error = str(exc)
        _append_progress(task_id, f"{task.sync_type} sync failed: {exc}")
        _save_task(task)


def _run_task(task_id: str) -> None:
    run_data_sync_task(task_id)


def create_data_sync_task(
    *,
    sync_type: str,
    request_payload: dict[str, Any],
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, str]:
    task_id = uuid.uuid4().hex
    now_iso = _utc_iso()
    task = DataSyncTask(
        id=task_id,
        sync_type=sync_type,
        request_payload=request_payload,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        created_at=now_iso,
    )
    if task_store.redis_task_backend_enabled():
        task.status = "queued"
        task.queued_at = now_iso
        task_store.get_task_store().save_task(
            "data_sync",
            task_id,
            task.to_dict(),
            enqueue=True,
        )
        task_store.get_task_store().append_event(
            "data_sync",
            task_id,
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "status": "queued",
                "message": f"{sync_type} sync queued.",
            },
        )
        return {"task_id": task_id, "status": "queued"}

    _save_task(task)
    thread = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
    thread.start()
    return {"task_id": task_id, "status": task.status}
