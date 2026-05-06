import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

        openai = next(provider for provider in summary["providers"] if provider["provider"] == "openai")
        self.assertEqual(openai["key_status"], "configured")
        self.assertEqual(openai["api_key_env"], "OPENAI_API_KEY")
        self.assertNotIn("secret-value", str(summary))

    def test_disabled_model_blocks_profile_resolution(self):
        with self._env({"OPENAI_API_KEY": "secret-value", "SUB2API_API_KEY": "secret-value"}):
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
        with self._env({"OPENAI_API_KEY": "secret-value", "SUB2API_API_KEY": "secret-value"}):
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


if __name__ == "__main__":
    unittest.main()
