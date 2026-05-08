import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from diverge.runner import AnalysisProgress, AnalysisRequest
from diverge.research.search.schema import SearchResponse, SearchResult
from diverge.research.search.session import search_sessions
from web.backend import app_config, auth
from web.backend.runtime import analysis_tasks


class SearchEvidenceArtifactRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(
            os.environ,
            {"AUTH_ENABLED": "false", "AUTH_MODE": "disabled"},
            clear=False,
        )
        self.env_patch.start()
        auth.reset_runtime_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = app_config.REPORTS_DIR
        self.original_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        app_config.REPORTS_DIR = Path(self.temp_dir.name) / "reports"
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
        app_config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        analysis_tasks.tasks.clear()

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        analysis_tasks.tasks.clear()
        search_sessions.pop("task-search")
        search_sessions.pop("task-empty")
        auth.reset_runtime_state()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _request(self) -> AnalysisRequest:
        return AnalysisRequest(
            ticker="SPY",
            analysis_date="2024-03-15",
            analysts=["news"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

    def _install_task(self, task_id: str) -> None:
        analysis_tasks.tasks[task_id] = analysis_tasks.Task(
            id=task_id,
            request=self._request(),
            created_at="2026-05-08T00:00:00+00:00",
        )

    def _patch_report_writers(self):
        def save_report_to_disk(_final_state, ticker, save_path):
            save_path.mkdir(parents=True, exist_ok=True)
            (save_path / "complete_report.md").write_text(
                f"# Trading Analysis Report: {ticker}\n\n",
                encoding="utf-8",
            )
            (save_path / "artifacts").mkdir(exist_ok=True)
            return save_path / "complete_report.md"

        return patch.multiple(
            analysis_tasks,
            save_report_to_disk=save_report_to_disk,
            build_decision_card=lambda **_kwargs: SimpleNamespace(),
            save_decision_card=lambda *_args, **_kwargs: None,
        )

    def test_web_task_persists_search_evidence_and_cleans_session(self):
        self._install_task("task-search")

        def fake_run_analysis_streaming(
            request,
            temp_dir,
            *,
            reports_dir=None,
            visible_trade_ids=None,
            analysis_run_id=None,
        ):
            self.assertEqual(analysis_run_id, "task-search")
            session = search_sessions.create(
                analysis_run_id="task-search",
                ticker=request.ticker,
                analysis_date=request.analysis_date,
            )
            now = datetime(2026, 5, 8, tzinfo=timezone.utc)
            session.record(
                SearchResponse(
                    agent="News Analyst",
                    ticker=request.ticker,
                    analysis_date=request.analysis_date,
                    query="SPY latest news",
                    requested_at=now,
                    results=[
                        SearchResult(
                            id="r1",
                            provider="brave",
                            query="SPY latest news",
                            title="SPY news",
                            url="https://example.com/spy",
                            retrieved_at=now,
                        )
                    ],
                )
            )
            if False:
                yield AnalysisProgress(
                    timestamp="00:00:00",
                    status="running",
                    stage_status={},
                    agent_status={},
                    current_agent=None,
                )
            return {"final_trade_decision": "HOLD"}

        with (
            patch.object(analysis_tasks, "run_analysis_streaming", fake_run_analysis_streaming),
            self._patch_report_writers(),
        ):
            analysis_tasks.run_task("task-search")

        task = analysis_tasks.get_task("task-search")
        artifact_path = app_config.REPORTS_DIR / task.report_id / "artifacts" / "search_evidence.json"
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["type"], "search_evidence")
        self.assertEqual(payload["summary"]["call_count"], 1)
        self.assertIsNone(search_sessions.get("task-search"))

    def test_no_search_calls_do_not_create_search_evidence_artifact(self):
        self._install_task("task-empty")

        def fake_run_analysis_streaming(
            request,
            temp_dir,
            *,
            reports_dir=None,
            visible_trade_ids=None,
            analysis_run_id=None,
        ):
            self.assertEqual(analysis_run_id, "task-empty")
            search_sessions.create(
                analysis_run_id="task-empty",
                ticker=request.ticker,
                analysis_date=request.analysis_date,
            )
            if False:
                yield
            return {"final_trade_decision": "HOLD"}

        with (
            patch.object(analysis_tasks, "run_analysis_streaming", fake_run_analysis_streaming),
            self._patch_report_writers(),
        ):
            analysis_tasks.run_task("task-empty")

        task = analysis_tasks.get_task("task-empty")
        artifact_path = app_config.REPORTS_DIR / task.report_id / "artifacts" / "search_evidence.json"
        self.assertFalse(artifact_path.exists())
        self.assertIsNone(search_sessions.get("task-empty"))


if __name__ == "__main__":
    unittest.main()
