from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException

from diverge.common.json_io import write_json_atomic
from diverge.screener.schema import ScreenRunConfig
from diverge.screener.sync import (
    sync_ohlcv_cache,
)
from diverge.screener.stages import prepare_universe_stage
from diverge.screener.universe import (
    load_universe,
)
from web.backend import app_config, audit, auth, job_records
from web.backend.runtime import task_store
from web.backend.runtime.task_logging import (
    current_worker_id,
    log_task_event,
    task_error_fields,
)
from web.backend.services import fundamental_sync, ohlcv_readiness, ohlcv_sync_payloads

logger = logging.getLogger(__name__)


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
    cancel_requested_at: str | None = None
    canceled_at: str | None = None

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
            "cancel_requested_at": self.cancel_requested_at,
            "canceled_at": self.canceled_at,
        }


data_sync_tasks: dict[str, DataSyncTask] = {}
data_sync_tasks_lock = threading.Lock()
VendorDataNotReadyError = ohlcv_readiness.VendorDataNotReadyError
fetch_price_history = ohlcv_readiness.fetch_price_history


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_for_vendor_timezone(timezone_name: str) -> datetime:
    return ohlcv_readiness.now_for_vendor_timezone(timezone_name)


def ensure_ohlcv_vendor_ready(payload: dict[str, Any]) -> None:
    return ohlcv_readiness.ensure_ohlcv_vendor_ready(
        payload,
        now_for_timezone=_now_for_vendor_timezone,
        fetch_price_history_fn=fetch_price_history,
    )


def resolve_ready_ohlcv_as_of_date(
    market: str, source: str, candidate_day: date
) -> date:
    return ohlcv_readiness.resolve_ready_ohlcv_as_of_date(
        market,
        source,
        candidate_day,
        now_for_timezone=_now_for_vendor_timezone,
    )


def resolve_latest_ready_trading_day(
    market: str,
    source: str | None = None,
) -> date:
    return ohlcv_readiness.resolve_latest_ready_trading_day(
        market,
        source,
        now_for_timezone=_now_for_vendor_timezone,
    )


def _state_dir() -> Path:
    return app_config.SCREENER_STATE_DIR / "data_sync"


def _task_path(task_id: str) -> Path:
    return _state_dir() / f"{task_id}.json"


def _save_task(task: DataSyncTask) -> None:
    job_records.upsert_job_record(
        kind="data_sync",
        task_id=task.id,
        status=task.status,
        request_payload=task.request_payload,
        result_summary=task.result,
        error=task.error,
        owner_user_id=task.owner_user_id,
        tenant_id=task.tenant_id,
        created_at=task.created_at,
        queued_at=task.queued_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        heartbeat_at=_utc_iso() if task.status == "running" else None,
        worker_id=current_worker_id() if task.status == "running" else None,
    )
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("data_sync", task.id, task.to_dict())
        return
    with data_sync_tasks_lock:
        data_sync_tasks[task.id] = task
    write_json_atomic(_task_path(task.id), task.to_dict())


def _build_recovered_progress(task: DataSyncTask) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "failed",
        "message": f"{task.sync_type} sync failed: {app_config.RECOVERED_TASK_ERROR}",
    }


