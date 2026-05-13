import unittest
from unittest.mock import patch

from diverge.llm_clients.google_client import GoogleClient


class TestGoogleApiKeyStandardization(unittest.TestCase):
    """Verify GoogleClient accepts unified api_key parameter."""

    @patch("diverge.llm_clients.google_client.NormalizedChatGoogleGenerativeAI")
    def test_api_key_handling(self, mock_chat):
        test_cases = [
            ("unified api_key is mapped", {"api_key": "test-key-123"}, "test-key-123"),
            (
                "legacy google_api_key still works",
                {"google_api_key": "legacy-key-456"},
                "legacy-key-456",
            ),
            (
                "unified api_key takes precedence",
                {"api_key": "unified", "google_api_key": "legacy"},
                "unified",
            ),
        ]

        for msg, kwargs, expected_key in test_cases:
            with self.subTest(msg=msg):
                mock_chat.reset_mock()
                client = GoogleClient("gemini-2.5-flash", **kwargs)
                client.get_llm()
                call_kwargs = mock_chat.call_args[1]
                self.assertEqual(call_kwargs.get("google_api_key"), expected_key)

    @patch("diverge.llm_clients.google_client.NormalizedChatGoogleGenerativeAI")
    def test_env_gemini_key_and_base_url_are_used(self, mock_chat):
        with patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "gemini-env-key",
                "GOOGLE_GEMINI_BASE_URL": "https://cc.z2blog.com",
            },
            clear=True,
        ):
            client = GoogleClient("gemini-2.5-flash")
            client.get_llm()

        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["google_api_key"], "gemini-env-key")
        self.assertEqual(call_kwargs["base_url"], "https://cc.z2blog.com")

    @patch("diverge.llm_clients.google_client.NormalizedChatGoogleGenerativeAI")
    def test_env_base_url_overrides_builtin_default(self, mock_chat):
        with patch.dict(
            "os.environ",
            {"GOOGLE_GEMINI_BASE_URL": "https://cc.z2blog.com"},
            clear=True,
        ):
            client = GoogleClient(
                "gemini-2.5-flash",
                base_url="https://generativelanguage.googleapis.com/v1",
            )
            client.get_llm()

        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["base_url"], "https://cc.z2blog.com")

    @patch("diverge.llm_clients.google_client.NormalizedChatGoogleGenerativeAI")
    def test_explicit_custom_base_url_takes_precedence_over_env(self, mock_chat):
        with patch.dict(
            "os.environ",
            {"GOOGLE_GEMINI_BASE_URL": "https://cc.z2blog.com"},
            clear=True,
        ):
            client = GoogleClient(
                "gemini-2.5-flash",
                base_url="https://custom.example.com",
            )
            client.get_llm()

        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["base_url"], "https://custom.example.com")


if __name__ == "__main__":
    unittest.main()
