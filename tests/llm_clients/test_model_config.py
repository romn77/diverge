import unittest

from tradingagents.default_config import DEFAULT_CONFIG
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


STRICT_VALIDATION_PROVIDERS = ("openai", "anthropic", "google", "xai")


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

    def test_validators_accept_all_shared_models_for_strict_providers(self):
        for provider in STRICT_VALIDATION_PROVIDERS:
            for model_id in get_model_ids_for_provider(provider):
                with self.subTest(provider=provider, model_id=model_id):
                    self.assertTrue(validate_model(provider, model_id))


if __name__ == "__main__":
    unittest.main()
