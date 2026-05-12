from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import HTTPException

from diverge.common.dates import parse_iso_date
from diverge.common.json_io import write_json_atomic
from diverge.common.market_calendar import latest_trading_day_on_or_before
from diverge.dataflows.vendor_errors import VendorDataEmptyError
from diverge.market_data.price_history import fetch_price_history
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
from web.backend import app_config, audit, auth, job_records
from web.backend.runtime import task_store
from web.backend.runtime.task_logging import (
    current_worker_id,
    log_task_event,
    task_error_fields,
)

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
DEFAULT_SIMFIN_DAILY_TICKER_LIMIT = 2500
OHLCV_READY_CHECKS = {
    ("cn", "tushare"): {
        "vendor_label": "Tushare",
        "timezone": "Asia/Shanghai",
        "cutoff_env": "DATA_SYNC_TUSHARE_READY_TIME",
        "default_cutoff": "18:10",
        "probe_symbols": ["000001.SZ", "600519.SH"],
    },
    ("us", "massive"): {
        "vendor_label": "Massive",
        "timezone": "America/New_York",
        "cutoff_env": "DATA_SYNC_MASSIVE_READY_TIME",
        "default_cutoff": "21:10",
        "probe_symbols": ["AAPL", "MSFT"],
    },
}
DEFAULT_READY_SOURCES = {"cn": "tushare", "us": "massive"}
MARKET_TIMEZONES = {"cn": "Asia/Shanghai", "us": "America/New_York"}


class VendorDataNotReadyError(RuntimeError):
    """Raised when same-day vendor bars are not available enough to start sync."""


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_for_vendor_timezone(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name)).replace(tzinfo=None)


def _parse_cutoff_time(raw_value: str) -> time:
    try:
        hour_text, minute_text = raw_value.strip().split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except Exception as exc:
        raise RuntimeError(
            f"Invalid data sync ready cutoff time '{raw_value}'. Use HH:MM."
        ) from exc


def _configured_cutoff_time(env_name: str, default_value: str) -> time:
    return _parse_cutoff_time(os.environ.get(env_name, default_value))


def _ohlcv_source_for_payload(payload: dict[str, Any], market: str) -> str:
    if market == "cn":
        return str(payload.get("cn_data_source") or "tushare").strip().lower()
    return str(payload.get("us_data_source") or "yfinance").strip().lower()


def _ohlcv_ready_context(market: str, source: str) -> dict[str, Any] | None:
    check = OHLCV_READY_CHECKS.get((market, source))
    if check is None:
        return None

    timezone_name = str(check["timezone"])
    return {
        **check,
        "timezone": timezone_name,
        "now_local": _now_for_vendor_timezone(timezone_name),
        "cutoff": _configured_cutoff_time(
            str(check["cutoff_env"]),
            str(check["default_cutoff"]),
        ),
    }


