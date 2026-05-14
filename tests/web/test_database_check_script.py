import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web.backend import auth
from web.backend import (
    analysis_limits,
    asset_entries,
    audit,
    data_sources,
    job_records,
    llm_models,
    report_metadata,
    screener_runs,
    search_quota,
    trade_entries,
)


class DatabaseCheckScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auth.db"
        self.env = {
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "required",
            "DATABASE_URL": f"sqlite+pysqlite:///{self.database_path}",
            "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "AdminPass123",
            "AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Administrator",
        }
        auth.reset_runtime_state()

    def tearDown(self):
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def _load_check_database_module(self):
        try:
            from web.backend.devops import check_database
        except ImportError as exc:
            self.fail(
                f"Expected web.backend.devops.check_database module to exist: {exc}"
            )
        return check_database

    def test_check_reports_pending_migrations_for_empty_database(self):
        stream = io.StringIO()
        check_database = self._load_check_database_module()

        with patch.dict(os.environ, self.env, clear=False):
            result = check_database.run_database_check(upgrade=False, stream=stream)

        self.assertEqual(result.exit_code, 1)
        output = stream.getvalue()
        self.assertIn("Connection: ok", output)
        self.assertIn("Schema: pending migrations", output)
        self.assertIn("Missing tables:", output)
        self.assertIn("users", output)

    def test_upgrade_applies_migrations_and_verifies_required_tables(self):
        stream = io.StringIO()
        check_database = self._load_check_database_module()

        with patch.dict(os.environ, self.env, clear=False):
            result = check_database.run_database_check(upgrade=True, stream=stream)

        self.assertEqual(result.exit_code, 0)
        output = stream.getvalue()
        self.assertIn("Applying migrations: alembic upgrade head", output)
        self.assertIn("Connection: ok", output)
        self.assertIn("Schema: up to date", output)
        self.assertIn("Required tables: ok", output)

    def test_required_tables_cover_current_model_metadata(self):
        check_database = self._load_check_database_module()
        expected_tables = set(auth.Base.metadata.tables) - {"alembic_version"}

        self.assertTrue(
            expected_tables.issubset(set(check_database.REQUIRED_TABLES)),
            expected_tables - set(check_database.REQUIRED_TABLES),
        )

    def test_alembic_metadata_imports_non_auth_models(self):
        # Imported modules above should populate auth.Base.metadata the same way
        # Alembic env.py now does before assigning target_metadata.
        for table_name in (
            "asset_positions",
            "report_runs",
            "llm_model_usage",
            "search_provider_usage",
        ):
            self.assertIn(table_name, auth.Base.metadata.tables)


if __name__ == "__main__":
    unittest.main()