def restore_persisted_data_sync_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing("data_sync")
        for task in list_data_sync_tasks():
            if task.status == "running":
                task.status = "failed"
                task.error = app_config.RECOVERED_TASK_ERROR
                task.finished_at = task.finished_at or _utc_iso()
                failure_progress = _build_recovered_progress(task)
                task.latest_progress = failure_progress
                task.progress_events.append(failure_progress)
                _save_task(task)
                task_store.get_task_store().append_event(
                    "data_sync", task.id, failure_progress
                )
                task_store.get_task_store().ack("data_sync", task.id)
        return

    if not _state_dir().is_dir():
        return

    for path in sorted(_state_dir().glob("*.json")):
        try:
            task = data_sync_task_from_payload(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        if task.status in app_config.TERMINAL_TASK_STATUSES:
            continue

        task.status = "failed"
        task.error = app_config.RECOVERED_TASK_ERROR
        task.finished_at = task.finished_at or _utc_iso()
        failure_progress = _build_recovered_progress(task)
        task.latest_progress = failure_progress
        task.progress_events.append(failure_progress)
        _save_task(task)


def data_sync_audit_metadata(
    task: DataSyncTask,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload = task.request_payload
    metadata: dict[str, Any] = {
        "sync_type": task.sync_type,
        "markets": payload.get("markets"),
        "market": payload.get("market"),
        "as_of_date": payload.get("as_of_date"),
        "cn_data_source": payload.get("cn_data_source"),
        "us_data_source": payload.get("us_data_source"),
    }
    if result:
        for key in (
            "symbols_total",
            "symbols_success",
            "symbols_failed",
            "rows_written",
            "symbols_missing_as_of_bar",
            "symbols_pruned_from_screener",
            "quality_artifact_path",
            "quality_reason_counts",
        ):
            if key in result:
                metadata[key] = result.get(key)
    if error:
        metadata["error"] = error
    return {key: value for key, value in metadata.items() if value is not None}


def record_data_sync_audit_event(
    task: DataSyncTask,
    *,
    action: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if task.owner_user_id is None or task.tenant_id is None or not auth.auth_enabled():
        return
    try:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=task.tenant_id,
                actor_user_id=task.owner_user_id,
                action=action,
                resource_type="data_sync_task",
                resource_id=task.id,
                metadata=data_sync_audit_metadata(task, result=result, error=error),
            )
    except Exception:
        return


def check_data_sync_task_canceled(task_id: str) -> None:
    if get_data_sync_task(task_id).cancel_requested_at:
        raise task_store.TaskCanceled("Data sync task canceled by request.")


def _data_sync_cancel_requested_progress(task: DataSyncTask) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "running",
        "message": (
            f"{task.sync_type} sync termination requested. "
            "Work will stop at the next safe step."
        ),
    }


def _data_sync_canceled_progress(task: DataSyncTask) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "canceled",
        "message": f"{task.sync_type} sync canceled by request.",
    }


def _mark_data_sync_task_canceled(task_id: str) -> None:
    task = get_data_sync_task(task_id)
    now_iso = _utc_iso()
    task.status = "canceled"
    task.canceled_at = task.canceled_at or now_iso
    task.finished_at = now_iso
    task.error = None
    task.result = None
    progress = _data_sync_canceled_progress(task)
    task.latest_progress = progress
    task.progress_events.append(progress)
    _save_task(task)
    log_task_event(
        logger,
        "task_canceled",
        kind="data_sync",
        task_id=task_id,
        task=task,
        sync_type=task.sync_type,
    )
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().append_event("data_sync", task_id, progress)
    record_data_sync_audit_event(
        task,
        action=f"data_sync.{task.sync_type}.canceled",
    )


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
        log_task_event(
            logger,
            "task_progress",
            kind="data_sync",
            task_id=task_id,
            task=task,
            message=message,
            stage=extra.get("stage"),
            current=extra.get("current"),
            total=extra.get("total"),
            symbol=extra.get("symbol"),
        )
        return
    with data_sync_tasks_lock:
        task = data_sync_tasks[task_id]
        task.latest_progress = progress
        task.progress_events.append(progress)
    _save_task(task)
    log_task_event(
        logger,
        "task_progress",
        kind="data_sync",
        task_id=task_id,
        task=task,
        message=message,
        stage=extra.get("stage"),
        current=extra.get("current"),
        total=extra.get("total"),
        symbol=extra.get("symbol"),
    )


def get_data_sync_task(task_id: str) -> DataSyncTask:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        payload = store.get_task("data_sync", task_id)
        if payload is None:
            raise HTTPException(
                status_code=404, detail=f"Data sync task '{task_id}' not found"
            )
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
            tasks.append(
                data_sync_task_from_payload(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            )
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
        cancel_requested_at=payload.get("cancel_requested_at"),
        canceled_at=payload.get("canceled_at"),
    )


def build_ohlcv_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return ohlcv_sync_payloads.build_ohlcv_config_payload(payload)


def run_ohlcv_sync_payload(
    payload: dict[str, Any],
    *,
    progress_callback: Callable[..., None] | None = None,
) -> dict[str, Any]:
    ensure_ohlcv_vendor_ready(payload)
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


def resolve_fundamental_symbols(payload: dict[str, Any]) -> list[str]:
    return fundamental_sync.resolve_fundamental_symbols(payload)


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
        _append_progress(
            task.id, message, stage=stage, current=current, total=total, symbol=symbol
        )
        check_data_sync_task_canceled(task.id)

    check_data_sync_task_canceled(task.id)
    result = run_ohlcv_sync_payload(
        payload,
        progress_callback=progress_callback,
    )
    check_data_sync_task_canceled(task.id)
    return result


