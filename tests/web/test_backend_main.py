import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from tradingagents.runner import AnalysisRequest
from web.backend import main as backend_main


class BackendMainTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.empty_project_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = backend_main.REPORTS_DIR
        backend_main.REPORTS_DIR = Path(self.temp_dir.name)
        self.empty_project_root = Path(self.empty_project_dir.name)
        self.empty_project_env = self.empty_project_root / ".env"
        backend_main.tasks.clear()

    def tearDown(self):
        backend_main.REPORTS_DIR = self.original_reports_dir
        backend_main.tasks.clear()
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
