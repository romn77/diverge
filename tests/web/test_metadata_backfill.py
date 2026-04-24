import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents.trade_feedback import create_trade_record as create_trade_record_file
from web.backend import app_config, auth, backfill_metadata, report_metadata
from web.backend.main import app
from tests.web.http_harness import app_client


class MetadataBackfillTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.reports_dir = self.root / "reports"
        self.reports_dir.mkdir(parents=True)
        self.screener_runs_dir = self.root / "data" / "screener" / "runs"
        self.screener_runs_dir.mkdir(parents=True)
        self.database_path = self.root / "auth.db"

        self.original_backend_reports_dir = app_config.REPORTS_DIR
        self.original_backend_screener_dir = app_config.SCREENER_RESULTS_DIR
        self.original_backend_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        self.original_backfill_reports_dir = backfill_metadata.REPORTS_DIR
        self.original_backfill_screener_runs_dir = backfill_metadata.SCREENER_RUNS_DIR

        app_config.REPORTS_DIR = self.reports_dir
        app_config.SCREENER_RESULTS_DIR = self.screener_runs_dir
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
        backfill_metadata.REPORTS_DIR = self.reports_dir
        backfill_metadata.SCREENER_RUNS_DIR = self.screener_runs_dir

        self.env = {
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "optional",
            "DATABASE_URL": f"sqlite:///{self.database_path}",
            "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "AdminPass123",
            "AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Administrator",
        }

    def tearDown(self):
        auth.reset_runtime_state()
        app_config.REPORTS_DIR = self.original_backend_reports_dir
        app_config.SCREENER_RESULTS_DIR = self.original_backend_screener_dir
        app_config.TMP_REPORTS_DIR = self.original_backend_tmp_reports_dir
        backfill_metadata.REPORTS_DIR = self.original_backfill_reports_dir
        backfill_metadata.SCREENER_RUNS_DIR = self.original_backfill_screener_runs_dir
        self.temp_dir.cleanup()

    def _write_report(self, report_id: str = "MSFT_20260320_100000") -> Path:
        report_dir = self.reports_dir / report_id
        artifact_dir = report_dir / "artifacts"
        analysts_dir = report_dir / "1_analysts"
        artifact_dir.mkdir(parents=True)
        analysts_dir.mkdir(parents=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-03-20 10:00:00\n\n",
            encoding="utf-8",
        )
        (analysts_dir / "market.md").write_text("# Market\n", encoding="utf-8")
        (artifact_dir / "thesis.json").write_text(
            json.dumps({"thesis_summary": "Cloud durability remains intact."}),
            encoding="utf-8",
        )
        return report_dir

    def _write_screener_run(self, run_id: str = "20260324_214530") -> None:
        run_dir = self.screener_runs_dir / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "run_timestamp": run_id,
                    "as_of_date": "2026-03-24",
                    "config": {"markets": ["cn"]},
                    "candidate_count": 1,
                    "filtered_count_by_reason": {"liquidity_floor": 2},
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "candidates.csv").write_text(
            "symbol,market,global_rank,total_score\n600519.SH,cn,1,0.91\n",
            encoding="utf-8",
        )

    def _write_trade(self) -> str:
        record = create_trade_record_file(
            {
                "ticker": "MSFT",
                "exchange_or_market": "NASDAQ",
                "side": "long",
                "status": "open",
                "entry_timestamp": "2026-04-01T09:30:00",
                "entry_price": 420.5,
                "size": 12,
                "initial_thesis": "Cloud durability remains underpriced.",
                "planned_horizon": "swing_2w",
                "stop_loss": 405.0,
                "take_profit": 450.0,
                "notes": "Initial entry.",
                "analysis_references": [],
            },
            reports_dir=self.reports_dir,
        )
        return record["trade_id"]

    def test_backfill_indexes_reports_trades_and_screener_runs_under_bootstrap_admin(self):
        self._write_report()
        self._write_trade()
        self._write_screener_run()

        with patch.dict(os.environ, self.env, clear=True):
            auth.reset_runtime_state()
            auth.create_all_for_testing()
            summary = backfill_metadata.backfill_all_metadata()

            self.assertEqual(summary.reports, 1)
            self.assertEqual(summary.report_files, 3)
            self.assertEqual(summary.trades, 1)
            self.assertEqual(summary.screener_runs, 1)

            with auth.db_session() as db:
                admin_user = auth.get_user_by_email(db, "admin@example.com")
                self.assertIsNotNone(admin_user)

                report_records = report_metadata.list_report_runs(
                    db,
                    owner_user_id=admin_user.id,
                    include_workspace=True,
                )
                self.assertEqual(len(report_records), 1)
                self.assertEqual(
                    report_records[0].visibility,
                    report_metadata.REPORT_VISIBILITY_WORKSPACE,
                )

    def test_authenticated_report_content_requires_metadata_indexed_path(self):
        async def scenario():
            report_dir = self._write_report()
            secret_path = report_dir / "secret.md"
            secret_path.write_text("hidden", encoding="utf-8")

            required_env = dict(self.env)
            required_env["AUTH_MODE"] = "required"

            with patch.dict(os.environ, required_env, clear=True):
                auth.reset_runtime_state()
                auth.create_all_for_testing()
                with auth.db_session() as db:
                    auth.ensure_bootstrap_admin(db)
                    admin_user = auth.get_user_by_email(db, "admin@example.com")
                    report_metadata.upsert_report_run(
                        db,
                        report_id=report_dir.name,
                        owner_user_id=admin_user.id,
                        visibility=report_metadata.REPORT_VISIBILITY_WORKSPACE,
                        ticker="MSFT",
                        generated_at="2026-03-20 10:00:00",
                        storage_path=report_dir.name,
                        file_entries=report_metadata.build_report_file_index(report_dir),
                    )

                async with app_client(app) as client:
                    login_response = await client.post(
                        "/api/auth/login",
                        json={"email": "admin@example.com", "password": "AdminPass123"},
                    )
                    self.assertEqual(login_response.status_code, 200, login_response.text)
                    change_response = await client.post(
                        "/api/auth/change-password",
                        json={
                            "current_password": "AdminPass123",
                            "new_password": "AdminPass456",
                        },
                    )
                    self.assertEqual(change_response.status_code, 200, change_response.text)

                    list_response = await client.get("/api/reports")
                    self.assertEqual(list_response.status_code, 200, list_response.text)
                    self.assertEqual([row["id"] for row in list_response.json()], [report_dir.name])

                    content_response = await client.get(
                        f"/api/reports/{report_dir.name}/content",
                        params={"path": "complete_report.md"},
                    )
                    self.assertEqual(content_response.status_code, 200, content_response.text)

                    missing_index_response = await client.get(
                        f"/api/reports/{report_dir.name}/content",
                        params={"path": "secret.md"},
                    )
                    self.assertEqual(missing_index_response.status_code, 404)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
