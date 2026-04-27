import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web.backend import app_config, auth
from web.backend.services.reports import get_structure


class ThesisArtifactListingTests(unittest.TestCase):
    def setUp(self):
        self.auth_env_patch = patch.dict(
            os.environ,
            {"AUTH_ENABLED": "false", "AUTH_MODE": "disabled"},
            clear=False,
        )
        self.auth_env_patch.start()
        auth.reset_runtime_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = app_config.REPORTS_DIR
        app_config.REPORTS_DIR = Path(self.temp_dir.name)
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
        self.temp_dir.cleanup()
        auth.reset_runtime_state()
        self.auth_env_patch.stop()

    def test_report_structure_exposes_thesis_artifact_metadata_when_present(self):
        report_dir = app_config.REPORTS_DIR / "MSFT_20260320_100000"
        artifact_dir = report_dir / "artifacts"
        artifact_dir.mkdir(parents=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-03-20 10:00:00\n\n",
            encoding="utf-8",
        )
        (artifact_dir / "thesis.json").write_text(
            json.dumps(
                {
                    "ticker": "MSFT",
                    "thesis_summary": "Cloud durability remains the core long thesis.",
                }
            ),
            encoding="utf-8",
        )

        payload = get_structure("MSFT_20260320_100000")
        self.assertEqual(payload["artifacts"][0]["path"], "artifacts/thesis.json")
        self.assertEqual(payload["artifacts"][0]["type"], "thesis")

    def test_report_structure_exposes_summary_artifact_metadata_when_present(self):
        report_dir = app_config.REPORTS_DIR / "MSFT_20260320_100000"
        artifact_dir = report_dir / "artifacts"
        artifact_dir.mkdir(parents=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-03-20 10:00:00\n\n",
            encoding="utf-8",
        )
        (artifact_dir / "summary.json").write_text(
            json.dumps(
                {
                    "ticker": "MSFT",
                    "summary": "BUY with disciplined sizing around valuation risk.",
                }
            ),
            encoding="utf-8",
        )
        (artifact_dir / "thesis.json").write_text(
            json.dumps(
                {
                    "ticker": "MSFT",
                    "thesis_summary": "Cloud durability remains the core long thesis.",
                }
            ),
            encoding="utf-8",
        )

        payload = get_structure("MSFT_20260320_100000")
        self.assertEqual(payload["artifacts"][0]["path"], "artifacts/summary.json")
        self.assertEqual(payload["artifacts"][0]["type"], "summary")
        self.assertEqual(
            payload["artifacts"][0]["summary"],
            "BUY with disciplined sizing around valuation risk.",
        )

    def test_report_structure_exposes_trade_feedback_artifact_metadata_when_present(self):
        report_dir = app_config.REPORTS_DIR / "MSFT_20260320_100000"
        artifact_dir = report_dir / "artifacts"
        artifact_dir.mkdir(parents=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-03-20 10:00:00\n\n",
            encoding="utf-8",
        )
        (artifact_dir / "trade_feedback.json").write_text(
            json.dumps(
                {
                    "ticker": "MSFT",
                    "reviews": [
                        {
                            "trade_id": "trade-1",
                            "review_type": "entry_review",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        payload = get_structure("MSFT_20260320_100000")
        self.assertEqual(payload["artifacts"][0]["path"], "artifacts/trade_feedback.json")
        self.assertEqual(payload["artifacts"][0]["type"], "trade_feedback")
