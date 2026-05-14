import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web.backend import auth, search_quota


class SearchQuotaBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'auth.db'}"
        auth.reset_runtime_state()

    def tearDown(self):
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def _env(self, extra: dict[str, str] | None = None):
        env = {
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "required",
            "DATABASE_URL": self.database_url,
        }
        if extra:
            env.update(extra)
        return patch.dict(os.environ, env, clear=False)

    def test_default_search_quota_config_is_disabled_and_zero_quota(self):
        with self._env():
            auth.create_all_for_testing()
            with auth.db_session() as db:
                summary = search_quota.get_search_quota_summary(db)

        self.assertFalse(summary["global"]["enabled"])
        self.assertEqual(summary["month"], search_quota.current_usage_month())
        self.assertEqual(
            [provider["provider"] for provider in summary["providers"]],
            ["brave", "tavily", "bocha"],
        )
        for provider in summary["providers"]:
            self.assertFalse(provider["enabled"])
            self.assertEqual(provider["monthly_free_quota"], 0)
            self.assertEqual(provider["monthly_hard_cap"], 0)
            self.assertEqual(provider["used_this_month"], 0)
            self.assertEqual(provider["remaining_to_hard_cap"], 0)

    def test_monthly_hard_cap_cannot_exceed_free_quota(self):
        with self._env():
            auth.create_all_for_testing()
            with auth.db_session() as db:
                with self.assertRaises(ValueError):
                    search_quota.update_provider_config(
                        db,
                        "brave",
                        {"monthly_free_quota": 10, "monthly_hard_cap": 11},
                    )

    def test_key_status_comes_from_environment_without_key_value(self):
        with self._env({"BRAVE_SEARCH_API_KEY": "secret-brave"}):
            auth.create_all_for_testing()
            with auth.db_session() as db:
                summary = search_quota.get_search_quota_summary(db)

        brave = next(
            provider
            for provider in summary["providers"]
            if provider["provider"] == "brave"
        )
        tavily = next(
            provider
            for provider in summary["providers"]
            if provider["provider"] == "tavily"
        )
        self.assertEqual(brave["key_status"], "configured")
        self.assertEqual(tavily["key_status"], "missing")
        self.assertNotIn("secret-brave", str(summary))

    def test_usage_month_uses_natural_month_key(self):
        with self._env():
            auth.create_all_for_testing()
            with auth.db_session() as db:
                search_quota.record_search_provider_call(
                    db, "brave", success=False, error="timeout"
                )
                summary = search_quota.get_search_quota_summary(db)

        brave = next(
            provider
            for provider in summary["providers"]
            if provider["provider"] == "brave"
        )
        self.assertRegex(summary["month"], r"^\d{4}-\d{2}$")
        self.assertEqual(brave["used_this_month"], 1)
        self.assertEqual(brave["failure_count"], 1)
        self.assertEqual(brave["last_error"], "timeout")

    def test_provider_usage_upsert_accumulates_success_failure_and_last_error(self):
        with self._env():
            auth.create_all_for_testing()
            with auth.db_session() as db:
                search_quota.record_search_provider_call(db, "brave", success=True)
                search_quota.record_search_provider_call(
                    db, "brave", success=False, error="timeout"
                )
                row = db.get(
                    search_quota.SearchProviderUsage,
                    (search_quota.current_usage_month(), "brave"),
                )

                self.assertIsNotNone(row)
                self.assertEqual(row.total_calls, 2)
                self.assertEqual(row.success_count, 1)
                self.assertEqual(row.failure_count, 1)
                self.assertEqual(row.last_error, "timeout")


if __name__ == "__main__":
    unittest.main()
