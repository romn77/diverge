import tempfile
import unittest
import os
import json
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from tradingagents.runner import AnalysisRequest
from tradingagents.screener.schema import ScreenRunResult
from web.backend import main as backend_main


class BackendMainTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.empty_project_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = backend_main.REPORTS_DIR
        self.original_screener_results_dir = getattr(
            backend_main,
            "SCREENER_RESULTS_DIR",
            Path(self.temp_dir.name) / "screener",
        )
        backend_main.REPORTS_DIR = Path(self.temp_dir.name)
        backend_main.SCREENER_RESULTS_DIR = Path(self.temp_dir.name) / "screener"
        self.empty_project_root = Path(self.empty_project_dir.name)
        self.empty_project_env = self.empty_project_root / ".env"
        backend_main.tasks.clear()
        if hasattr(backend_main, "screener_tasks"):
            backend_main.screener_tasks.clear()

    def tearDown(self):
        backend_main.REPORTS_DIR = self.original_reports_dir
        backend_main.SCREENER_RESULTS_DIR = self.original_screener_results_dir
        backend_main.tasks.clear()
        if hasattr(backend_main, "screener_tasks"):
            backend_main.screener_tasks.clear()
        self.empty_project_dir.cleanup()
        self.temp_dir.cleanup()

    def test_list_reports_ignores_tmp_directory(self):
        temp_report_dir = backend_main.REPORTS_DIR / ".tmp" / "task-123"
        temp_report_dir.mkdir(parents=True)

        report_dir = backend_main.REPORTS_DIR / "SPY_20260305_155836"
        report_dir.mkdir(parents=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: SPY\n\nGenerated: 2026-03-05 15:58:40\n\n",
            encoding="utf-8",
        )

        reports = backend_main.list_reports()

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["id"], "SPY_20260305_155836")

    def test_resolve_report_dir_rejects_tmp_report_id(self):
        with self.assertRaises(HTTPException) as context:
            backend_main._resolve_report_dir(".tmp")

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
        }

        self.empty_project_env.write_text(
            "OPENAI_API_KEY=test-openai-key\n",
            encoding="utf-8",
        )

        with (
            patch("web.backend.main._start_task_thread") as start_task_thread,
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_main, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_main, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            body = backend_main.create_task(backend_main.TaskCreatePayload(**payload))

        self.assertEqual(body["status"], "pending")
        start_task_thread.assert_called_once()

        task_status = backend_main.get_task_status(body["task_id"])
        self.assertEqual(task_status["status"], "pending")
        self.assertEqual(task_status["request_payload"]["ticker"], "SPY")
        self.assertEqual(task_status["request_payload"]["analysts"], ["market", "news"])
        self.assertEqual(task_status["request_payload"]["llm_provider"], "openai")

        snapshot_path = backend_main._task_snapshot_path(body["task_id"])
        self.assertTrue(snapshot_path.is_file())
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["status"], "pending")
        self.assertEqual(snapshot["ticker"], "SPY")

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
        task = backend_main.Task(
            id="task-terminal",
            request=AnalysisRequest(**payload),
            status="running",
        )
        backend_main.tasks[task.id] = task

        backend_main._persist_task_snapshot(task.id)
        self.assertTrue(backend_main._task_snapshot_path(task.id).is_file())

        backend_main._set_task_status(task.id, "completed")

        self.assertFalse(backend_main._task_snapshot_path(task.id).exists())

    def test_restore_persisted_active_tasks_marks_running_tasks_failed(self):
        task_dir = backend_main._task_snapshot_path("task-recover").parent
        task_dir.mkdir(parents=True, exist_ok=True)
        backend_main._task_snapshot_path("task-recover").write_text(
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

        backend_main._restore_persisted_active_tasks()

        restored = backend_main.get_task_status("task-recover")
        self.assertEqual(restored["status"], "failed")
        self.assertIn("restarted", restored["error"].lower())
        self.assertFalse(backend_main._task_snapshot_path("task-recover").exists())

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
        backend_main.tasks["task-one"] = backend_main.Task(
            id="task-one",
            request=request,
            status="running",
        )
        backend_main.tasks["task-two"] = backend_main.Task(
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
            patch.object(backend_main, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_main, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            with self.assertRaises(HTTPException) as context:
                backend_main.create_task(backend_main.TaskCreatePayload(**payload))

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("queue", context.exception.detail.lower())

    def test_post_screener_tasks_creates_a_pending_task(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "cn_data_source": "akshare",
        }

        with patch("web.backend.main._start_screener_task_thread") as start_task_thread:
            body = backend_main.create_screener_task(
                backend_main.ScreenTaskCreatePayload(**payload)
            )

        self.assertEqual(body["status"], "pending")
        start_task_thread.assert_called_once()

        task_status = backend_main.get_screener_task_status(body["task_id"])
        self.assertEqual(task_status["status"], "pending")
        self.assertEqual(task_status["request_payload"]["markets"], ["cn"])
        self.assertEqual(task_status["request_payload"]["cn_data_source"], "akshare")
        self.assertEqual(task_status["config_payload"]["cn_data_source"], "akshare")
        self.assertNotIn("limit_per_market", task_status["request_payload"])
        self.assertNotIn("limit_per_market", task_status["config_payload"])

    def test_get_screener_config_options_exposes_cn_data_source_choices(self):
        payload = backend_main._get_screener_config_options_payload()

        self.assertEqual(payload["defaults"]["cn_data_source"], "tushare")
        self.assertNotIn("limit_per_market", payload["defaults"])
        self.assertEqual(
            [option["value"] for option in payload["cn_data_sources"]],
            ["tushare", "akshare"],
        )

    def test_post_screener_tasks_rejects_us_market_without_backend_manifest(self):
        payload = {
            "markets": ["us"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as context:
                backend_main.create_screener_task(
                    backend_main.ScreenTaskCreatePayload(**payload)
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
        backend_main.tasks["task-one"] = backend_main.Task(
            id="task-one",
            request=analysis_request,
            status="running",
        )
        backend_main.tasks["task-two"] = backend_main.Task(
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
            backend_main.create_screener_task(
                backend_main.ScreenTaskCreatePayload(**payload)
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("queue", context.exception.detail.lower())

    def test_list_screener_runs_reads_run_meta_files(self):
        run_dir = backend_main.SCREENER_RESULTS_DIR / "20260324_214530"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "run_timestamp": "20260324_214530",
                    "as_of_date": "2026-03-24",
                    "config": {"markets": ["cn", "us"]},
                    "candidate_count": 12,
                }
            ),
            encoding="utf-8",
        )

        runs = backend_main.list_screener_runs()

        self.assertEqual(runs[0]["id"], "20260324_214530")
        self.assertEqual(runs[0]["markets"], ["cn", "us"])
        self.assertEqual(runs[0]["candidate_count"], 12)

    def test_get_screener_run_candidates_reads_candidates_csv(self):
        run_dir = backend_main.SCREENER_RESULTS_DIR / "20260324_214530"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "candidates.csv").write_text(
            "symbol,market,global_rank,total_score\n600519.SH,cn,1,1.23\nAAPL,us,2,0.91\n",
            encoding="utf-8",
        )

        rows = backend_main.get_screener_run_candidates("20260324_214530")

        self.assertEqual(rows[0]["symbol"], "600519.SH")
        self.assertEqual(rows[1]["market"], "us")

    def test_run_screener_task_marks_failed_stage_as_not_processing(self):
        task = backend_main.ScreenerTask(
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
        backend_main.screener_tasks[task.id] = task

        with patch("web.backend.main.run_screen", side_effect=ValueError("boom")):
            backend_main._run_screener_task(task.id)

        task_status = backend_main.get_screener_task_status(task.id)
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
        self.assertIn("boom", task_status["error"])

    def test_run_screener_task_accepts_extended_progress_callback_signature(self):
        task = backend_main.ScreenerTask(
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
        backend_main.screener_tasks[task.id] = task

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
                run_dir=Path("/tmp/results/screener/20260324_214530"),
                universe_count_by_market={"cn": 1},
                fetch_failed_count=0,
                filtered_count_by_reason={},
                candidate_count=1,
                candidate_preview=[],
            )

        with patch("web.backend.main.run_screen", side_effect=fake_run_screen):
            backend_main._run_screener_task(task.id)

        task_status = backend_main.get_screener_task_status(task.id)
        self.assertEqual(task_status["status"], "completed")
        self.assertIn("cache_hit", task_status["progress_events"][0]["message"])
        self.assertIn("600519.SH", task_status["progress_events"][0]["message"])

    def test_post_screener_tasks_rejects_empty_markets_before_queueing(self):
        payload = {
            "markets": [],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }

        with patch("web.backend.main._start_screener_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                backend_main.create_screener_task(
                    backend_main.ScreenTaskCreatePayload(**payload)
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

        with patch("web.backend.main._start_screener_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                backend_main.create_screener_task(
                    backend_main.ScreenTaskCreatePayload(**payload)
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

        with patch("web.backend.main._start_screener_task_thread") as start_task_thread:
            with self.assertRaises(HTTPException) as context:
                backend_main.create_screener_task(
                    backend_main.ScreenTaskCreatePayload(**payload)
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
            patch.object(backend_main, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_main, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            with self.assertRaises(HTTPException) as context:
                backend_main.create_task(backend_main.TaskCreatePayload(**payload))

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("API key", context.exception.detail)

    def test_config_options_expose_shared_provider_and_model_choices(self):
        payload = backend_main.get_config_options()
        provider_values = {provider["value"] for provider in payload["providers"]}

        self.assertIn("openai", provider_values)
        self.assertIn("google", provider_values)
        self.assertIn("market", {option["value"] for option in payload["analysts"]})
        self.assertIn("gpt-5-mini", {option["value"] for option in payload["models"]["openai"]["quick"]})

    def test_config_options_mark_provider_availability_from_project_env_file(self):
        self.empty_project_env.write_text(
            "OPENAI_API_KEY=test-openai-key\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_main, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_main, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            payload = backend_main._get_config_options_payload()

        providers = {provider["value"]: provider for provider in payload["providers"]}

        self.assertTrue(providers["openai"]["enabled"])
        self.assertFalse(providers["xiaohumini"]["enabled"])
        self.assertIn("API key", providers["xiaohumini"]["disabled_reason"])

    def test_config_options_detect_provider_key_from_project_env_file(self):
        temp_project = tempfile.TemporaryDirectory()
        temp_project_path = Path(temp_project.name)
        (temp_project_path / ".env").write_text(
            "XIAOHUMINI_API_KEY=test-xiaohumini-key\n",
            encoding="utf-8",
        )

        try:
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(backend_main, "PROJECT_ROOT", temp_project_path),
                patch.object(backend_main, "PROJECT_ENV_FILE", temp_project_path / ".env"),
            ):
                payload = backend_main._get_config_options_payload()
        finally:
            temp_project.cleanup()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertTrue(providers["xiaohumini"]["enabled"])

    def test_config_options_ignore_process_env_without_project_env_value(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True),
            patch.object(backend_main, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_main, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            payload = backend_main._get_config_options_payload()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertFalse(providers["openai"]["enabled"])

    def test_config_options_treat_blank_project_env_value_as_unavailable(self):
        self.empty_project_env.write_text(
            "XIAOHUMINI_API_KEY=\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend_main, "PROJECT_ROOT", self.empty_project_root),
            patch.object(backend_main, "PROJECT_ENV_FILE", self.empty_project_env),
        ):
            payload = backend_main._get_config_options_payload()

        providers = {provider["value"]: provider for provider in payload["providers"]}
        self.assertFalse(providers["xiaohumini"]["enabled"])

    def test_frontend_origins_default_to_localhost_3000(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                backend_main._get_frontend_origins(),
                ["http://localhost:3000"],
            )

    def test_frontend_origins_use_frontend_origin_env(self):
        with patch.dict(
            os.environ,
            {"FRONTEND_ORIGIN": "https://reports.example.com, https://alt.example.com"},
            clear=True,
        ):
            self.assertEqual(
                backend_main._get_frontend_origins(),
                ["https://reports.example.com", "https://alt.example.com"],
            )


if __name__ == "__main__":
    unittest.main()
