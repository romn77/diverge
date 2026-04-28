import tempfile
import unittest
import asyncio
import contextlib
import os
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from tradingagents.dataflows import vendor_usage
from tradingagents.runner import AnalysisRequest
from tradingagents.screener.schema import ScreenRunResult
from web.backend import app_config as backend_config, auth, main as backend_main, screener_results
from web.backend.routers import admin as admin_router
from web.backend.routers import config as config_router
from web.backend.routers import screeners as screeners_router
from web.backend.routers import tasks as tasks_router
from web.backend.runtime import analysis_tasks, screener_tasks, task_store
from web.backend.schemas.admin import AdminDataSourceUpdatePayload
from web.backend.schemas.screeners import ScreenTaskCreatePayload
from web.backend.schemas.tasks import TaskCreatePayload
from web.backend.schemas.ticker_history import (
    TickerHistoryBatchItemPayload,
    TickerHistoryBatchPayload,
)
from web.backend.services import config as config_service
from web.backend.services import reports as report_service
from web.backend.services import screeners as screener_service
from web.backend.services import ticker_history as ticker_history_service


class BackendMainTests(unittest.TestCase):
    def setUp(self):
        self.auth_env_patch = patch.dict(
            os.environ,
            {"AUTH_ENABLED": "false", "AUTH_MODE": "disabled"},
            clear=False,
        )
        self.auth_env_patch.start()
        auth.reset_runtime_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.empty_project_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = backend_config.REPORTS_DIR
        self.original_screener_results_dir = backend_config.SCREENER_RESULTS_DIR
        self.original_screener_state_dir = backend_config.SCREENER_STATE_DIR
        self.original_screener_tasks_dir = backend_config.SCREENER_TASKS_DIR
        self.original_screener_cache_dir = backend_config.SCREENER_CACHE_DIR
        self.original_stock_history_dir = backend_config.STOCK_HISTORY_DIR
        self.original_tmp_reports_dir = backend_config.TMP_REPORTS_DIR
        self.vendor_usage_env_patch = patch.dict(
            os.environ,
            {"DATA_SOURCE_USAGE_PATH": str(Path(self.temp_dir.name) / "vendor_usage.json")},
            clear=False,
        )
        self.vendor_usage_env_patch.start()
        vendor_usage.reset_data_source_usage_state()
        backend_config.REPORTS_DIR = Path(self.temp_dir.name) / "data" / "reports"
        backend_config.SCREENER_RESULTS_DIR = Path(self.temp_dir.name) / "data" / "screener" / "runs"
        backend_config.SCREENER_STATE_DIR = Path(self.temp_dir.name) / "data" / "screener" / "state"
        backend_config.SCREENER_TASKS_DIR = Path(self.temp_dir.name) / "data" / "screener" / "tasks"
        backend_config.SCREENER_CACHE_DIR = Path(self.temp_dir.name) / "data" / "cache" / "screener"
        backend_config.STOCK_HISTORY_DIR = Path(self.temp_dir.name) / "data" / "history"
        backend_config.TMP_REPORTS_DIR = backend_config.REPORTS_DIR / ".tmp"
        self.empty_project_root = Path(self.empty_project_dir.name)
        self.empty_project_env = self.empty_project_root / ".env"
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()

    def tearDown(self):
        backend_config.REPORTS_DIR = self.original_reports_dir
        backend_config.SCREENER_RESULTS_DIR = self.original_screener_results_dir
        backend_config.SCREENER_STATE_DIR = self.original_screener_state_dir
        backend_config.SCREENER_TASKS_DIR = self.original_screener_tasks_dir
        backend_config.SCREENER_CACHE_DIR = self.original_screener_cache_dir
        backend_config.STOCK_HISTORY_DIR = self.original_stock_history_dir
        backend_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        screener_results.reset_screener_result_observability()
        vendor_usage.reset_data_source_usage_state()
        self.vendor_usage_env_patch.stop()
        auth.reset_runtime_state()
        self.auth_env_patch.stop()
        self.empty_project_dir.cleanup()
        self.temp_dir.cleanup()

    def _write_screener_run(
        self,
        run_id: str,
        *,
        rows: list[dict] | None = None,
        markets: list[str] | None = None,
        filtered_count_by_reason: dict[str, int] | None = None,
    ) -> Path:
        run_dir = backend_config.SCREENER_RESULTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        candidate_rows = rows or [
            {"symbol": "600519.SH", "market": "cn", "global_rank": 1, "total_score": 1.23},
            {"symbol": "AAPL", "market": "us", "global_rank": 2, "total_score": 0.91},
        ]
        headers = list(candidate_rows[0].keys())
        (run_dir / "candidates.csv").write_text(
            "\n".join(
                [
                    ",".join(headers),
                    *[
                        ",".join(str(row.get(header, "")) for header in headers)
                        for row in candidate_rows
                    ],
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "run_timestamp": run_id,
                    "as_of_date": "2026-03-24",
                    "config": {"markets": markets or ["cn", "us"]},
                    "candidate_count": len(candidate_rows),
                    "filtered_count_by_reason": filtered_count_by_reason or {},
                    "artifact_paths": {
                        "run_meta": str(run_dir / "run_meta.json"),
                        "candidates": str(run_dir / "candidates.csv"),
                    },
                }
            ),
            encoding="utf-8",
        )
        return run_dir

    def test_list_reports_ignores_tmp_directory(self):
        temp_report_dir = backend_config.REPORTS_DIR / ".tmp" / "task-123"
        temp_report_dir.mkdir(parents=True)
        (backend_config.REPORTS_DIR / ".tasks").mkdir(parents=True)
        (backend_config.REPORTS_DIR / ".trade_feedback").mkdir(parents=True)

        report_dir = backend_config.REPORTS_DIR / "SPY_20260305_155836"
        report_dir.mkdir(parents=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: SPY\n\nGenerated: 2026-03-05 15:58:40\n\n",
            encoding="utf-8",
        )

        reports = report_service.list_reports()

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["id"], "SPY_20260305_155836")

    def test_resolve_report_dir_rejects_tmp_report_id(self):
        with self.assertRaises(HTTPException) as context:
            report_service.resolve_report_dir(".tmp")

        self.assertEqual(context.exception.status_code, 404)

    def test_resolve_report_dir_rejects_hidden_trade_feedback_directory(self):
        with self.assertRaises(HTTPException) as context:
            report_service.resolve_report_dir(".trade_feedback")

        self.assertEqual(context.exception.status_code, 404)

    def test_post_tasks_creates_a_pending_task_and_status_endpoint(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
            "market_data_source": "massive",
        }

        self.empty_project_env.write_text(
            "OPENAI_API_KEY=test-openai-key\n",
            encoding="utf-8",
        )

        with (
            patch("web.backend.runtime.analysis_tasks.start_task_thread") as start_task_thread,
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            body = tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(body["status"], "pending")
        start_task_thread.assert_called_once()

        task_status = tasks_router.get_task_status(body["task_id"])
        self.assertEqual(task_status["status"], "pending")
        self.assertEqual(task_status["request_payload"]["ticker"], "SPY")
        self.assertEqual(task_status["request_payload"]["analysts"], ["market", "news"])
        self.assertEqual(task_status["request_payload"]["llm_provider"], "openai")
        self.assertEqual(task_status["request_payload"]["market_data_source"], "massive")

        snapshot_path = analysis_tasks.task_snapshot_path(body["task_id"])
        self.assertTrue(snapshot_path.is_file())
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["status"], "pending")
        self.assertEqual(snapshot["ticker"], "SPY")

    def test_post_tasks_normalizes_non_trading_analysis_date(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2024-03-17",
            "analysts": ["market"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
            "market_data_source": "massive",
        }
        self.empty_project_env.write_text(
            "OPENAI_API_KEY=test-openai-key\n",
            encoding="utf-8",
        )

        with (
            patch("web.backend.runtime.analysis_tasks.start_task_thread"),
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            body = tasks_router.create_task(TaskCreatePayload(**payload))

        task_status = tasks_router.get_task_status(body["task_id"])
        self.assertEqual(task_status["request_payload"]["analysis_date"], "2024-03-15")

    def test_post_tasks_rejects_path_ticker_before_queueing(self):
        payload = {
            "ticker": "../../ESCAPE",
            "analysis_date": "2026-03-13",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }

        with patch("web.backend.runtime.analysis_tasks.start_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("path", context.exception.detail.lower())
        start_task_thread.assert_not_called()
        self.assertFalse((backend_config.REPORTS_DIR.parent / "ESCAPE").exists())

    def test_redis_task_submission_uses_per_user_limit_not_global_active_count(self):
        fake_store = task_store.InMemoryTaskStore()
        for index in range(5):
            fake_store.save_task(
                "analysis",
                f"operator-one-{index}",
                {
                    "id": f"operator-one-{index}",
                    "status": "queued",
                    "owner_user_id": "operator-one",
                    "request_payload": {
                        "ticker": "SPY",
                        "analysis_date": "2026-03-13",
                        "analysts": ["market"],
                        "research_depth": 1,
                        "llm_provider": "openai",
                        "quick_think_llm": "gpt-5-mini",
                        "deep_think_llm": "gpt-5.2",
                        "output_language": "en",
                        "openai_reasoning_effort": "medium",
                        "google_thinking_level": None,
                    },
                },
                enqueue=False,
            )

        payload = {
            "ticker": "AAPL",
            "analysis_date": "2026-03-13",
            "analysts": ["market"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }

        def user(user_id: str):
            return SimpleNamespace(id=user_id, role=auth.UserRole.OPERATOR.value)

        with (
            patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
            patch("web.backend.runtime.task_store.get_task_store", return_value=fake_store),
            patch("web.backend.routers.tasks.hydrate_provider_credentials"),
            patch(
                "web.backend.routers.tasks.get_provider_availability",
                return_value={"enabled": True, "disabled_reason": None},
            ),
            patch("web.backend.routers.tasks.auth.db_session", return_value=contextlib.nullcontext()),
            patch("web.backend.routers.tasks.auth.get_user_by_id", return_value=user("operator-one")),
            patch("web.backend.routers.tasks.analysis_limits.record_analysis_task_creation"),
            patch("web.backend.routers.tasks.asset_service.build_portfolio_context_for_owner", return_value=None),
            patch("web.backend.routers.tasks._current_user", return_value=user("operator-one")),
        ):
            with self.assertRaises(HTTPException) as context:
                tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("user", context.exception.detail.lower())

        with (
            patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
            patch("web.backend.runtime.task_store.get_task_store", return_value=fake_store),
            patch("web.backend.routers.tasks.hydrate_provider_credentials"),
            patch(
                "web.backend.routers.tasks.get_provider_availability",
                return_value={"enabled": True, "disabled_reason": None},
            ),
            patch("web.backend.routers.tasks.auth.db_session", return_value=contextlib.nullcontext()),
            patch("web.backend.routers.tasks.auth.get_user_by_id", return_value=user("operator-two")),
            patch("web.backend.routers.tasks.analysis_limits.record_analysis_task_creation"),
            patch("web.backend.routers.tasks.asset_service.build_portfolio_context_for_owner", return_value=None),
            patch("web.backend.routers.tasks._current_user", return_value=user("operator-two")),
        ):
            body = tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(body["status"], "queued")

    def test_report_output_dir_rejects_paths_outside_reports_root(self):
        with self.assertRaises(ValueError):
            analysis_tasks.report_output_dir("../../ESCAPE")

    def test_terminal_task_status_removes_persisted_active_snapshot(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }
        task = analysis_tasks.Task(
            id="task-terminal",
            request=AnalysisRequest(**payload),
            status="running",
        )
        analysis_tasks.tasks[task.id] = task

        analysis_tasks.persist_task_snapshot(task.id)
        self.assertTrue(analysis_tasks.task_snapshot_path(task.id).is_file())

        analysis_tasks.set_task_status(task.id, "completed")

        self.assertFalse(analysis_tasks.task_snapshot_path(task.id).exists())

    def test_run_analysis_task_hides_internal_failure_detail(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }
        task = analysis_tasks.Task(
            id="task-failed-analysis",
            request=AnalysisRequest(**payload),
            status="pending",
        )
        analysis_tasks.tasks[task.id] = task

        with patch(
            "web.backend.runtime.analysis_tasks.run_analysis_streaming",
            side_effect=RuntimeError("secret /tmp/provider-token"),
        ):
            analysis_tasks.run_task(task.id)

        task_status = tasks_router.get_task_status(task.id)
        self.assertEqual(task_status["status"], "failed")
        self.assertEqual(
            task_status["error"],
            analysis_tasks.GENERIC_ANALYSIS_TASK_ERROR,
        )
        self.assertNotIn("secret", task_status["latest_progress"]["message"])

    def test_restore_persisted_active_tasks_marks_running_tasks_failed(self):
        task_dir = analysis_tasks.task_snapshot_path("task-recover").parent
        task_dir.mkdir(parents=True, exist_ok=True)
        analysis_tasks.task_snapshot_path("task-recover").write_text(
            json.dumps(
                {
                    "id": "task-recover",
                    "ticker": "SPY",
                    "analysis_date": "2026-03-13",
                    "analysts": ["market", "news"],
                    "request_payload": {
                        "ticker": "SPY",
                        "analysis_date": "2026-03-13",
                        "analysts": ["market", "news"],
                        "research_depth": 1,
                        "llm_provider": "openai",
                        "quick_think_llm": "gpt-5-mini",
                        "deep_think_llm": "gpt-5.2",
                        "output_language": "en",
                        "openai_reasoning_effort": "medium",
                        "google_thinking_level": None,
                    },
                    "status": "running",
                    "latest_progress": None,
                    "report_id": None,
                    "error": None,
                }
            ),
            encoding="utf-8",
        )

        analysis_tasks.restore_persisted_active_tasks()

        restored = tasks_router.get_task_status("task-recover")
        self.assertEqual(restored["status"], "failed")
        self.assertIn("restarted", restored["error"].lower())
        self.assertFalse(analysis_tasks.task_snapshot_path("task-recover").exists())

    def test_api_lifespan_skips_task_recovery_when_redis_worker_is_enabled(self):
        async def run_lifespan():
            async with backend_main._app_lifespan(backend_main.app):
                pass

        with (
            patch("web.backend.runtime.task_store.redis_task_backend_enabled", return_value=True),
            patch("web.backend.main.restore_persisted_active_tasks") as restore_analysis,
            patch("web.backend.main.restore_persisted_screener_tasks") as restore_screener,
        ):
            asyncio.run(run_lifespan())

        restore_analysis.assert_not_called()
        restore_screener.assert_not_called()

    def test_post_tasks_rejects_when_two_active_tasks_already_exist(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }
        request = AnalysisRequest(**payload)
        analysis_tasks.tasks["task-one"] = analysis_tasks.Task(
            id="task-one",
            request=request,
            status="running",
        )
        analysis_tasks.tasks["task-two"] = analysis_tasks.Task(
            id="task-two",
            request=request,
            status="pending",
        )

        self.empty_project_env.write_text(
            "OPENAI_API_KEY=test-openai-key\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            with self.assertRaises(HTTPException) as context:
                tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("queue", context.exception.detail.lower())

    def test_post_screener_tasks_creates_a_pending_task(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "cn_data_source": "akshare",
        }

        with patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread:
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        self.assertEqual(body["status"], "pending")
        start_task_thread.assert_called_once()

        task_status = screeners_router.get_screener_task_status(body["task_id"])
        self.assertEqual(task_status["status"], "pending")
        self.assertEqual(task_status["request_payload"]["markets"], ["cn"])
        self.assertEqual(task_status["request_payload"]["cn_data_source"], "tushare")
        self.assertEqual(task_status["request_payload"]["us_data_source"], "massive")
        self.assertEqual(task_status["config_payload"]["cn_data_source"], "tushare")
        self.assertEqual(task_status["config_payload"]["us_data_source"], "massive")
        self.assertNotIn("limit_per_market", task_status["request_payload"])
        self.assertNotIn("limit_per_market", task_status["config_payload"])

    def test_post_screener_tasks_forces_fixed_sources_for_us_market(self):
        payload = {
            "markets": ["us"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "cn_data_source": "akshare",
            "us_data_source": "alpha_vantage",
        }

        with (
            patch.dict(os.environ, {"SCREEN_US_MANIFEST_PATH": "/tmp/us.csv"}, clear=False),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread,
        ):
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        start_task_thread.assert_called_once()
        task_status = screeners_router.get_screener_task_status(body["task_id"])
        self.assertEqual(task_status["request_payload"]["cn_data_source"], "tushare")
        self.assertEqual(task_status["request_payload"]["us_data_source"], "massive")
        self.assertEqual(task_status["config_payload"]["cn_data_source"], "tushare")
        self.assertEqual(task_status["config_payload"]["us_data_source"], "massive")

    def test_get_screener_config_options_exposes_market_data_source_choices(self):
        payload = config_service.get_screener_config_options_payload()

        self.assertEqual(payload["defaults"]["cn_data_source"], "tushare")
        self.assertEqual(payload["defaults"]["us_data_source"], "massive")
        self.assertNotIn("limit_per_market", payload["defaults"])
        self.assertEqual(
            [option["value"] for option in payload["cn_data_sources"]],
            ["tushare"],
        )
        self.assertEqual(
            [option["value"] for option in payload["us_data_sources"]],
            ["massive"],
        )

    def test_get_config_options_uses_automatic_analysis_market_data_routing(self):
        payload = config_service.get_config_options_payload()

        self.assertNotIn("market_data_sources", payload)
        self.assertNotIn("market_data_source", payload["defaults"])

    def test_admin_data_source_usage_endpoint_reports_and_updates_vendor_state(self):
        vendor_usage.record_data_source_call(
            "alpha_vantage",
            module="analysis",
            success=True,
        )

        payload = admin_router.list_admin_data_sources()
        sources = {source["vendor"]: source for source in payload["sources"]}
        routes = {
            (route["module"], route["market"], route["category"]): route
            for route in payload["routes"]
        }

        self.assertEqual(sources["alpha_vantage"]["daily_limit"], 25)
        self.assertIsNone(sources["alpha_vantage"]["hourly_limit"])
        self.assertEqual(sources["alpha_vantage"]["used_today"], 1)
        self.assertEqual(sources["alpha_vantage"]["used_this_hour"], 1)
        self.assertEqual(
            sources["alpha_vantage"]["modules"]["analysis"]["total_calls"],
            1,
        )
        self.assertEqual(
            routes[("screener", "us", "core_stock_apis")]["vendor_chain"],
            ["massive"],
        )

        updated = admin_router.update_admin_data_source(
            "alpha_vantage",
            AdminDataSourceUpdatePayload(enabled=False, daily_limit=25, hourly_limit=5),
        )

        self.assertFalse(updated["source"]["enabled"])
        self.assertEqual(updated["source"]["hourly_limit"], 5)
        self.assertFalse(vendor_usage.is_data_source_available("alpha_vantage"))

    def test_admin_task_queue_endpoint_lists_active_tasks_with_owner_details(self):
        fake_store = task_store.InMemoryTaskStore()
        fake_store.save_task(
            "analysis",
            "analysis-queued",
            {
                "id": "analysis-queued",
                "ticker": "AAPL",
                "status": "queued",
                "owner_user_id": "user-1",
                "created_at": "2026-04-26T01:00:00+00:00",
                "queued_at": "2026-04-26T01:01:00+00:00",
            },
            enqueue=True,
        )
        fake_store.save_task(
            "analysis",
            "analysis-running",
            {
                "id": "analysis-running",
                "ticker": "MSFT",
                "status": "running",
                "owner_user_id": "user-2",
                "started_at": "2026-04-26T01:05:00+00:00",
            },
            enqueue=False,
        )
        fake_store.save_task(
            "screener",
            "screener-waiting",
            {
                "id": "screener-waiting",
                "request_payload": {
                    "markets": ["us", "cn"],
                    "as_of_date": "2026-04-26",
                },
                "status": "waiting_for_quota",
                "owner_user_id": "user-1",
                "blocked_vendor": "alpha_vantage",
                "blocked_until": "2026-04-27T00:00:00+00:00",
            },
            enqueue=False,
        )

        users = [
            SimpleNamespace(
                id="user-1",
                email="operator@example.com",
                display_name="Operator",
                role="operator",
            ),
            SimpleNamespace(
                id="user-2",
                email="viewer@example.com",
                display_name="Viewer",
                role="viewer",
            ),
        ]

        with (
            patch.dict(os.environ, {"TASK_BACKEND": "redis"}, clear=False),
            patch("web.backend.runtime.task_store.get_task_store", return_value=fake_store),
            patch("web.backend.routers.admin.auth.db_session", return_value=contextlib.nullcontext(object())),
            patch("web.backend.routers.admin.auth.list_users", return_value=users),
            patch(
                "web.backend.routers.admin.auth.serialize_user",
                side_effect=lambda user: {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.display_name,
                    "role": user.role,
                },
            ),
        ):
            payload = admin_router.list_admin_task_queue()

        self.assertEqual(payload["task_backend"], "redis")
        self.assertEqual(payload["totals"]["active"], 3)
        self.assertEqual(payload["totals"]["queued"], 1)
        self.assertEqual(payload["totals"]["running"], 1)
        self.assertEqual(payload["totals"]["waiting_for_quota"], 1)
        items = {item["task_id"]: item for item in payload["tasks"]}
        self.assertEqual(items["analysis-queued"]["kind"], "analysis")
        self.assertEqual(items["analysis-queued"]["label"], "AAPL")
        self.assertEqual(items["analysis-queued"]["queue_position"], 1)
        self.assertEqual(items["analysis-queued"]["owner"]["email"], "operator@example.com")
        self.assertEqual(items["analysis-running"]["owner"]["role"], "viewer")
        self.assertEqual(items["screener-waiting"]["label"], "us, cn")
        self.assertEqual(items["screener-waiting"]["blocked_vendor"], "alpha_vantage")

    def test_delete_failed_analysis_task_removes_local_record(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }
        task = analysis_tasks.Task(
            id="task-failed-delete",
            request=AnalysisRequest(**payload),
            status="failed",
            error="boom",
        )
        analysis_tasks.tasks[task.id] = task

        body = tasks_router.delete_task(task.id)

        self.assertEqual(body, {"deleted": True, "task_id": task.id})
        with self.assertRaises(HTTPException) as context:
            tasks_router.get_task_status(task.id)
        self.assertEqual(context.exception.status_code, 404)

    def test_delete_running_analysis_task_is_rejected(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }
        task = analysis_tasks.Task(
            id="task-running-delete",
            request=AnalysisRequest(**payload),
            status="running",
        )
        analysis_tasks.tasks[task.id] = task

        with self.assertRaises(HTTPException) as context:
            tasks_router.delete_task(task.id)

        self.assertEqual(context.exception.status_code, 409)

    def test_delete_failed_screener_task_removes_local_record(self):
        task = screener_tasks.ScreenerTask(
            id="screener-failed-delete",
            request_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
            config_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
            status="failed",
            error="boom",
        )
        screener_tasks.screener_tasks[task.id] = task

        body = screeners_router.delete_screener_task(task.id)

        self.assertEqual(body, {"deleted": True, "task_id": task.id})
        with self.assertRaises(HTTPException) as context:
            screeners_router.get_screener_task_status(task.id)
        self.assertEqual(context.exception.status_code, 404)

    def test_post_screener_tasks_forces_us_data_source_selection(self):
        payload = {
            "markets": ["us"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "us_data_source": "alpha_vantage",
        }

        with (
            patch.dict(os.environ, {"SCREEN_US_MANIFEST_PATH": "/tmp/us_manifest.csv"}, clear=True),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread,
        ):
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        self.assertEqual(body["status"], "pending")
        start_task_thread.assert_called_once()

        task_status = screeners_router.get_screener_task_status(body["task_id"])
        self.assertEqual(task_status["request_payload"]["markets"], ["us"])
        self.assertEqual(task_status["request_payload"]["us_data_source"], "massive")
        self.assertEqual(task_status["config_payload"]["us_data_source"], "massive")
        self.assertEqual(task_status["config_payload"]["us_manifest_path"], "/tmp/us_manifest.csv")

    def test_post_screener_tasks_injects_backend_cn_manifest_when_configured(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }

        with patch.dict(
            os.environ,
            {"SCREEN_CN_MANIFEST_PATH": "/tmp/cn_manifest.csv"},
            clear=True,
        ):
            with patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread:
                body = screeners_router.create_screener_task(
                    ScreenTaskCreatePayload(**payload)
                )

        self.assertEqual(body["status"], "pending")
        start_task_thread.assert_called_once()

        task_status = screeners_router.get_screener_task_status(body["task_id"])
        self.assertEqual(task_status["request_payload"]["markets"], ["cn"])
        self.assertNotIn("cn_manifest_path", task_status["request_payload"])
        self.assertEqual(
            task_status["config_payload"]["cn_manifest_path"],
            "/tmp/cn_manifest.csv",
        )

    def test_post_screener_tasks_rejects_us_market_without_backend_manifest(self):
        payload = {
            "markets": ["us"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as context:
                screeners_router.create_screener_task(
                    ScreenTaskCreatePayload(**payload)
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("SCREEN_US_MANIFEST_PATH", context.exception.detail)

    def test_post_screener_tasks_rejects_when_combined_queue_limit_is_full(self):
        analysis_request = AnalysisRequest(
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
        analysis_tasks.tasks["task-one"] = analysis_tasks.Task(
            id="task-one",
            request=analysis_request,
            status="running",
        )
        analysis_tasks.tasks["task-two"] = analysis_tasks.Task(
            id="task-two",
            request=analysis_request,
            status="pending",
        )

        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }
        with self.assertRaises(HTTPException) as context:
            screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("queue", context.exception.detail.lower())

    def test_list_screener_runs_reads_run_meta_files(self):
        self._write_screener_run("20260324_214530")
        screener_results.migrate_legacy_screener_results(force=True)

        runs = screener_service.list_screener_runs()

        self.assertEqual(runs[0]["id"], "20260324_214530")
        self.assertEqual(runs[0]["markets"], ["cn", "us"])
        self.assertEqual(runs[0]["candidate_count"], 2)
        self.assertEqual(runs[0]["snapshot_slot"], "current")

    def test_get_screener_run_candidates_reads_candidates_csv(self):
        self._write_screener_run("20260324_214530")
        screener_results.migrate_legacy_screener_results(force=True)

        rows = screener_service.get_screener_run_candidates("20260324_214530")

        self.assertEqual(rows[0]["symbol"], "600519.SH")
        self.assertEqual(rows[1]["market"], "us")

    def test_get_ticker_history_payload_reads_cached_series_and_infers_market(self):
        cache_path = (
            backend_config.STOCK_HISTORY_DIR
            / "us"
            / "AAPL.csv"
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            (
                "Date,Open,High,Low,Close,Volume,Amount\n"
                "2025-02-17,180,184,179,182,900,163800\n"
                "2026-03-21,210,214,209,213,1000,213000\n"
                "2026-03-24,214,216,213,215,1200,258000\n"
            ),
            encoding="utf-8",
        )

        payload = ticker_history_service.get_ticker_history_payload("AAPL", as_of_date="2026-03-24")

        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["market"], "us")
        self.assertEqual(payload["as_of_date"], "2026-03-24")
        self.assertEqual(payload["start_date"], "2025-02-17")
        self.assertEqual(payload["end_date"], "2026-03-24")
        self.assertEqual(len(payload["points"]), 3)
        self.assertEqual(payload["points"][1]["close"], 213.0)
        self.assertEqual(payload["points"][2]["open"], 214.0)

    def test_get_batch_ticker_history_payload_returns_compact_points(self):
        cache_path = (
            backend_config.STOCK_HISTORY_DIR
            / "cn"
            / "600519.SH.csv"
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            (
                "Date,Open,High,Low,Close,Volume,Amount\n"
                "2025-02-17,1290,1302,1285,1298,880,1142240\n"
                "2026-03-21,1500,1510,1492,1508,1000,1508000\n"
                "2026-03-24,1512,1520,1501,1519,1200,1822800\n"
            ),
            encoding="utf-8",
        )

        payload = ticker_history_service.get_batch_ticker_history_payload(
            TickerHistoryBatchPayload(
                tickers=[TickerHistoryBatchItemPayload(symbol="600519.SH", market="cn")],
                as_of_date="2026-03-24",
            )
        )

        self.assertEqual(payload["as_of_date"], "2026-03-24")
        self.assertEqual(payload["items"][0]["symbol"], "600519.SH")
        self.assertEqual(payload["items"][0]["market"], "cn")
        self.assertEqual(payload["items"][0]["points"][1]["close"], 1508.0)
        self.assertNotIn("open", payload["items"][0]["points"][0])

    def test_get_batch_ticker_history_payload_rejects_empty_items(self):
        with self.assertRaises(HTTPException) as context:
            ticker_history_service.get_batch_ticker_history_payload(
                TickerHistoryBatchPayload(tickers=[], as_of_date="2026-03-24")
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("tickers", context.exception.detail.lower())

    def test_run_screener_task_marks_failed_stage_as_not_processing(self):
        screener_results.persist_screener_run(
            SimpleNamespace(
                request_payload={"markets": ["cn"], "as_of_date": "2026-03-24"},
                owner_user_id=None,
            ),
            screener_results.ScreenerResultCandidate(
                source_run_id="20260324_214530",
                generated_at="20260324_214530",
                as_of_date="2026-03-24",
                markets=["cn"],
                universe_count=20,
                match_count=1,
                filtered_count_by_reason={},
                artifact_paths={"candidates": "runs/20260324_214530/candidates.csv"},
                rows=[
                    {
                        "symbol": "600519.SH",
                        "market": "cn",
                        "global_rank": 1,
                        "total_score": 0.91,
                    }
                ],
                manifest_version="manifest-v1",
                logic_version="logic-v1",
                duration_ms=1000,
            ),
        )
        task = screener_tasks.ScreenerTask(
            id="task-failed-screener",
            request_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
            config_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
        )
        screener_tasks.screener_tasks[task.id] = task

        with patch("web.backend.runtime.screener_tasks.run_screen", side_effect=ValueError("boom")):
            screener_tasks.run_screener_task(task.id)

        task_status = screeners_router.get_screener_task_status(task.id)
        self.assertEqual(task_status["status"], "failed")
        self.assertEqual(
            task_status["latest_progress"]["stage_status"],
            {
                "Universe": "not_started",
                "History": "not_started",
                "Features": "not_started",
                "Filters": "not_started",
                "Ranking": "not_started",
                "Export": "not_started",
            },
        )
        self.assertEqual(
            task_status["error"],
            screener_tasks.GENERIC_SCREENER_TASK_ERROR,
        )
        self.assertNotIn("boom", task_status["latest_progress"]["message"])

        state = screener_results.load_screener_result_state()
        self.assertEqual(state.current_result.source_run_id, "20260324_214530")
        self.assertIsNone(state.previous_result)
        self.assertEqual(state.recent_runs[0].status, "failed")
        self.assertEqual(
            state.recent_runs[0].error_summary,
            screener_tasks.GENERIC_SCREENER_TASK_ERROR,
        )
        self.assertFalse(state.recent_runs[0].snapshot_available)

    def test_run_screener_task_accepts_extended_progress_callback_signature(self):
        task = screener_tasks.ScreenerTask(
            id="task-progress-screener",
            request_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
            config_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
        )
        screener_tasks.screener_tasks[task.id] = task

        def fake_run_screen(config, progress_callback=None):
            assert progress_callback is not None
            progress_callback(
                "history",
                1,
                2,
                "600519.SH",
                status="cache_hit",
                detail="cache=2025-02-17..2026-03-24",
            )
            return ScreenRunResult(
                run_dir=run_dir,
                universe_count_by_market={"cn": 1},
                fetch_failed_count=0,
                filtered_count_by_reason={},
                candidate_count=1,
                candidate_preview=[],
            )

        run_dir = self._write_screener_run(
            "20260324_214530",
            rows=[{"symbol": "600519.SH", "market": "cn", "global_rank": 1, "total_score": 0.91}],
            markets=["cn"],
        )
        with patch("web.backend.runtime.screener_tasks.run_screen", side_effect=fake_run_screen):
            screener_tasks.run_screener_task(task.id)

        task_status = screeners_router.get_screener_task_status(task.id)
        self.assertEqual(task_status["status"], "completed")
        self.assertIn("cache_hit", task_status["progress_events"][0]["message"])
        self.assertIn("600519.SH", task_status["progress_events"][0]["message"])

    def test_screener_task_stream_starts_from_cursor(self):
        task = screener_tasks.ScreenerTask(
            id="task-stream-cursor",
            request_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
            config_payload={
                "markets": ["cn"],
                "as_of_date": "2026-03-24",
                "top_k": 20,
                "cn_data_source": "akshare",
            },
            status="failed",
            latest_progress={"timestamp": "10:00:01", "status": "failed", "message": "new"},
            progress_events=[
                {"timestamp": "10:00:00", "status": "running", "message": "old"},
                {"timestamp": "10:00:01", "status": "failed", "message": "new"},
            ],
        )
        screener_tasks.screener_tasks[task.id] = task

        class RequestStub:
            async def is_disconnected(self):
                return False

        async def render_stream() -> str:
            response = await screeners_router.stream_screener_task(
                task.id,
                RequestStub(),
                cursor=1,
            )
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
            return "".join(chunks)

        body = asyncio.run(render_stream())
        self.assertIn("new", body)
        self.assertNotIn("old", body)

    def test_post_screener_tasks_rejects_empty_markets_before_queueing(self):
        payload = {
            "markets": [],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }

        with patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                screeners_router.create_screener_task(
                    ScreenTaskCreatePayload(**payload)
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("markets", context.exception.detail.lower())
        start_task_thread.assert_not_called()

    def test_post_screener_tasks_rejects_non_positive_top_k_before_queueing(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 0,
        }

        with patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                screeners_router.create_screener_task(
                    ScreenTaskCreatePayload(**payload)
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("top_k", context.exception.detail.lower())
        start_task_thread.assert_not_called()

    def test_post_screener_tasks_rejects_invalid_as_of_date_before_queueing(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "03/24/2026",
            "top_k": 20,
        }

        with patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                screeners_router.create_screener_task(
                    ScreenTaskCreatePayload(**payload)
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("as_of_date", context.exception.detail.lower())
        start_task_thread.assert_not_called()

    def test_post_tasks_rejects_unconfigured_provider(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2026-03-13",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "xiaohumini",
            "quick_think_llm": "gpt-5.3-chat-latest",
            "deep_think_llm": "gpt-5.4",
            "output_language": "en",
            "openai_reasoning_effort": None,
            "google_thinking_level": None,
        }

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            with self.assertRaises(HTTPException) as context:
                tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("API key", context.exception.detail)

    def test_config_options_expose_shared_provider_and_model_choices(self):
        payload = config_router.get_config_options()
        provider_values = {provider["value"] for provider in payload["providers"]}

        self.assertIn("openai", provider_values)
        self.assertIn("google", provider_values)
        self.assertIn("siliconflow", provider_values)
        self.assertIn("sub2api", provider_values)
        self.assertIn("balanced", {option["value"] for option in payload["model_profiles"]})
        self.assertIn("custom", {option["value"] for option in payload["model_profiles"]})
        self.assertIn("market", {option["value"] for option in payload["analysts"]})
        self.assertIn("gpt-5-mini", {option["value"] for option in payload["models"]["openai"]["quick"]})
        self.assertIn("gpt-5.4", {option["value"] for option in payload["models"]["sub2api"]["deep"]})
        self.assertIn(
            "deepseek-ai/DeepSeek-V4-Flash",
            {option["value"] for option in payload["models"]["siliconflow"]["quick"]},
        )
        self.assertIn(
            "Pro/zai-org/GLM-5.1",
            {option["value"] for option in payload["models"]["siliconflow"]["deep"]},
        )
        self.assertIn(
            "deepseek-v4-flash",
            {option["value"] for option in payload["models"]["deepseek"]["quick"]},
        )
        self.assertIn(
            "deepseek-v4-pro",
            {option["value"] for option in payload["models"]["deepseek"]["deep"]},
        )

    def test_create_task_accepts_model_profile_payload(self):
        payload = {
            "ticker": "SPY",
            "analysis_date": "2024-03-15",
            "analysts": ["market"],
            "research_depth": 1,
            "model_profile": "balanced",
            "output_language": "en",
            "report_visibility": "private",
        }

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=False),
            patch.object(tasks_router.analysis_tasks, "create_task") as create_task,
        ):
            create_task.return_value = {"task_id": "task-profile", "status": "pending"}
            response = tasks_router.create_task(TaskCreatePayload(**payload))

        self.assertEqual(response["task_id"], "task-profile")
        analysis_request = create_task.call_args.args[0]
        self.assertEqual(analysis_request.model_profile, "balanced")
        self.assertEqual(analysis_request.llm_provider, "openai")
        self.assertEqual(analysis_request.quick_think_llm, "gpt-5.4-mini")

    def test_config_options_mark_provider_availability_from_project_env_file(self):
        self.empty_project_env.write_text(
            "OPENAI_API_KEY=test-openai-key\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            payload = config_service.get_config_options_payload()

        providers = {provider["value"]: provider for provider in payload["providers"]}

        self.assertTrue(providers["openai"]["enabled"])
        self.assertFalse(providers["siliconflow"]["enabled"])
        self.assertFalse(providers["sub2api"]["enabled"])
        self.assertFalse(providers["xiaohumini"]["enabled"])
        self.assertIn("API key", providers["xiaohumini"]["disabled_reason"])

    def test_config_options_detect_provider_key_from_project_env_file(self):
        temp_project = tempfile.TemporaryDirectory()
        temp_project_path = Path(temp_project.name)
        (temp_project_path / ".env").write_text(
            "XIAOHUMINI_API_KEY=test-xiaohumini-key\n"
            "SILICONFLOW_API_KEY=test-siliconflow-key\n",
            encoding="utf-8",
        )

        try:
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(backend_config, "PROJECT_ROOT", temp_project_path),
                patch.object(backend_config, "PROJECT_ENV_FILE", temp_project_path / ".env"),
            ):
                payload = config_service.get_config_options_payload()
        finally:
            temp_project.cleanup()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertTrue(providers["xiaohumini"]["enabled"])
        self.assertTrue(providers["siliconflow"]["enabled"])

    def test_config_options_detect_sub2api_key_from_project_env_file(self):
        temp_project = tempfile.TemporaryDirectory()
        temp_project_path = Path(temp_project.name)
        (temp_project_path / ".env").write_text(
            "SUB2API_API_KEY=test-sub2api-key\n",
            encoding="utf-8",
        )

        try:
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(backend_config, "PROJECT_ROOT", temp_project_path),
                patch.object(backend_config, "PROJECT_ENV_FILE", temp_project_path / ".env"),
            ):
                payload = config_service.get_config_options_payload()
        finally:
            temp_project.cleanup()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertTrue(providers["sub2api"]["enabled"])

    def test_config_options_accept_process_env_without_project_env_value(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            payload = config_service.get_config_options_payload()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertTrue(providers["openai"]["enabled"])

    def test_config_options_treat_blank_project_env_value_as_unavailable(self):
        self.empty_project_env.write_text(
            "XIAOHUMINI_API_KEY=\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_config, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_config, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            payload = config_service.get_config_options_payload()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertFalse(providers["xiaohumini"]["enabled"])

    def test_frontend_origins_default_to_localhost_3000(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                backend_config.get_frontend_origins(),
                ["http://localhost:3000"],
            )

    def test_frontend_origins_use_frontend_origin_env(self):
        with patch.dict(
            os.environ,
            {"FRONTEND_ORIGIN": "https://reports.example.com, https://alt.example.com"},
            clear=True,
        ):
            self.assertEqual(
                backend_config.get_frontend_origins(),
                ["https://reports.example.com", "https://alt.example.com"],
            )


if __name__ == "__main__":
    unittest.main()