def run_fundamental_sync_payload(
    payload: dict[str, Any],
    *,
    progress_callback: Callable[..., None] | None = None,
) -> dict[str, Any]:
    return fundamental_sync.run_fundamental_sync_payload(
        payload,
        progress_callback=progress_callback,
    )


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
        check_data_sync_task_canceled(task.id)

    check_data_sync_task_canceled(task.id)
    return run_fundamental_sync_payload(
        task.request_payload,
        progress_callback=progress_callback,
    )


def run_data_sync_task(task_id: str) -> None:
    task = get_data_sync_task(task_id)
    task.status = "running"
    task.started_at = _utc_iso()
    _save_task(task)
    log_task_event(
        logger,
        "task_started",
        kind="data_sync",
        task_id=task_id,
        task=task,
        sync_type=task.sync_type,
    )
    try:
        check_data_sync_task_canceled(task_id)
        _append_progress(task_id, f"{task.sync_type} sync started.")
        result = (
            _run_ohlcv_task(task)
            if task.sync_type == "ohlcv"
            else _run_fundamental_task(task)
        )
        check_data_sync_task_canceled(task_id)
        task = get_data_sync_task(task_id)
        task.status = "completed"
        task.finished_at = _utc_iso()
        task.result = result
        check_data_sync_task_canceled(task_id)
        _append_progress(task_id, f"{task.sync_type} sync completed.")
        _save_task(task)
        log_task_event(
            logger,
            "task_completed",
            kind="data_sync",
            task_id=task_id,
            task=task,
            sync_type=task.sync_type,
            result_keys=sorted(result.keys()),
        )
        record_data_sync_audit_event(
            task,
            action=f"data_sync.{task.sync_type}.completed",
            result=result,
        )
    except task_store.TaskCanceled:
        _mark_data_sync_task_canceled(task_id)
    except Exception as exc:
        task = get_data_sync_task(task_id)
        task.status = "failed"
        task.finished_at = _utc_iso()
        task.error = str(exc)
        _append_progress(task_id, f"{task.sync_type} sync failed: {exc}")
        _save_task(task)
        log_task_event(
            logger,
            "task_failed",
            kind="data_sync",
            task_id=task_id,
            task=task,
            sync_type=task.sync_type,
            **task_error_fields(exc),
        )
        record_data_sync_audit_event(
            task,
            action=f"data_sync.{task.sync_type}.failed",
            error=str(exc),
        )


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
        _save_task(task)
        task_store.get_task_store().enqueue("data_sync", task_id)
        task_store.get_task_store().append_event(
            "data_sync",
            task_id,
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "status": "queued",
                "message": f"{sync_type} sync queued.",
            },
        )
        log_task_event(
            logger,
            "task_queued",
            kind="data_sync",
            task_id=task_id,
            task=task,
            sync_type=sync_type,
        )
        return {"task_id": task_id, "status": "queued"}

    _save_task(task)
    thread = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
    thread.start()
    log_task_event(
        logger,
        "task_submitted",
        kind="data_sync",
        task_id=task_id,
        task=task,
        sync_type=sync_type,
    )
    return {"task_id": task_id, "status": task.status}


def cancel_data_sync_task(task_id: str) -> None:
    task = get_data_sync_task(task_id)
    if task.status in task_store.TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409, detail="Finished data sync tasks cannot be canceled."
        )
    now_iso = _utc_iso()
    if task.status == "running":
        if not task.cancel_requested_at:
            task.cancel_requested_at = now_iso
            task.latest_progress = _data_sync_cancel_requested_progress(task)
            task.progress_events.append(task.latest_progress)
        _save_task(task)
        log_task_event(
            logger,
            "task_cancel_requested",
            kind="data_sync",
            task_id=task_id,
            task=task,
            sync_type=task.sync_type,
        )
        if task_store.redis_task_backend_enabled():
            task_store.get_task_store().append_event(
                "data_sync", task_id, task.latest_progress
            )
        return

    task.status = "canceled"
    task.cancel_requested_at = task.cancel_requested_at or now_iso
    task.canceled_at = now_iso
    task.finished_at = now_iso
    task.error = None
    task.result = None
    task.latest_progress = _data_sync_canceled_progress(task)
    task.progress_events.append(task.latest_progress)
    _save_task(task)
    log_task_event(
        logger,
        "task_canceled",
        kind="data_sync",
        task_id=task_id,
        task=task,
        sync_type=task.sync_type,
    )
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        store.remove_task_refs("data_sync", task_id)
        store.append_event("data_sync", task_id, task.latest_progress)
    record_data_sync_audit_event(
        task,
        action=f"data_sync.{task.sync_type}.canceled",
    )
