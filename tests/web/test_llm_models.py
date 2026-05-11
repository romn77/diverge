import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select

from web.backend import auth, llm_models


class LLMModelConfigTests(unittest.TestCase):
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

    def test_summary_reports_key_status_without_key_value(self):
        with self._env({"OPENAI_API_KEY": "secret-value"}):
            auth.create_all_for_testing()
            summary = llm_models.list_llm_model_summary()

        openai = next(
            provider
            for provider in summary["providers"]
            if provider["provider"] == "openai"
        )
        self.assertEqual(openai["key_status"], "configured")
        self.assertEqual(openai["api_key_env"], "OPENAI_API_KEY")
        self.assertNotIn("secret-value", str(summary))

    def test_summary_seeds_database_defaults(self):
        with self._env():
            auth.create_all_for_testing()
            summary = llm_models.list_llm_model_summary()

            with auth.db_session() as db:
                provider_count = db.scalar(
                    select(func.count()).select_from(llm_models.LLMProviderConfig)
                )
                model_count = db.scalar(
                    select(func.count()).select_from(llm_models.LLMModelConfig)
                )
                profile_count = db.scalar(
                    select(func.count()).select_from(llm_models.LLMModelProfile)
                )
                route_count = db.scalar(
                    select(func.count()).select_from(llm_models.LLMModelProfileRoute)
                )

        self.assertEqual(provider_count, len(summary["providers"]))
        self.assertEqual(model_count, len(summary["models"]))
        self.assertEqual(profile_count, len(summary["profiles"]))
        self.assertEqual(
            route_count,
            sum(len(profile["routes"]) * 2 for profile in summary["profiles"]),
        )

    def test_disabled_model_blocks_profile_resolution(self):
        with self._env(
            {"OPENAI_API_KEY": "secret-value", "SUB2API_API_KEY": "secret-value"}
        ):
            auth.create_all_for_testing()
            llm_models.update_model_config(
                "openai",
                "gpt-5.4-mini",
                enabled=False,
                cost_tier="medium",
                visible_to_roles=["admin", "operator", "viewer"],
                daily_limit=None,
                weekly_limit=None,
            )
            resolved = llm_models.resolve_model_profile_from_db("balanced")

        self.assertEqual(resolved.llm_provider, "sub2api")

    def test_daily_model_limit_blocks_route(self):
        with self._env(
            {"OPENAI_API_KEY": "secret-value", "SUB2API_API_KEY": "secret-value"}
        ):
            auth.create_all_for_testing()
            llm_models.update_model_config(
                "openai",
                "gpt-5.4-mini",
                enabled=True,
                cost_tier="medium",
                visible_to_roles=["admin", "operator", "viewer"],
                daily_limit=1,
                weekly_limit=None,
            )
            llm_models.record_model_usage("openai", "gpt-5.4-mini", module="analysis")
            resolved = llm_models.resolve_model_profile_from_db("balanced")

        self.assertEqual(resolved.llm_provider, "sub2api")

    def test_model_usage_upsert_accumulates_and_resets_hour_bucket(self):
        with self._env():
            auth.create_all_for_testing()
            llm_models.record_model_usage("openai", "gpt-5.4-mini", module="analysis")
            llm_models.record_model_usage(
                "openai", "gpt-5.4-mini", module="analysis", success=False
            )

            usage_date = llm_models._today_key()
            with auth.db_session() as db:
                row = db.get(
                    llm_models.LLMModelUsage,
                    (usage_date, "openai", "gpt-5.4-mini", "analysis"),
                )
                self.assertIsNotNone(row)
                self.assertEqual(row.total_calls, 2)
                self.assertEqual(row.success_count, 1)
                self.assertEqual(row.failure_count, 1)
                self.assertEqual(row.hour_total_calls, 2)
                row.hour_key = "2000-01-01T00"
                row.hour_total_calls = 9

            llm_models.record_model_usage("openai", "gpt-5.4-mini", module="analysis")
            with auth.db_session() as db:
                row = db.get(
                    llm_models.LLMModelUsage,
                    (usage_date, "openai", "gpt-5.4-mini", "analysis"),
                )
                self.assertEqual(row.total_calls, 3)
                self.assertEqual(row.success_count, 2)
                self.assertEqual(row.failure_count, 1)
                self.assertEqual(row.hour_total_calls, 1)
                self.assertNotEqual(row.hour_key, "2000-01-01T00")

    def test_admin_module_setting_resolves_trade_journal_review_model(self):
        with self._env({"OPENAI_API_KEY": "secret-value"}):
            auth.create_all_for_testing()
            setting = llm_models.update_module_setting(
                "trade_journal_review",
                enabled=True,
                model_profile="balanced",
                output_language="cn",
                openai_reasoning_effort="high",
                google_thinking_level="minimal",
            )
            resolved = llm_models.resolve_module_model_selection("trade_journal_review")

        self.assertTrue(setting["enabled"])
        self.assertEqual(resolved["llm_provider"], "openai")
        self.assertEqual(resolved["model"], "gpt-5.2")
        self.assertEqual(resolved["output_language"], "cn")
        self.assertEqual(resolved["openai_reasoning_effort"], "high")

    def test_admin_module_setting_accepts_custom_review_model(self):
        with self._env({"OPENAI_API_KEY": "secret-value"}):
            auth.create_all_for_testing()
            setting = llm_models.update_module_setting(
                "trade_journal_review",
                enabled=True,
                model_profile="custom",
                output_language="cn",
                custom_provider="openai",
                custom_model="gpt-5.5",
                openai_reasoning_effort="high",
                google_thinking_level=None,
            )
            resolved = llm_models.resolve_module_model_selection("trade_journal_review")

        self.assertEqual(setting["model_profile"], "custom")
        self.assertEqual(setting["custom_provider"], "openai")
        self.assertEqual(setting["custom_model"], "gpt-5.5")
        self.assertEqual(resolved["llm_provider"], "openai")
        self.assertEqual(resolved["model"], "gpt-5.5")

    def test_default_profile_routes_can_be_saved(self):
        with self._env():
            auth.create_all_for_testing()
            summary = llm_models.list_llm_model_summary()
            for profile in summary["profiles"]:
                if profile["profile_id"] == "custom":
                    continue
                routes = [
                    {
                        "provider": route["provider"],
                        "quick_model": route["quick_model"],
                        "deep_model": route["deep_model"],
                    }
                    for route in profile["routes"]
                ]
                saved = llm_models.update_profile_routes(profile["profile_id"], routes)

                self.assertEqual(len(saved), len(routes))


if __name__ == "__main__":
    unittest.main()
