from __future__ import annotations

import logging
import os
import time

from web.backend.runtime import (
    analysis_tasks,
    data_sync_tasks,
    screener_tasks,
    task_scheduler,
    task_store,
)

logger = logging.getLogger(__name__)


def run_once(*, timeout: int = 5) -> bool:
    claimed = task_scheduler.claim_next_task(timeout=timeout)
    if claimed is None:
        return False

    kind, task_id = claimed
    if kind == "analysis":
        logger.info("Running analysis task %s", task_id)
        try:
            analysis_tasks.run_task(task_id)
        finally:
            task_store.get_task_store().ack("analysis", task_id)
        return True

    if kind == "screener":
        logger.info("Running screener task %s", task_id)
        try:
            screener_tasks.run_screener_task(task_id)
        finally:
            task_store.get_task_store().ack("screener", task_id)
        return True

    if kind == "data_sync":
        logger.info("Running data sync task %s", task_id)
        try:
            data_sync_tasks.run_data_sync_task(task_id)
        finally:
            task_store.get_task_store().ack("data_sync", task_id)
        return True

    return False


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    if not task_store.redis_task_backend_enabled():
        raise RuntimeError("Worker requires TASK_BACKEND=redis")

    analysis_tasks.restore_persisted_active_tasks()
    screener_tasks.restore_persisted_screener_tasks()

    worker_once = os.environ.get("WORKER_ONCE", "").lower() in {"1", "true", "yes"}
    while True:
        did_work = run_once(timeout=int(os.environ.get("WORKER_POLL_TIMEOUT", "5")))
        if worker_once:
            return
        if not did_work:
            time.sleep(float(os.environ.get("WORKER_IDLE_SLEEP", "1")))


if __name__ == "__main__":
    main()
