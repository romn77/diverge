import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web.backend import app_config, auth, report_metadata
from web.backend.main import app
from web.backend.runtime import analysis_tasks, screener_tasks
from tests.web.http_harness import app_client


class ReportMetadataAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.temp_dir.name) / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(self.temp_dir.name) / "backend.sqlite3"
        self.project_root = Path(self.temp_dir.name) / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.project_env = self.project_root / ".env"
        self.project_env.write_text("OPENAI_API_KEY=test-openai-key\n", encoding="utf-8")

        self.original_reports_dir = app_config.REPORTS_DIR
        self.original_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        self.original_project_root = app_config.PROJECT_ROOT
        self.original_project_env_file = app_config.PROJECT_ENV_FILE
        app_config.REPORTS_DIR = self.reports_dir
        app_config.TMP_REPORTS_DIR = self.reports_dir / ".tmp"
        app_config.PROJECT_ROOT = self.project_root
        app_config.PROJECT_ENV_FILE = self.project_env
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()

        self.env_patcher = patch.dict(
            "os.environ",
            {
                "AUTH_MODE": "required",
                "AUTH_ENABLED": "true",
                "DATABASE_URL": f"sqlite+pysqlite:///{self.db_path}",
                "SESSION_COOKIE_NAME": "test_session",
                "SESSION_COOKIE_SECURE": "false",
                "SESSION_COOKIE_SAMESITE": "lax",
                "SESSION_TTL_HOURS": "24",
            },
            clear=False,
        )
        self.env_patcher.start()
        auth.reset_runtime_state()
        auth.create_all_for_testing()

        with auth.db_session() as db:
            self.owner = auth.create_user(
                db,
                email="owner@example.com",
                display_name="Owner",
                password="owner-password",
                role=auth.UserRole.VIEWER,
                must_change_password=False,
            )
            self.collaborator = auth.create_user(
                db,
                email="collab@example.com",
                display_name="Collaborator",
                password="collab-password",
                role=auth.UserRole.VIEWER,
                must_change_password=False,
            )
            self.operator = auth.create_user(
                db,
                email="operator@example.com",
                display_name="Operator",
                password="operator-password",
                role=auth.UserRole.OPERATOR,
                must_change_password=False,
            )
            self.owner_id = self.owner.id
            self.collaborator_id = self.collaborator.id
            self.operator_id = self.operator.id

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        app_config.PROJECT_ROOT = self.original_project_root
        app_config.PROJECT_ENV_FILE = self.original_project_env_file
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        self.env_patcher.stop()
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def _write_report(
        self,
        report_id: str,
        *,
        owner_user_id: str,
        visibility: str,
        tenant_id: str | None = None,
    ) -> Path:
        report_dir = self.reports_dir / report_id
        (report_dir / "1_analysts").mkdir(parents=True, exist_ok=True)
        (report_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-04-20 09:30:00\n\n",
            encoding="utf-8",
        )
        (report_dir / "1_analysts" / "market.md").write_text(
            "# Market\n\nMomentum remains constructive.",
            encoding="utf-8",
        )
        (report_dir / "artifacts" / "thesis.json").write_text(
            '{"ticker":"MSFT","thesis_summary":"Cloud remains durable."}',
            encoding="utf-8",
        )

        with auth.db_session() as db:
            metadata_payload = report_metadata.build_report_metadata(report_dir, report_id=report_id)
            report_metadata.upsert_report_run(
                db,
                report_id=report_id,
                owner_user_id=owner_user_id,
                tenant_id=tenant_id,
                visibility=visibility,
                ticker=str(metadata_payload["ticker"] or "MSFT"),
                generated_at=metadata_payload["generated_at"],
                storage_path=str(metadata_payload["storage_path"] or report_id),
                file_entries=report_metadata.build_report_file_index(report_dir),
            )
        return report_dir

    def test_authenticated_reports_list_only_includes_visible_runs(self):
        async def scenario():
            self._write_report(
                "MSFT_20260420_093000",
                owner_user_id=self.owner_id,
                visibility=report_metadata.REPORT_VISIBILITY_PRIVATE,
            )
            self._write_report(
                "QQQ_20260420_101500",
                owner_user_id=self.collaborator_id,
                visibility=report_metadata.REPORT_VISIBILITY_WORKSPACE,
            )
            self._write_report(
                "IWM_20260420_110500",
                owner_user_id=self.collaborator_id,
                visibility=report_metadata.REPORT_VISIBILITY_PRIVATE,
            )

            async with app_client(app) as client:
                login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "owner@example.com", "password": "owner-password"},
                )
                self.assertEqual(login_response.status_code, 200)

                reports_response = await client.get("/api/reports")
                self.assertEqual(reports_response.status_code, 200)
                report_ids = {row["id"] for row in reports_response.json()}

            self.assertIn("MSFT_20260420_093000", report_ids)
            self.assertIn("QQQ_20260420_101500", report_ids)
            self.assertNotIn("IWM_20260420_110500", report_ids)

        asyncio.run(scenario())

    def test_workspace_reports_are_visible_only_within_same_tenant(self):
        async def scenario():
            with auth.db_session() as db:
                owner = auth.get_user_by_id(db, self.owner_id)
                other_tenant = auth.create_tenant(db, name="External Desk", slug="external-desk")
                other_user = auth.create_user(
                    db,
                    email="external@example.com",
                    display_name="External",
                    password="external-password",
                    role=auth.UserRole.VIEWER,
                    must_change_password=False,
                    tenant_id=other_tenant.id,
                )
                owner_tenant_id = owner.tenant_id
                other_user_id = other_user.id
                other_tenant_id = other_tenant.id

            self._write_report(
                "MSFT_20260420_093000",
                owner_user_id=self.owner_id,
                tenant_id=owner_tenant_id,
                visibility=report_metadata.REPORT_VISIBILITY_WORKSPACE,
            )
            self._write_report(
                "QQQ_20260420_101500",
                owner_user_id=other_user_id,
                tenant_id=other_tenant_id,
                visibility=report_metadata.REPORT_VISIBILITY_WORKSPACE,
            )

            async with app_client(app) as client:
                login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "owner@example.com", "password": "owner-password"},
                )
                self.assertEqual(login_response.status_code, 200)

                reports_response = await client.get("/api/reports")
                self.assertEqual(reports_response.status_code, 200)
                self.assertEqual(
                    [row["id"] for row in reports_response.json()],
                    ["MSFT_20260420_093000"],
                )

                external_detail = await client.get("/api/reports/QQQ_20260420_101500/structure")
                self.assertEqual(external_detail.status_code, 404)

        asyncio.run(scenario())

    def test_report_structure_and_content_use_db_index_as_authority(self):
        async def scenario():
            report_dir = self._write_report(
                "MSFT_20260420_093000",
                owner_user_id=self.owner_id,
                visibility=report_metadata.REPORT_VISIBILITY_PRIVATE,
            )
            (report_dir / "artifacts" / "manual.json").write_text(
                '{"note":"not indexed"}',
                encoding="utf-8",
            )

            async with app_client(app) as client:
                login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "owner@example.com", "password": "owner-password"},
                )
                self.assertEqual(login_response.status_code, 200)

                structure_response = await client.get("/api/reports/MSFT_20260420_093000/structure")
                self.assertEqual(structure_response.status_code, 200)
                structure_payload = structure_response.json()

                self.assertEqual(structure_payload["categories"]["analysts"], ["market"])
                self.assertEqual(structure_payload["artifacts"][0]["path"], "artifacts/thesis.json")

                content_response = await client.get(
                    "/api/reports/MSFT_20260420_093000/content",
                    params={"path": "1_analysts/market.md"},
                )
                self.assertEqual(content_response.status_code, 200)
                self.assertIn("Momentum remains constructive", content_response.json()["content"])

                unindexed_response = await client.get(
                    "/api/reports/MSFT_20260420_093000/content",
                    params={"path": "artifacts/manual.json"},
                )
                self.assertEqual(unindexed_response.status_code, 404)

        asyncio.run(scenario())

    def test_analysis_completion_indexes_report_with_owner_and_private_visibility(self):
        payload = {
            "ticker": "MSFT",
            "analysis_date": "2026-04-20",
            "analysts": ["market"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }

        final_state = {"type": "final_state_stub"}

        def fake_run_analysis_streaming(_request, _temp_dir, *, reports_dir=None, visible_trade_ids=None):
            self.assertEqual(reports_dir, self.reports_dir)
            self.assertEqual(visible_trade_ids, set())
            if False:  # pragma: no cover
                yield None
            return final_state

        def fake_save_report_to_disk(_final_state, _ticker, temp_dir):
            (temp_dir / "1_analysts").mkdir(parents=True, exist_ok=True)
            (temp_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (temp_dir / "complete_report.md").write_text(
                "# Trading Analysis Report: MSFT\n\nGenerated: 2026-04-20 09:30:00\n\n",
                encoding="utf-8",
            )
            (temp_dir / "1_analysts" / "market.md").write_text(
                "# Market\n\nStable backdrop.",
                encoding="utf-8",
            )
            (temp_dir / "artifacts" / "thesis.json").write_text(
                '{"ticker":"MSFT","thesis_summary":"Cloud remains durable."}',
                encoding="utf-8",
            )
            return temp_dir / "complete_report.md"

        async def create_task():
            async with app_client(app) as client:
                login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "operator@example.com", "password": "operator-password"},
                )
                self.assertEqual(login_response.status_code, 200)

                with patch("web.backend.runtime.analysis_tasks.start_task_thread") as start_task_thread:
                    response = await client.post("/api/tasks", json=payload)
                start_task_thread.assert_called_once()
                return response.json()

        task_body = asyncio.run(create_task())
        task_id = task_body["task_id"]
        with (
            patch("web.backend.runtime.analysis_tasks.run_analysis_streaming", side_effect=fake_run_analysis_streaming),
            patch("web.backend.runtime.analysis_tasks.save_report_to_disk", side_effect=fake_save_report_to_disk),
        ):
            analysis_tasks.run_task(task_id)

        indexed_report_id = analysis_tasks.tasks[task_id].report_id
        self.assertIsNotNone(indexed_report_id)

        with auth.db_session() as db:
            report_run = db.get(report_metadata.ReportRun, indexed_report_id)
            self.assertIsNotNone(report_run)
            self.assertEqual(report_run.owner_user_id, self.operator_id)
            self.assertEqual(report_run.visibility, report_metadata.REPORT_VISIBILITY_PRIVATE)
            self.assertEqual(report_run.ticker, "MSFT")

            file_entries = report_metadata.list_report_files(db, indexed_report_id)
            self.assertGreaterEqual(len(file_entries), 2)


if __name__ == "__main__":
    unittest.main()
