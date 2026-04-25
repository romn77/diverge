import os
import unittest
from unittest.mock import Mock, patch

from tradingagents.runner import AnalysisRequest
from web.backend.runtime import analysis_tasks, task_store


class RedisTaskQueueTests(unittest.TestCase):
    def setUp(self):
        analysis_tasks.tasks.clear()

    def tearDown(self):
        analysis_tasks.tasks.clear()
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
            patch("web.backend.runtime.task_store.get_task_store", return_value=fake_store),
            patch("web.backend.runtime.analysis_tasks.start_task_thread") as start_thread,
        ):
            body = analysis_tasks.create_task(self._request(), owner_user_id="user-1")
            task = analysis_tasks.get_task(body["task_id"])

        self.assertEqual(body["status"], "pending")
        self.assertEqual(fake_store.queue_names["analysis"], [body["task_id"]])
        start_thread.assert_not_called()

        self.assertEqual(task.owner_user_id, "user-1")
        self.assertEqual(task.request.ticker, "SPY")

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
        client.rpush.assert_any_call("ta:test:analysis:ids", "task-1")
        client.rpush.assert_any_call("ta:test:analysis:queue", "task-1")
        client.rpush.assert_any_call(
            "ta:test:analysis:task:task-1:events",
            '{"status":"running"}',
        )
        self.assertEqual(store.list_events("analysis", "task-1"), [{"status": "running"}])


if __name__ == "__main__":
    unittest.main()
