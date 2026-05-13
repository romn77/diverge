import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from diverge.runner import AnalysisRequest
from web.backend import app_config, report_metadata
from web.backend.services import report_publication


class ReportPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = app_config.REPORTS_DIR
        self.original_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        app_config.REPORTS_DIR = Path(self.temp_dir.name) / "reports"
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
        app_config.TMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        self.temp_dir.cleanup()

    def _request(self) -> AnalysisRequest:
        return AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-20",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

    def _write_minimal_report(self, _final_state, ticker, save_path):
        save_path.mkdir(parents=True, exist_ok=True)
        (save_path / "1_analysts").mkdir(parents=True, exist_ok=True)
        (save_path / "artifacts").mkdir(parents=True, exist_ok=True)
        (save_path / "complete_report.md").write_text(
            f"# Trading Analysis Report: {ticker}\n\n"
            "Generated: 2026-04-20 09:30:00\n\n",
            encoding="utf-8",
        )
        (save_path / "1_analysts" / "market.md").write_text(
            "# Market\n\nStable backdrop.",
            encoding="utf-8",
        )
        return save_path / "complete_report.md"

    def test_report_output_dir_rejects_paths_outside_reports_root(self):
        with self.assertRaises(ValueError):
            report_publication.report_output_dir("../../ESCAPE")

    def test_publish_analysis_report_moves_temp_dir_behind_single_interface(self):
        temp_report_dir = app_config.TMP_REPORTS_DIR / "task-1"
        events = []

        def check_canceled():
            events.append("check")

        def write_search_evidence(task_id, report_dir):
            events.append(("search", task_id, report_dir))
            return None

        def build_decision_card(**kwargs):
            events.append(("decision", kwargs["report_id"]))
            return SimpleNamespace(kind="decision")

        adapters = report_publication.ReportPublicationAdapters(
            save_report_to_disk=self._write_minimal_report,
            build_decision_card=build_decision_card,
            save_decision_card=lambda *_args, **_kwargs: events.append("save-card"),
            write_search_evidence=write_search_evidence,
            write_decision_delta=lambda **_kwargs: events.append("delta"),
            storage_backend_is_remote=lambda: False,
            check_canceled=check_canceled,
            now=lambda: datetime(2026, 4, 20, 15, 30, 45),
        )

        with patch.object(report_publication.auth, "auth_enabled", return_value=False):
            result = report_publication.publish_analysis_report(
                report_publication.ReportPublicationRequest(
                    task_id="task-1",
                    request=self._request(),
                    final_state={"final_trade_decision": "HOLD"},
                    temp_dir=temp_report_dir,
                    owner_user_id=None,
                    tenant_id=None,
                    report_visibility=report_metadata.REPORT_VISIBILITY_PRIVATE,
                ),
                adapters=adapters,
            )

        self.assertEqual(result.report_id, "MSFT_20260420_153045")
        self.assertEqual(result.report_dir, app_config.REPORTS_DIR / result.report_id)
        self.assertFalse(temp_report_dir.exists())
        self.assertTrue((result.report_dir / "complete_report.md").is_file())
        self.assertIn(("search", "task-1", temp_report_dir), events)
        self.assertIn(("decision", result.report_id), events)
        self.assertEqual(events.count("check"), 3)

    def test_publish_analysis_report_indexes_metadata_and_uploads_remote_storage(self):
        temp_report_dir = app_config.TMP_REPORTS_DIR / "task-2"
        fake_db = object()
        uploaded = []

        @contextmanager
        def fake_db_session():
            yield fake_db

        def upload_directory(local_dir, prefix):
            uploaded.append((local_dir, prefix))
            return [f"{prefix}/complete_report.md"]

        adapters = report_publication.ReportPublicationAdapters(
            save_report_to_disk=self._write_minimal_report,
            build_decision_card=lambda **_kwargs: SimpleNamespace(),
            save_decision_card=lambda *_args, **_kwargs: None,
            write_search_evidence=lambda *_args, **_kwargs: None,
            write_decision_delta=lambda **_kwargs: None,
            storage_backend_is_remote=lambda: True,
            upload_directory=upload_directory,
            now=lambda: datetime(2026, 4, 20, 15, 30, 45),
        )

        with (
            patch.object(report_publication.auth, "auth_enabled", return_value=True),
            patch.object(report_publication.auth, "db_session", fake_db_session),
            patch.object(
                report_publication.report_metadata, "upsert_report_run"
            ) as upsert_report_run,
        ):
            result = report_publication.publish_analysis_report(
                report_publication.ReportPublicationRequest(
                    task_id="task-2",
                    request=self._request(),
                    final_state={"final_trade_decision": "BUY"},
                    temp_dir=temp_report_dir,
                    owner_user_id="user-1",
                    tenant_id="tenant-1",
                    report_visibility=report_metadata.REPORT_VISIBILITY_WORKSPACE,
                ),
                adapters=adapters,
            )

        upsert_report_run.assert_called_once()
        _, kwargs = upsert_report_run.call_args
        self.assertIs(upsert_report_run.call_args.args[0], fake_db)
        self.assertEqual(kwargs["report_id"], "MSFT_20260420_153045")
        self.assertEqual(kwargs["owner_user_id"], "user-1")
        self.assertEqual(kwargs["tenant_id"], "tenant-1")
        self.assertEqual(
            kwargs["visibility"], report_metadata.REPORT_VISIBILITY_WORKSPACE
        )
        self.assertEqual(kwargs["ticker"], "MSFT")
        self.assertEqual(kwargs["generated_at"], "2026-04-20 09:30:00")
        self.assertGreaterEqual(len(kwargs["file_entries"]), 2)
        self.assertEqual(
            uploaded, [(result.report_dir, "reports/MSFT_20260420_153045")]
        )


if __name__ == "__main__":
    unittest.main()