def _price_frame_has_as_of_date(frame: pd.DataFrame, as_of_date: str) -> bool:
    if frame is None or frame.empty or "Date" not in frame.columns:
        return False
    dates = pd.to_datetime(frame["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return bool((dates == as_of_date).any())


def _raise_vendor_not_ready(
    *,
    vendor_label: str,
    as_of_date: str,
    cutoff: time,
    timezone_name: str,
    reason: str,
) -> None:
    raise VendorDataNotReadyError(
        f"{vendor_label} daily data for {as_of_date} is not ready. "
        f"{reason} Retry after {cutoff.strftime('%H:%M')} {timezone_name}."
    )


def _probe_ohlcv_vendor_ready(
    *,
    market: str,
    source: str,
    as_of_date: str,
    probe_symbols: list[str],
) -> bool:
    for symbol in probe_symbols:
        try:
            frame = fetch_price_history(
                symbol,
                market,
                as_of_date,
                as_of_date,
                cn_data_source=source if market == "cn" else "tushare",
                us_data_source=source if market == "us" else "yfinance",
            )
        except VendorDataEmptyError:
            continue
        if _price_frame_has_as_of_date(frame, as_of_date):
            return True
    return False


def ensure_ohlcv_vendor_ready(payload: dict[str, Any]) -> None:
    as_of_date = str(payload["as_of_date"])
    requested_date = parse_iso_date(as_of_date)
    if requested_date is None:
        raise RuntimeError("as_of_date must use YYYY-MM-DD format")
    markets = [str(market).strip().lower() for market in payload.get("markets") or []]

    for market in markets:
        source = _ohlcv_source_for_payload(payload, market)
        ready_context = _ohlcv_ready_context(market, source)
        if ready_context is None:
            continue

        timezone_name = str(ready_context["timezone"])
        now_local = ready_context["now_local"]
        cutoff = ready_context["cutoff"]
        vendor_label = str(ready_context["vendor_label"])

        if requested_date > now_local.date():
            _raise_vendor_not_ready(
                vendor_label=vendor_label,
                as_of_date=as_of_date,
                cutoff=cutoff,
                timezone_name=timezone_name,
                reason="Requested date is ahead of the vendor-local date.",
            )
        if requested_date < now_local.date():
            continue
        if now_local.time() < cutoff:
            _raise_vendor_not_ready(
                vendor_label=vendor_label,
                as_of_date=as_of_date,
                cutoff=cutoff,
                timezone_name=timezone_name,
                reason=f"Current vendor-local time is {now_local.strftime('%H:%M')}.",
            )

        if not _probe_ohlcv_vendor_ready(
            market=market,
            source=source,
            as_of_date=as_of_date,
            probe_symbols=list(ready_context["probe_symbols"]),
        ):
            _raise_vendor_not_ready(
                vendor_label=vendor_label,
                as_of_date=as_of_date,
                cutoff=cutoff,
                timezone_name=timezone_name,
                reason="Readiness probe returned no bars for representative symbols.",
            )


def resolve_ready_ohlcv_as_of_date(
    market: str, source: str, candidate_day: date
) -> date:
    """Resolve the latest default screener date that should have vendor OHLCV data."""
    normalized_market = str(market).strip().lower()
    normalized_source = str(source).strip().lower()
    ready_context = _ohlcv_ready_context(normalized_market, normalized_source)
    if ready_context is None:
        return candidate_day

    now_local = ready_context["now_local"]
    cutoff = ready_context["cutoff"]

    ready_day = min(candidate_day, now_local.date())
    if ready_day == now_local.date() and now_local.time() < cutoff:
        ready_day = ready_day - timedelta(days=1)

    resolved_day = latest_trading_day_on_or_before(normalized_market, ready_day)
    return resolved_day or ready_day


def resolve_latest_ready_trading_day(
    market: str,
    source: str | None = None,
) -> date:
    """Resolve the latest market-local trading day with expected ready data."""
    normalized_market = str(market).strip().lower()
    normalized_source = (
        str(source or DEFAULT_READY_SOURCES.get(normalized_market) or "")
        .strip()
        .lower()
    )
    ready_context = _ohlcv_ready_context(normalized_market, normalized_source)
    if ready_context is not None:
        candidate_day = ready_context["now_local"].date()
        return resolve_ready_ohlcv_as_of_date(
            normalized_market,
            normalized_source,
            candidate_day,
        )

    timezone_name = MARKET_TIMEZONES.get(normalized_market, "UTC")
    candidate_day = _now_for_vendor_timezone(timezone_name).date()
    trading_day = latest_trading_day_on_or_before(normalized_market, candidate_day)
    return trading_day or candidate_day


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
        manifest_path = app_config.resolve_manifest_path(
            "cn", app_config.PROJECT_ROOT, require_exists=True
        )
        config_payload["cn_manifest_path"] = (
            str(manifest_path) if manifest_path else None
        )
    if "us" in payload["markets"] and not config_payload["us_manifest_path"]:
        manifest_path = app_config.resolve_manifest_path(
            "us", app_config.PROJECT_ROOT, require_exists=True
        )
        if not manifest_path:
            raise RuntimeError(
                "US data sync requires a manifest at DATA_DIR/manifest/us.csv "
                "or SCREEN_US_MANIFEST_PATH."
            )
        config_payload["us_manifest_path"] = (
            str(manifest_path) if manifest_path else None
        )
    return config_payload


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
            str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
        )
    )


def resolve_fundamental_symbols(payload: dict[str, Any]) -> list[str]:
    symbols = _dedupe_symbols(payload.get("symbols") or [])
    if symbols:
        return symbols

    market = str(payload["market"]).strip().lower()
    manifest_path = payload.get("manifest_path")
    if market == "us":
        manifest_path = manifest_path or app_config.resolve_manifest_path(
            "us",
            app_config.PROJECT_ROOT,
            require_exists=True,
        )
        if not manifest_path:
            return []
        universe_df = load_us_universe(str(manifest_path))
    elif market == "cn":
        manifest_path = manifest_path or app_config.resolve_manifest_path(
            "cn", app_config.PROJECT_ROOT, require_exists=True
        )
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
    if payload.get("run_screener_prewarm"):
        from web.backend.runtime import screener_prewarm

        check_data_sync_task_canceled(task.id)
        prewarm_summary = screener_prewarm.run_screener_prewarm_after_ohlcv(
            payload["markets"],
            payload["as_of_date"],
            ohlcv_payload=payload,
        )
        check_data_sync_task_canceled(task.id)
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
                "Pass symbols, manifest_path, add DATA_DIR/manifest/us.csv, "
                "or set SCREEN_US_MANIFEST_PATH as a compatibility override."
            )
        if len(symbols) > ticker_limit:
            raise RuntimeError(
                f"US SimFin fundamental sync requested {len(symbols)} symbols, "
                f"which exceeds SIMFIN_DAILY_TICKER_LIMIT={ticker_limit}. "
                "Reduce DATA_DIR/manifest/us.csv or raise the limit only if your SimFin plan allows it."
            )
        api_key = os.environ.get("SIMFIN_API_KEY")
        if not api_key:
            raise RuntimeError(
                "SIMFIN_API_KEY is required for US SimFin fundamental sync."
            )
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
