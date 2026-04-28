import unittest

from tradingagents.llm_clients.model_profiles import (
    STATIC_MODEL_PROFILES,
    list_model_profile_options,
    resolve_model_profile,
)
from tradingagents.llm_clients.validators import validate_model


def _available(_provider: str) -> dict[str, object]:
    return {"enabled": True, "disabled_reason": None}


def _only_sub2api(provider: str) -> dict[str, object]:
    return {"enabled": provider == "sub2api", "disabled_reason": None}


def _none(_provider: str) -> dict[str, object]:
    return {"enabled": False, "disabled_reason": "missing key"}


class ModelProfileTests(unittest.TestCase):
    def test_static_profiles_resolve_to_valid_models(self):
        for profile in STATIC_MODEL_PROFILES:
            with self.subTest(profile=profile.value):
                resolved = resolve_model_profile(profile.value, _available)
                self.assertTrue(validate_model(resolved.llm_provider, resolved.quick_think_llm))
                self.assertTrue(validate_model(resolved.llm_provider, resolved.deep_think_llm))

    def test_resolver_skips_unavailable_provider_routes(self):
        resolved = resolve_model_profile("balanced", _only_sub2api)

        self.assertEqual(resolved.llm_provider, "sub2api")
        self.assertEqual(resolved.quick_think_llm, "gpt-5.4-mini")
        self.assertEqual(resolved.deep_think_llm, "gpt-5.2")

    def test_resolver_rejects_profile_without_available_route(self):
        with self.assertRaisesRegex(ValueError, "no available provider route"):
            resolve_model_profile("balanced", _none)

    def test_options_include_custom_and_disabled_reason(self):
        options = list_model_profile_options(_none)
        by_value = {str(option["value"]): option for option in options}

        self.assertIn("custom", by_value)
        self.assertTrue(by_value["custom"]["enabled"])
        self.assertFalse(by_value["balanced"]["enabled"])
        self.assertIn("No configured provider", str(by_value["balanced"]["disabled_reason"]))


if __name__ == "__main__":
    unittest.main()
