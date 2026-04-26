import unittest
from unittest.mock import patch

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.openai_client import OpenAIClient


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_factory_routes_siliconflow_to_openai_compatible_client(self):
        client = create_llm_client(
            "siliconflow",
            "deepseek-ai/DeepSeek-V4-Flash",
        )

        self.assertIsInstance(client, OpenAIClient)

    def test_siliconflow_client_uses_provider_base_url_and_api_key(self):
        client = OpenAIClient(
            "deepseek-ai/DeepSeek-V4-Flash",
            provider="siliconflow",
        )

        with (
            patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-siliconflow-key"}, clear=True),
            patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI") as chat_openai,
        ):
            client.get_llm()

        chat_openai.assert_called_once()
        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "deepseek-ai/DeepSeek-V4-Flash")
        self.assertEqual(kwargs["base_url"], "https://api.siliconflow.cn/v1")
        self.assertEqual(kwargs["api_key"], "test-siliconflow-key")
        self.assertNotIn("use_responses_api", kwargs)


if __name__ == "__main__":
    unittest.main()
