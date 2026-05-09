import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from diverge.dataflows.vendor_usage import QuotaWaitRequired
from diverge.runner import AnalysisRequest
from web.backend.runtime import (
    analysis_tasks,
    screener_tasks,
    task_scheduler,
    task_store,
)


class RedisTaskQueueTests(unittest.TestCase):
    def setUp(self):
        analysis_tasks.tasks.clear()

    def tearDown(self):
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        task_store.reset_task_store_cache()

    def _request(self):
        return AnalysisRequest(
            ticker="SPY",
            analysis_date="2026-03-13",
            analysts=["market", "news"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
            google_thinking_level=None,
        )

    def test_redis_mode_enqueues_analysis_task_without_starting_thread(self):
        fake_store = task_store.InMemoryTaskStore()

        with (
            patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
            patch(
                "web.backend.runtime.task_store.get_task_store", return_value=fake_store
            ),
            patch(
                "web.backend.runtime.analysis_tasks.start_task_thread"
            ) as start_thread,
        ):
            body = analysis_tasks.create_task(self._request(), owner_user_id="user-1")
            task = analysis_tasks.get_task(body["task_id"])

        self.assertEqual(body["status"], "queued")
        self.assertEqual(fake_store.queue_names["analysis"], [body["task_id"]])
        start_thread.assert_not_called()

        self.assertEqual(task.owner_user_id, "user-1")
        self.assertEqual(task.request.ticker, "SPY")
        self.assertIsNotNone(task.created_at)
        self.assertIsNotNone(task.queued_at)

    def test_store_queue_limit_counts_active_analysis_and_screener_tasks(self):
        fake_store = task_store.InMemoryTaskStore()
        fake_store.save_task(
            "analysis",
            "a1",
            {"id": "a1", "status": "running"},
            enqueue=False,
        )
        fake_store.save_task(
            "screener",
            "s1",
            {"id": "s1", "status": "pending"},
            enqueue=False,
        )

        self.assertEqual(fake_store.count_active("analysis"), 1)
        self.assertEqual(fake_store.count_active("screener"), 1)

    def test_scheduler_respects_global_and_per_user_running_limits(self):
        fake_store = task_store.InMemoryTaskStore()
        fake_store.save_task(
            "analysis",
            "a1",
            {"id": "a1", "status": "queued", "owner_user_id": "user-1"},
            enqueue=True,
        )
        fake_store.save_task(
            "analysis",
            "a2",
            {"id": "a2", "status": "queued", "owner_user_id": "user-1"},
            enqueue=True,
        )
        fake_store.save_task(
            "screener",
            "s1",
            {"id": "s1", "status": "queued", "owner_user_id": "user-2"},
            enqueue=True,
        )

        with (
            patch.dict(
                os.environ,
                {
                    "TASK_BACKEND": "redis",
                    "TASK_GLOBAL_RUNNING_LIMIT": "2",
                    "TASK_USER_RUNNING_LIMIT": "1",
                },
                clear=False,
            ),
            patch(
                "web.backend.runtime.task_store.get_task_store", return_value=fake_store
            ),
        ):
            self.assertEqual(
                task_scheduler.claim_next_task(timeout=0), ("analysis", "a1")
            )
            self.assertEqual(
                task_scheduler.claim_next_task(timeout=0), ("screener", "s1")
            )
            self.assertIsNone(task_scheduler.claim_next_task(timeout=0))

        self.assertEqual(fake_store.get_task("analysis", "a1")["status"], "running")
        self.assertEqual(fake_store.get_task("analysis", "a2")["status"], "queued")
        self.assertEqual(fake_store.get_task("screener", "s1")["status"], "running")

    def test_scheduler_uses_fifo_except_reserved_analysis_lane(self):
        fake_store = task_store.InMemoryTaskStore()
        fake_store.save_task(
            "screener",
            "s1",
            {
                "id": "s1",
                "status": "queued",
                "owner_user_id": "user-2",
                "queued_at": "2026-01-01T00:00:00+00:00",
            },
            enqueue=True,
        )
        fake_store.save_task(
            "analysis",
            "a1",
            {
                "id": "a1",
                "status": "queued",
                "owner_user_id": "user-1",
                "queued_at": "2026-01-01T00:00:10+00:00",
            },
            enqueue=True,
        )

        with (
            patch.dict(
                os.environ,
                {
                    "TASK_BACKEND": "redis",
                    "TASK_GLOBAL_RUNNING_LIMIT": "2",
                    "TASK_USER_RUNNING_LIMIT": "1",
                },
                clear=False,
            ),
            patch(
                "web.backend.runtime.task_store.get_task_store", return_value=fake_store
            ),
        ):
            self.assertEqual(
                task_scheduler.claim_next_task(timeout=0), ("screener", "s1")
            )

        reserve_store = task_store.InMemoryTaskStore()
        reserve_store.save_task(
            "screener",
            "s1",
            {
                "id": "s1",
                "status": "queued",
                "owner_user_id": "user-2",
                "queued_at": "2026-01-01T00:00:00+00:00",
            },
            enqueue=True,
        )
        reserve_store.save_task(
            "analysis",
            "a1",
            {
                "id": "a1",
                "status": "queued",
                "owner_user_id": "user-1",
                "queued_at": "2026-01-01T00:00:10+00:00",
            },
            enqueue=True,
        )

        with (
            patch.dict(
                os.environ,
                {
                    "TASK_BACKEND": "redis",
                    "TASK_GLOBAL_RUNNING_LIMIT": "1",
                    "TASK_USER_RUNNING_LIMIT": "1",
                },
                clear=False,
            ),
            patch(
                "web.backend.runtime.task_store.get_task_store",
                return_value=reserve_store,
            ),
        ):
            self.assertEqual(
                task_scheduler.claim_next_task(timeout=0), ("analysis", "a1")
            )

    def test_scheduler_promotes_due_delayed_tasks_before_claiming(self):
        fake_store = task_store.InMemoryTaskStore()
        fake_store.save_task(
            "analysis",
            "a1",
            {
                "id": "a1",
                "status": "waiting_for_quota",
                "owner_user_id": "user-1",
                "blocked_until": "2000-01-01T00:00:00+00:00",
            },
            enqueue=False,
        )
        fake_store.delay("analysis", "a1", 0)

        with (
            patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
            patch(
                "web.backend.runtime.task_store.get_task_store", return_value=fake_store
            ),
        ):
            self.assertEqual(
                task_scheduler.claim_next_task(timeout=0), ("analysis", "a1")
            )

        task = fake_store.get_task("analysis", "a1")
        self.assertEqual(task["status"], "running")
        self.assertEqual(fake_store.queue_names["analysis"], [])

    def test_cancel_queued_analysis_task_marks_canceled_and_removes_queue_refs(self):
        fake_store = task_store.InMemoryTaskStore()
        with (
            patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
            patch(
                "web.backend.runtime.task_store.get_task_store", return_value=fake_store
            ),
        ):
            body = analysis_tasks.create_task(self._request(), owner_user_id="user-1")
            analysis_tasks.cancel_task(body["task_id"])
            task = analysis_tasks.get_task(body["task_id"])

        self.assertEqual(task.status, "canceled")
        self.assertIsNotNone(task.canceled_at)
        self.assertEqual(fake_store.queue_names["analysis"], [])

    def test_running_analysis_task_waits_for_quota_instead_of_failing(self):
        fake_store = task_store.InMemoryTaskStore()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
                patch(
                    "web.backend.runtime.task_store.get_task_store",
                    return_value=fake_store,
                ),
                patch(
                    "web.backend.runtime.analysis_tasks.app_config.TMP_REPORTS_DIR",
                    Path(temp_dir),
                ),
                patch(
                    "web.backend.runtime.analysis_tasks.access.visible_trade_ids_for_task",
                    return_value=[],
                ),
                patch(
                    "web.backend.runtime.analysis_tasks.run_analysis_streaming",
                    side_effect=QuotaWaitRequired(
                        vendor="alpha_vantage",
                        reason="Data source quota exhausted.",
                        blocked_until="2030-01-01T00:00:00+00:00",
                    ),
                ),
            ):
                body = analysis_tasks.create_task(
                    self._request(), owner_user_id="user-1"
                )
                claimed = task_scheduler.claim_next_task(timeout=0)
                self.assertEqual(claimed, ("analysis", body["task_id"]))
                analysis_tasks.run_task(body["task_id"])
                task = analysis_tasks.get_task(body["task_id"])

        self.assertEqual(task.status, "waiting_for_quota")
        self.assertEqual(task.blocked_vendor, "alpha_vantage")
        self.assertEqual(task.blocked_until, "2030-01-01T00:00:00+00:00")
        self.assertIn(body["task_id"], fake_store.delayed_names["analysis"])

    def test_redis_store_uses_prefixed_keys_and_progress_lists(self):
        client = Mock()
        client.lrange.return_value = [b'{"status":"running"}']
        store = task_store.RedisTaskStore(client, prefix="ta:test")

        store.save_task(
            "analysis",
            "task-1",
            {"id": "task-1", "status": "pending"},
            enqueue=True,
        )
        store.append_event("analysis", "task-1", {"status": "running"})

        client.set.assert_called()
        client.sadd.assert_any_call("ta:test:analysis:ids", "task-1")
        client.rpush.assert_any_call("ta:test:analysis:queue", "task-1")
        client.rpush.assert_any_call(
            "ta:test:analysis:task:task-1:events",
            '{"status":"running"}',
        )
        self.assertEqual(
            store.list_events("analysis", "task-1"), [{"status": "running"}]
        )

    def test_redis_store_uses_deduped_ids_processing_queue_and_terminal_ttl(self):
        client = Mock()
        client.blmove.return_value = b"task-1"
        client.get.return_value = b'{"id":"task-1","status":"pending"}'
        store = task_store.RedisTaskStore(client, prefix="ta:test")

        store.save_task("analysis", "task-1", {"id": "task-1", "status": "pending"})
        store.save_task("analysis", "task-1", {"id": "task-1", "status": "running"})
        claimed_task_id = store.claim("analysis", timeout=7)
        store.save_task("analysis", "task-1", {"id": "task-1", "status": "completed"})
        store.ack("analysis", "task-1")

        self.assertEqual(claimed_task_id, "task-1")
        client.sadd.assert_any_call("ta:test:analysis:ids", "task-1")
        client.blmove.assert_called_once_with(
            "ta:test:analysis:queue",
            "ta:test:analysis:processing",
            timeout=7,
            src="LEFT",
            dest="RIGHT",
        )
        client.lrem.assert_any_call("ta:test:analysis:processing", 0, "task-1")
        client.expire.assert_any_call("ta:test:analysis:task:task-1", 604800)
        client.expire.assert_any_call("ta:test:analysis:task:task-1:events", 604800)
        id_pushes = [
            call
            for call in client.rpush.call_args_list
            if call.args[:1] == ("ta:test:analysis:ids",)
        ]
        self.assertEqual(id_pushes, [])

    def test_redis_store_recovers_pending_processing_tasks(self):
        client = Mock()
        client.lrange.return_value = [
            b"pending-1",
            b"done-1",
            b"missing-1",
            b"running-1",
        ]

        def get_value(key):
            payloads = {
                "ta:test:analysis:task:pending-1": b'{"id":"pending-1","status":"pending"}',
                "ta:test:analysis:task:done-1": b'{"id":"done-1","status":"completed"}',
                "ta:test:analysis:task:running-1": b'{"id":"running-1","status":"running"}',
            }
            return payloads.get(key)

        client.get.side_effect = get_value
        store = task_store.RedisTaskStore(client, prefix="ta:test")

        store.recover_processing("analysis")

        client.lrem.assert_any_call("ta:test:analysis:processing", 0, "pending-1")
        client.lrem.assert_any_call("ta:test:analysis:processing", 0, "done-1")
        client.lrem.assert_any_call("ta:test:analysis:processing", 0, "missing-1")
        client.rpush.assert_any_call("ta:test:analysis:queue", "pending-1")
        self.assertNotIn(
            ("ta:test:analysis:processing", 0, "running-1"),
            [call.args for call in client.lrem.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
