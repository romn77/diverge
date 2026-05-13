from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from arq.worker import Retry

from diverge.worker.prewarm import (
    readiness,
    scheduler,
    state,
    vendor_readiness,
    worker,
    workflow,
)


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.enqueued: list[dict] = []
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.next_job = object()

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        if ex is not None:
            self.expirations[key] = ex
        return True

    async def enqueue_job(self, function: str, *args, **kwargs):
        self.enqueued.append(
            {"function": function, "args": args, "kwargs": dict(kwargs)}
        )
        return self.next_job


def _utc_from_local(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    zone_name: str,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=ZoneInfo(zone_name),
    ).astimezone(timezone.utc)


def test_prewarm_window_uses_market_local_cutoffs():
    cn_before = datetime(2026, 4, 28, 10, 9, tzinfo=timezone.utc)
    cn_start = datetime(2026, 4, 28, 10, 10, tzinfo=timezone.utc)
    cn_closed = datetime(2026, 4, 28, 13, 31, tzinfo=timezone.utc)

    assert readiness.resolve_due_prewarm_trading_day("cn", cn_before) is None
    assert readiness.resolve_due_prewarm_trading_day("cn", cn_start) == "2026-04-28"
    assert readiness.resolve_due_prewarm_trading_day("cn", cn_closed) is None


def test_us_prewarm_window_uses_new_york_timezone_for_dst():
    summer_start = _utc_from_local(2026, 5, 13, 21, 10, "America/New_York")
    winter_start = _utc_from_local(2026, 1, 5, 21, 10, "America/New_York")
    before = _utc_from_local(2026, 5, 13, 21, 9, "America/New_York")
    closed = _utc_from_local(2026, 5, 13, 23, 31, "America/New_York")

    assert readiness.resolve_due_prewarm_trading_day("us", before) is None
    assert readiness.resolve_due_prewarm_trading_day("us", summer_start) == "2026-05-13"
    assert readiness.resolve_due_prewarm_trading_day("us", winter_start) == "2026-01-05"
    assert readiness.resolve_due_prewarm_trading_day("us", closed) is None


def test_prewarm_window_skips_weekends():
    saturday = _utc_from_local(2026, 5, 16, 21, 10, "America/New_York")

    assert readiness.resolve_due_prewarm_trading_day("us", saturday) is None


