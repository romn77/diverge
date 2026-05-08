import json
import tempfile
import unittest
from pathlib import Path

from web.backend.services import reports


class SearchEvidenceReportStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.report_dir = Path(self.temp_dir.name) / "SPY_20260508_120000"
        (self.report_dir / "artifacts").mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scan_artifacts_recognizes_search_evidence_summary(self):
        (self.report_dir / "artifacts" / "search_evidence.json").write_text(
            json.dumps(
                {
                    "type": "search_evidence",
                    "calls": [
                        {"results": [{"url": "https://example.com/1"}]},
                        {
                            "results": [
                                {"url": "https://example.com/2"},
                                {"url": "https://example.com/3"},
                            ]
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        artifacts = reports.scan_artifacts(self.report_dir)

        search_artifact = next(
            artifact for artifact in artifacts if artifact["type"] == "search_evidence"
        )
        self.assertEqual(search_artifact["path"], "artifacts/search_evidence.json")
        self.assertEqual(search_artifact["summary"], "2 web search call(s), 3 result(s)")

    def test_invalid_search_evidence_json_still_exposes_artifact(self):
        (self.report_dir / "artifacts" / "search_evidence.json").write_text(
            "{not-json",
            encoding="utf-8",
        )

        artifacts = reports.scan_artifacts(self.report_dir)

        search_artifact = next(
            artifact for artifact in artifacts if artifact["type"] == "search_evidence"
        )
        self.assertIsNone(search_artifact["summary"])


if __name__ == "__main__":
    unittest.main()
