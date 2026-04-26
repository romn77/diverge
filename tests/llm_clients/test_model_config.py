import unittest

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import model_config
from tradingagents.llm_clients.model_config import (
    DEEP_MODEL_OPTIONS,
    DEFAULT_DEEP_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_QUICK_MODEL,
    PROVIDER_OPTIONS,
    QUICK_MODEL_OPTIONS,
    get_model_ids_for_provider,
)
from tradingagents.llm_clients.validators import validate_model


STRICT_VALIDATION_PROVIDERS = ("openai", "anthropic", "google", "xai", "siliconflow")


class ModelConfigTests(unittest.TestCase):
    def test_default_config_uses_shared_model_defaults(self):
        self.assertEqual(DEFAULT_CONFIG["llm_provider"], DEFAULT_LLM_PROVIDER)
        self.assertEqual(DEFAULT_CONFIG["quick_think_llm"], DEFAULT_QUICK_MODEL)
        self.assertEqual(DEFAULT_CONFIG["deep_think_llm"], DEFAULT_DEEP_MODEL)

    def test_every_provider_has_quick_and_deep_options(self):
        provider_keys = {provider for provider, _label, _url in PROVIDER_OPTIONS}
        self.assertEqual(provider_keys, set(QUICK_MODEL_OPTIONS))
        self.assertEqual(provider_keys, set(DEEP_MODEL_OPTIONS))
        for provider in provider_keys:
            with self.subTest(provider=provider):
                self.assertGreater(len(QUICK_MODEL_OPTIONS[provider]), 0)
                self.assertGreater(len(DEEP_MODEL_OPTIONS[provider]), 0)

    def test_provider_model_maps_are_assembled_from_named_option_constants(self):
        self.assertIs(QUICK_MODEL_OPTIONS["openai"], model_config.OPENAI_QUICK_MODEL_OPTIONS)
        self.assertIs(DEEP_MODEL_OPTIONS["openai"], model_config.OPENAI_DEEP_MODEL_OPTIONS)
        self.assertIs(QUICK_MODEL_OPTIONS["deepseek"], model_config.DEEPSEEK_QUICK_MODEL_OPTIONS)
        self.assertIs(DEEP_MODEL_OPTIONS["deepseek"], model_config.DEEPSEEK_DEEP_MODEL_OPTIONS)
        self.assertIs(QUICK_MODEL_OPTIONS["siliconflow"], model_config.SILICONFLOW_MODEL_OPTIONS)
        self.assertIs(DEEP_MODEL_OPTIONS["siliconflow"], model_config.SILICONFLOW_MODEL_OPTIONS)
        self.assertIs(QUICK_MODEL_OPTIONS["xiaohumini"], model_config.XIAOHUMINI_MODEL_OPTIONS)
        self.assertIs(DEEP_MODEL_OPTIONS["xiaohumini"], model_config.XIAOHUMINI_MODEL_OPTIONS)

    def test_validators_accept_all_shared_models_for_strict_providers(self):
        for provider in STRICT_VALIDATION_PROVIDERS:
            for model_id in get_model_ids_for_provider(provider):
                with self.subTest(provider=provider, model_id=model_id):
                    self.assertTrue(validate_model(provider, model_id))

    def test_siliconflow_provider_exposes_requested_models(self):
        provider_map = {provider: (label, base_url) for provider, label, base_url in PROVIDER_OPTIONS}
        self.assertEqual(provider_map["siliconflow"], ("SiliconFlow", "https://api.siliconflow.cn/v1"))

        model_ids = set(get_model_ids_for_provider("siliconflow"))
        expected_model_ids = {
            "deepseek-ai/DeepSeek-V4-Flash",
            "Pro/moonshotai/Kimi-K2.6",
            "Pro/zai-org/GLM-5.1",
            "MiniMaxAI/MiniMax-M2.5",
            "Pro/MiniMaxAI/MiniMax-M2.5",
            "Pro/zai-org/GLM-5",
            "Pro/moonshotai/Kimi-K2.5",
            "Pro/zai-org/GLM-4.7",
            "deepseek-ai/DeepSeek-V3.2",
            "Pro/deepseek-ai/DeepSeek-V3.2",
            "deepseek-ai/DeepSeek-V3.1-Terminus",
            "Pro/deepseek-ai/DeepSeek-V3.1-Terminus",
            "Qwen/Qwen3.6-35B-A3B",
            "Qwen/Qwen3.6-27B",
            "Qwen/Qwen3.5-397B-A17B",
            "Qwen/Qwen3.5-122B-A10B",
        }

        self.assertEqual(model_ids, expected_model_ids)
        self.assertIn("deepseek-ai/DeepSeek-V4-Flash", {model for _label, model in QUICK_MODEL_OPTIONS["siliconflow"]})
        self.assertIn("Pro/zai-org/GLM-5.1", {model for _label, model in DEEP_MODEL_OPTIONS["siliconflow"]})

    def test_deepseek_provider_exposes_v4_models_for_quick_and_deep(self):
        quick_models = {model for _label, model in QUICK_MODEL_OPTIONS["deepseek"]}
        deep_models = {model for _label, model in DEEP_MODEL_OPTIONS["deepseek"]}
        expected_models = {"deepseek-v4-flash", "deepseek-v4-pro"}

        self.assertTrue(expected_models.issubset(quick_models))
        self.assertTrue(expected_models.issubset(deep_models))
        self.assertTrue(expected_models.issubset(set(get_model_ids_for_provider("deepseek"))))


if __name__ == "__main__":
    unittest.main()