def test_state_records_workflow_and_completed_marker(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("PREWARM_COMPLETED_TTL_SECONDS", "30")
    monkeypatch.setenv("PREWARM_WORKFLOW_TTL_SECONDS", "40")

    async def scenario():
        await state.mark_queued(redis, "US", "2026-05-13", "job-1")
        assert await state.workflow_status(redis, "us", "2026-05-13") == "queued"

        await state.mark_running(redis, "us", "2026-05-13", "job-1", 2)
        await state.mark_retrying(
            redis,
            "us",
            "2026-05-13",
            "job-1",
            2,
            "vendor_not_ready",
        )
        workflow = await state.get_workflow(redis, "us", "2026-05-13")
        assert workflow["status"] == "retrying"
        assert workflow["attempt"] == 2
        assert workflow["last_error"] == "vendor_not_ready"

        await state.mark_completed(
            redis,
            "us",
            "2026-05-13",
            "job-1",
            {"success": True, "symbols_count": 503, "extra": "dropped"},
        )
        assert await state.is_completed(redis, "us", "2026-05-13")
        assert redis.expirations[state.completed_key("us", "2026-05-13")] == 30
        assert redis.expirations[state.workflow_key("us", "2026-05-13")] == 40
        completed = await state.get_workflow(redis, "us", "2026-05-13")
        assert completed["status"] == "completed"
        assert completed["result"] == {"success": True, "symbols_count": 503}

    asyncio.run(scenario())


def test_scheduler_enqueues_stable_job_id(monkeypatch):
    redis = FakeRedis()

    monkeypatch.setattr(
        scheduler,
        "resolve_due_prewarm_trading_day",
        lambda market, now_utc=None: "2026-05-13",
    )

    result = asyncio.run(scheduler.prewarm_due_tick({"redis": redis}, markets=["us"]))

    assert result["enqueued"] == [
        {
            "market": "us",
            "trading_day": "2026-05-13",
            "job_id": "prewarm:us:2026-05-13:v1",
        }
    ]
    assert redis.enqueued == [
        {
            "function": "run_market_prewarm",
            "args": ("us", "2026-05-13"),
            "kwargs": {
                "_queue_name": "arq:prewarm",
                "_job_id": "prewarm:us:2026-05-13:v1",
            },
        }
    ]
    assert asyncio.run(state.workflow_status(redis, "us", "2026-05-13")) == "queued"


def test_scheduler_skips_completed_and_active_workflows(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(
        scheduler,
        "resolve_due_prewarm_trading_day",
        lambda market, now_utc=None: "2026-05-13",
    )

    async def scenario():
        await state.mark_completed(
            redis,
            "cn",
            "2026-05-13",
            "job-cn",
            {"success": True},
        )
        await state.mark_running(redis, "us", "2026-05-13", "job-us", 1)
        result = await scheduler.prewarm_due_tick(
            {"redis": redis},
            markets=["cn", "us"],
        )
        assert result["enqueued"] == []
        assert result["skipped"] == [
            {"market": "cn", "trading_day": "2026-05-13", "reason": "completed"},
            {
                "market": "us",
                "trading_day": "2026-05-13",
                "reason": "already_queued_or_running",
            },
        ]
        assert redis.enqueued == []

    asyncio.run(scenario())


def test_worker_retries_when_vendor_not_ready(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("PREWARM_RETRY_DEFER_SECONDS", "300")

    async def not_ready(market, trading_day):
        return False

    monkeypatch.setattr(worker, "check_vendor_ready", not_ready)

    async def scenario():
        with pytest.raises(Retry):
            await worker.run_market_prewarm(
                {"redis": redis, "job_id": "job-1", "job_try": 1},
                "cn",
                "2026-04-28",
            )
        workflow = await state.get_workflow(redis, "cn", "2026-04-28")
        assert workflow["status"] == "retrying"
        assert workflow["last_error"] == "vendor_not_ready"

    asyncio.run(scenario())


def test_worker_marks_failed_on_final_attempt(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("PREWARM_MAX_TRIES", "5")

    async def not_ready(market, trading_day):
        return False

    monkeypatch.setattr(worker, "check_vendor_ready", not_ready)

    async def scenario():
        with pytest.raises(RuntimeError, match="vendor_not_ready"):
            await worker.run_market_prewarm(
                {"redis": redis, "job_id": "job-1", "job_try": 5},
                "cn",
                "2026-04-28",
            )
        workflow = await state.get_workflow(redis, "cn", "2026-04-28")
        assert workflow["status"] == "failed"
        assert not await state.is_completed(redis, "cn", "2026-04-28")
        workflow_writes = [
            call
            for call in redis.set_calls
            if call[0] == state.workflow_key("cn", "2026-04-28")
        ]
        assert len(workflow_writes) == 2

    asyncio.run(scenario())


def test_worker_marks_completed_after_success(monkeypatch):
    redis = FakeRedis()

    async def ready(market, trading_day):
        return True

    async def successful_workflow(market, trading_day):
        return {
            "success": True,
            "market": market,
            "trading_day": trading_day,
            "ohlcv_synced": True,
            "screener_prewarmed": True,
            "symbols_count": 10,
        }

    monkeypatch.setattr(worker, "check_vendor_ready", ready)
    monkeypatch.setattr(worker, "run_market_prewarm_workflow", successful_workflow)

    result = asyncio.run(
        worker.run_market_prewarm(
            {"redis": redis, "job_id": "job-1", "job_try": 1},
            "cn",
            "2026-04-28",
        )
    )

    assert result["status"] == "completed"
    assert asyncio.run(state.is_completed(redis, "cn", "2026-04-28"))


def test_workflow_success_requires_ohlcv_success_and_screener_signal():
    result = workflow.build_workflow_success_result(
        "us",
        "2026-05-13",
        {
            "as_of_date": "2026-05-13",
            "ohlcv_sync": {"status": "completed", "symbols_success": 503},
            "screener_prewarm": {
                "status": "completed",
                "runs_total": 2,
                "runs_completed": 1,
                "runs_cached": 1,
            },
        },
    )

    assert result == {
        "success": True,
        "status": "completed",
        "market": "us",
        "trading_day": "2026-05-13",
        "ohlcv_synced": True,
        "screener_prewarmed": True,
        "manifest_as_of_date": "2026-05-13",
        "symbols_count": 503,
        "screener_runs_total": 2,
        "screener_runs_completed": 1,
        "screener_runs_cached": 1,
    }


def test_market_workflow_runs_ohlcv_fundamentals_and_screener(monkeypatch):
    from web.backend.runtime import data_sync_tasks, screener_prewarm

    calls = []

    monkeypatch.setattr(
        screener_prewarm,
        "build_ohlcv_sync_payload",
        lambda market, trading_day: {"markets": [market], "as_of_date": trading_day},
    )

    def sync_ohlcv(payload):
        calls.append(("ohlcv", payload["markets"][0], payload["as_of_date"]))
        return {"status": "completed", "symbols_success": 10}

    def sync_fundamentals(market, trading_day, *, ohlcv_payload):
        calls.append(("fundamentals", market, trading_day))
        return {"status": "completed", "symbols_success": 8}

    def sync_screener(market, trading_day):
        calls.append(("screener", market, trading_day))
        return {
            "status": "completed",
            "runs_total": 1,
            "runs_completed": 1,
            "runs_cached": 0,
        }

    monkeypatch.setattr(data_sync_tasks, "run_ohlcv_sync_payload", sync_ohlcv)
    monkeypatch.setattr(
        screener_prewarm,
        "run_fundamental_prewarm_sync",
        sync_fundamentals,
    )
    monkeypatch.setattr(workflow, "run_screener_prewarm_sync", sync_screener)

    result = workflow.run_market_prewarm_workflow_sync("cn", "2026-04-28")

    assert result["success"] is True
    assert result["screener_prewarmed"] is True
    assert calls == [
        ("ohlcv", "cn", "2026-04-28"),
        ("fundamentals", "cn", "2026-04-28"),
        ("screener", "cn", "2026-04-28"),
    ]


def test_async_market_workflow_uses_blocking_runner(monkeypatch):
    captured = {}

    async def run_inline(function, *args):
        captured["function"] = function
        captured["args"] = args
        return {"success": True, "market": args[0], "trading_day": args[1]}

    monkeypatch.setattr(workflow, "_run_blocking", run_inline)

    result = asyncio.run(workflow.run_market_prewarm_workflow("us", "2026-05-13"))

    assert result == {
        "success": True,
        "market": "us",
        "trading_day": "2026-05-13",
    }
    assert captured["function"] is workflow.run_market_prewarm_workflow_sync
    assert captured["args"] == ("us", "2026-05-13")


def test_vendor_readiness_delegates_to_backend_ready_check(monkeypatch):
    from web.backend.runtime import data_sync_tasks, screener_prewarm

    captured = {}
    monkeypatch.setattr(
        screener_prewarm,
        "build_ohlcv_sync_payload",
        lambda market, trading_day: {"markets": [market], "as_of_date": trading_day},
    )

    def ready(payload):
        captured.update(payload)

    monkeypatch.setattr(data_sync_tasks, "ensure_ohlcv_vendor_ready", ready)

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(vendor_readiness, "_run_blocking", run_inline)

    assert asyncio.run(vendor_readiness.check_vendor_ready("cn", "2026-04-28"))
    assert captured == {"markets": ["cn"], "as_of_date": "2026-04-28"}


def test_vendor_readiness_returns_false_when_backend_vendor_is_not_ready(monkeypatch):
    from web.backend.runtime import data_sync_tasks, screener_prewarm

    monkeypatch.setattr(
        screener_prewarm,
        "build_ohlcv_sync_payload",
        lambda market, trading_day: {"markets": [market], "as_of_date": trading_day},
    )

    def not_ready(payload):
        raise data_sync_tasks.VendorDataNotReadyError("not ready")

    monkeypatch.setattr(data_sync_tasks, "ensure_ohlcv_vendor_ready", not_ready)

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(vendor_readiness, "_run_blocking", run_inline)

    assert not asyncio.run(vendor_readiness.check_vendor_ready("us", "2026-05-13"))


def test_prewarm_arq_settings_parse_redis_url(monkeypatch):
    from web.backend.runtime import prewarm_arq

    settings = prewarm_arq.redis_settings_from_dsn(
        "redis://user:pass@redis.example:6380/3"
    )

    assert settings.host == "redis.example"
    assert settings.port == 6380
    assert settings.database == 3
    assert settings.username == "user"
    assert settings.password == "pass"
