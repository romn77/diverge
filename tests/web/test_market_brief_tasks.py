from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from web.backend import app_config
from web.backend.routers import market_briefs as market_briefs_router
from web.backend.runtime import market_brief_tasks, task_store
from web.backend.schemas.market_briefs import MarketBriefCreatePayload
from web.backend.services import market_briefs as market_brief_service


@contextlib.contextmanager
def _reset_state(tmp_path: Path):
    original_reports = app_config.REPORTS_DIR
    original_tmp = app_config.TMP_REPORTS_DIR
    original_state = app_config.SCREENER_STATE_DIR
    app_config.REPORTS_DIR = tmp_path / "reports"
    app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
    app_config.SCREENER_STATE_DIR = tmp_path / "state"
    market_brief_tasks.market_brief_tasks.clear()
    task_store.reset_task_store_cache()
    try:
        yield
    finally:
        app_config.REPORTS_DIR = original_reports
        app_config.TMP_REPORTS_DIR = original_tmp
        app_config.SCREENER_STATE_DIR = original_state
        market_brief_tasks.market_brief_tasks.clear()
        task_store.reset_task_store_cache()


def test_market_brief_manual_task_creates_pending_task(tmp_path):
    with (
        _reset_state(tmp_path),
        patch(
            "web.backend.runtime.market_brief_tasks.start_market_brief_task_thread"
        ) as start_thread,
    ):
        payload = MarketBriefCreatePayload(markets=["cn", "hk", "us"])
        result = market_briefs_router.create_market_brief_task(payload)

        assert result["status"] == "pending"
        start_thread.assert_called_once()
        task = market_brief_tasks.get_market_brief_task(result["task_id"])
        assert task.request_payload["markets"] == ["cn", "hk", "us"]
        assert task.request_payload["trigger"] == "manual"


def test_market_brief_run_writes_report_artifact(tmp_path):
    with (
        _reset_state(tmp_path),
        patch(
            "diverge.market_brief.builder.collect_web_search_sources"
        ) as collect_sources,
        patch(
            "diverge.market_brief.builder.collect_market_snapshots"
        ) as collect_snapshots,
        patch("web.backend.runtime.market_brief_tasks.start_market_brief_task_thread"),
    ):
        collect_sources.return_value = []
        collect_snapshots.return_value = []
        result = market_brief_tasks.create_market_brief_task(
            request_payload={
                "markets": ["cn", "hk", "us"],
                "output_language": "zh-CN",
                "report_visibility": "workspace",
                "trigger": "manual",
            }
        )
        market_brief_tasks.run_market_brief_task(result["task_id"])

        task = market_brief_tasks.get_market_brief_task(result["task_id"])
        assert task.status == "completed"
        assert task.report_id
        report_dir = app_config.REPORTS_DIR / task.report_id
        artifact_path = report_dir / "artifacts" / "premarket_brief.json"
        assert artifact_path.is_file()
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert payload["type"] == "premarket_brief"
        assert payload["markets"] == ["cn", "hk", "us"]
        assert (report_dir / "complete_report.md").is_file()

        index = market_brief_service.list_market_briefs(
            today=datetime.now(timezone.utc).date()
        )
        assert index["latest"]["report_id"] == task.report_id


def test_market_brief_scheduler_tick_enqueues_redis_task(monkeypatch):
    from diverge.worker.market_brief import scheduler

    class FakeRedis:
        def __init__(self):
            self.values = {}

        async def get(self, key):
            return self.values.get(key)

        async def set(self, key, value, ex=None):
            self.values[key] = value
            return True

    fake_store = task_store.InMemoryTaskStore()
    monkeypatch.setenv("TASK_BACKEND", "redis")
    monkeypatch.setenv("MARKET_BRIEF_ENABLED", "true")
    monkeypatch.setenv("MARKET_BRIEF_TIMES", "08:30")
    monkeypatch.setenv("MARKET_BRIEF_MARKETS", "cn,hk,us")
    monkeypatch.setenv("MARKET_BRIEF_TIMEZONE", "Asia/Shanghai")

    with (
        patch("web.backend.runtime.task_store.get_task_store", return_value=fake_store),
        patch(
            "web.backend.runtime.market_brief_tasks.resolve_automation_owner"
        ) as resolve_owner,
    ):
        resolve_owner.return_value = (None, None)
        import asyncio

        payload = asyncio.run(
            scheduler.market_brief_due_tick(
                {"redis": FakeRedis()},
                now_utc=datetime(2026, 5, 15, 0, 30, tzinfo=timezone.utc),
            )
        )
    assert payload["enqueued"]
    task_id = payload["enqueued"][0]["task_id"]
    stored = fake_store.get_task("market_brief", task_id)
    assert stored["request_payload"]["markets"] == ["cn", "hk", "us"]
    assert stored["request_payload"]["trigger"] == "scheduled"
