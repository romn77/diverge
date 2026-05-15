from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from web.backend import app_config
from web.backend.monitoring import initialize_sentry
from web.backend.runtime import (
    analysis_tasks,
    backtest_tasks,
    data_sync_tasks,
    market_brief_tasks,
    opportunity_tasks,
    screener_tasks,
    task_scheduler,
    task_store,
)
from web.backend.runtime.task_logging import (
    current_worker_id,
    log_task_event,
    task_error_fields,
)

logger = logging.getLogger(__name__)


def _task_payload(kind: str, task_id: str) -> dict | None:
    try:
        return task_store.get_task_store().get_task(kind, task_id)
    except Exception:
        return None


def _run_claimed_task(
    *,
    kind: str,
    task_id: str,
    runner: Callable[[str], None],
) -> bool:
    started = time.monotonic()
    log_task_event(
        logger,
        "worker_task_started",
        kind=kind,
        task_id=task_id,
        task=_task_payload(kind, task_id),
    )
    try:
        runner(task_id)
    except Exception as exc:
        log_task_event(
            logger,
            "worker_task_failed",
            kind=kind,
            task_id=task_id,
            task=_task_payload(kind, task_id),
            duration_seconds=round(time.monotonic() - started, 3),
            **task_error_fields(exc),
        )
        raise
    else:
        log_task_event(
            logger,
            "worker_task_finished",
            kind=kind,
            task_id=task_id,
            task=_task_payload(kind, task_id),
            duration_seconds=round(time.monotonic() - started, 3),
        )
        return True
    finally:
        task_store.get_task_store().ack(kind, task_id)
        log_task_event(
            logger,
            "worker_task_acknowledged",
            kind=kind,
            task_id=task_id,
            task=_task_payload(kind, task_id),
        )


def run_once(*, timeout: int = 5) -> bool:
    claimed = task_scheduler.claim_next_task(timeout=timeout)
    if claimed is None:
        return False

    kind, task_id = claimed
    if kind == "analysis":
        return _run_claimed_task(
            kind="analysis", task_id=task_id, runner=analysis_tasks.run_task
        )

    if kind == "screener":
        return _run_claimed_task(
            kind="screener", task_id=task_id, runner=screener_tasks.run_screener_task
        )

    if kind == "data_sync":
        return _run_claimed_task(
            kind="data_sync", task_id=task_id, runner=data_sync_tasks.run_data_sync_task
        )

    if kind == "market_brief":
        return _run_claimed_task(
            kind="market_brief",
            task_id=task_id,
            runner=market_brief_tasks.run_market_brief_task,
        )

    if kind == "opportunity":
        return _run_claimed_task(
            kind="opportunity",
            task_id=task_id,
            runner=opportunity_tasks.run_opportunity_task,
        )

    if kind == "backtest":
        return _run_claimed_task(
            kind="backtest", task_id=task_id, runner=backtest_tasks.run_backtest_task
        )

    return False


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    initialize_sentry(default_service_name="worker")
    if not task_store.redis_task_backend_enabled():
        raise RuntimeError("Worker requires TASK_BACKEND=redis")

    logger.info(
        "worker_started worker_id=%s task_backend=redis redis_url_configured=%s",
        current_worker_id(),
        bool(os.environ.get("REDIS_URL")),
    )
    analysis_tasks.restore_persisted_active_tasks()
    screener_tasks.restore_persisted_screener_tasks()
    data_sync_tasks.restore_persisted_data_sync_tasks()
    market_brief_tasks.restore_persisted_market_brief_tasks()
    if app_config.opportunity_radar_enabled():
        opportunity_tasks.restore_persisted_opportunity_tasks()
        backtest_tasks.restore_persisted_backtest_tasks()

    worker_once = os.environ.get("WORKER_ONCE", "").lower() in {"1", "true", "yes"}
    while True:
        did_work = run_once(timeout=int(os.environ.get("WORKER_POLL_TIMEOUT", "5")))
        if worker_once:
            return
        if not did_work:
            time.sleep(float(os.environ.get("WORKER_IDLE_SLEEP", "1")))


if __name__ == "__main__":
    main()
