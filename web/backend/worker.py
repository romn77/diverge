from __future__ import annotations

import logging
import os
import time

from web.backend.runtime import analysis_tasks, screener_tasks, task_store

logger = logging.getLogger(__name__)


def run_once(*, timeout: int = 5) -> bool:
    analysis_task_id = analysis_tasks.claim_next_task(timeout=timeout)
    if analysis_task_id:
        logger.info("Running analysis task %s", analysis_task_id)
        analysis_tasks.run_task(analysis_task_id)
        return True

    screener_task_id = screener_tasks.claim_next_screener_task(timeout=timeout)
    if screener_task_id:
        logger.info("Running screener task %s", screener_task_id)
        screener_tasks.run_screener_task(screener_task_id)
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
