import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from diverge.llm_clients.factory import create_llm_client
from diverge.llm_clients.openai_client import NormalizedChatOpenAI, OpenAIClient


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_factory_routes_siliconflow_to_openai_compatible_client(self):
        client = create_llm_client(
            "siliconflow",
            "deepseek-ai/DeepSeek-V4-Flash",
        )

        self.assertIsInstance(client, OpenAIClient)

    def test_factory_routes_sub2api_to_openai_compatible_client(self):
        client = create_llm_client(
            "sub2api",
            "gpt-5.4",
        )

        self.assertIsInstance(client, OpenAIClient)

    def test_siliconflow_client_uses_provider_base_url_and_api_key(self):
        client = OpenAIClient(
            "deepseek-ai/DeepSeek-V4-Flash",
            provider="siliconflow",
        )

        with (
            patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-siliconflow-key"}, clear=True),
            patch("diverge.llm_clients.openai_client.NormalizedChatOpenAI") as chat_openai,
        ):
            client.get_llm()

        chat_openai.assert_called_once()
        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "deepseek-ai/DeepSeek-V4-Flash")
        self.assertEqual(kwargs["base_url"], "https://api.siliconflow.cn/v1")
        self.assertEqual(kwargs["api_key"], "test-siliconflow-key")
        self.assertNotIn("use_responses_api", kwargs)

    def test_sub2api_client_uses_responses_api_base_url_and_api_key(self):
        client = OpenAIClient(
            "gpt-5.4",
            provider="sub2api",
        )

        with (
            patch.dict("os.environ", {"SUB2API_API_KEY": "test-sub2api-key"}, clear=True),
            patch("diverge.llm_clients.openai_client.NormalizedChatOpenAI") as chat_openai,
        ):
            client.get_llm()

        chat_openai.assert_called_once()
        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.4")
        self.assertEqual(kwargs["base_url"], "https://cc.z2blog.com")
        self.assertEqual(kwargs["api_key"], "test-sub2api-key")
        self.assertTrue(kwargs["use_responses_api"])

    def test_sub2api_responses_payload_promotes_system_message_to_instructions(self):
        with patch.dict("os.environ", {"SUB2API_API_KEY": "test-sub2api-key"}, clear=True):
            llm = OpenAIClient(
                "gpt-5.4",
                provider="sub2api",
            ).get_llm()

        payload = llm._get_request_payload(
            [
                SystemMessage(content="Follow the trading analyst instructions."),
                HumanMessage(content="Analyze AAPL."),
            ]
        )

        self.assertEqual(payload["instructions"], "Follow the trading analyst instructions.")
        self.assertEqual(
            [message["role"] for message in payload["input"]],
            ["user"],
        )

    def test_sub2api_plain_string_responses_are_returned_as_ai_messages(self):
        class RawStringResponse:
            headers = {}

            def parse(self):
                return "Market momentum is mixed."

        llm = NormalizedChatOpenAI(
            model="gpt-5.4",
            api_key="test-key",
            base_url="https://cc.z2blog.com",
            use_responses_api=True,
            ensure_responses_instructions=True,
        )

        with patch.object(
            llm.root_client.responses.with_raw_response,
            "create",
            return_value=RawStringResponse(),
        ):
            result = llm._generate(
                [
                    SystemMessage(content="Follow the trading analyst instructions."),
                    HumanMessage(content="Analyze AAPL."),
                ]
            )

        self.assertEqual(result.generations[0].message.content, "Market momentum is mixed.")

    def test_sub2api_sse_function_calls_are_returned_as_tool_calls(self):
        class RawStringResponse:
            headers = {}

            def parse(self):
                return "\n\n".join(
                    [
                        "event: response.output_item.added\n"
                        'data: {"type":"response.output_item.added","item":{"id":"fc_1","type":"function_call","status":"in_progress","arguments":"","call_id":"call_1","name":"get_stock_data"},"output_index":0,"sequence_number":1}',
                        "event: response.function_call_arguments.done\n"
                        'data: {"type":"response.function_call_arguments.done","arguments":"{\\"symbol\\":\\"AMD\\",\\"start_date\\":\\"2026-01-01\\",\\"end_date\\":\\"2026-04-27\\"}","item_id":"fc_1","output_index":0,"sequence_number":2}',
                        "event: response.output_item.done\n"
                        'data: {"type":"response.output_item.done","item":{"id":"fc_1","type":"function_call","status":"completed","arguments":"{\\"symbol\\":\\"AMD\\",\\"start_date\\":\\"2026-01-01\\",\\"end_date\\":\\"2026-04-27\\"}","call_id":"call_1","name":"get_stock_data"},"output_index":0,"sequence_number":3}',
                        "event: response.completed\n"
                        'data: {"type":"response.completed","response":{"id":"resp_1","object":"response","status":"completed","error":null,"output":[],"usage":null}}',
                    ]
                )

        llm = NormalizedChatOpenAI(
            model="gpt-5.4",
            api_key="test-key",
            base_url="https://cc.z2blog.com",
            use_responses_api=True,
            ensure_responses_instructions=True,
        )

        with patch.object(
            llm.root_client.responses.with_raw_response,
            "create",
            return_value=RawStringResponse(),
        ):
            result = llm._generate(
                [
                    SystemMessage(content="Follow the trading analyst instructions."),
                    HumanMessage(content="Analyze AMD."),
                ]
            )

        message = result.generations[0].message
        self.assertEqual(message.content, "")
        self.assertEqual(
            message.tool_calls,
            [
                {
                    "name": "get_stock_data",
                    "args": {
                        "symbol": "AMD",
                        "start_date": "2026-01-01",
                        "end_date": "2026-04-27",
                    },
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )

    def test_sub2api_sse_text_deltas_are_returned_as_ai_message_content(self):
        class RawStringResponse:
            headers = {}

            def parse(self):
                return "\n\n".join(
                    [
                        "event: response.output_text.delta\n"
                        'data: {"type":"response.output_text.delta","delta":"市场","output_index":0,"content_index":0,"sequence_number":1}',
                        "event: response.output_text.delta\n"
                        'data: {"type":"response.output_text.delta","delta":"偏中性。","output_index":0,"content_index":0,"sequence_number":2}',
                        "event: response.completed\n"
                        'data: {"type":"response.completed","response":{"id":"resp_1","object":"response","status":"completed","error":null,"output":[],"usage":null}}',
                    ]
                )

        llm = NormalizedChatOpenAI(
            model="gpt-5.4",
            api_key="test-key",
            base_url="https://cc.z2blog.com",
            use_responses_api=True,
            ensure_responses_instructions=True,
        )

        with patch.object(
            llm.root_client.responses.with_raw_response,
            "create",
            return_value=RawStringResponse(),
        ):
            result = llm._generate(
                [
                    SystemMessage(content="Follow the trading analyst instructions."),
                    HumanMessage(content="Summarize AMD."),
                ]
            )

        self.assertEqual(result.generations[0].message.content, "市场偏中性。")

    def test_reasoning_content_is_preserved_for_follow_up_tool_calls(self):
        llm = NormalizedChatOpenAI(
            model="deepseek-v4-pro",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            preserve_reasoning_content=True,
        )
        ai_message = AIMessage(
            content="",
            additional_kwargs={
                "reasoning_content": "I should call the price tool.",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "price", "arguments": "{}"},
                    }
                ],
            },
        )

        payload = llm._get_request_payload(
            [HumanMessage(content="Analyze AAPL"), ai_message, HumanMessage(content="Tool done")]
        )

        self.assertEqual(
            payload["messages"][1]["reasoning_content"],
            "I should call the price tool.",
        )

    def test_reasoning_content_from_provider_response_is_stored_on_ai_message(self):
        llm = NormalizedChatOpenAI(
            model="deepseek-v4-pro",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            preserve_reasoning_content=True,
        )

        result = llm._create_chat_result(
            {
                "id": "chatcmpl-test",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "I should call the price tool.",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {"name": "price", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
            }
        )

        self.assertEqual(
            result.generations[0].message.additional_kwargs["reasoning_content"],
            "I should call the price tool.",
        )

    def test_nonstandard_assistant_response_role_is_normalized_to_ai_message(self):
        llm = NormalizedChatOpenAI(
            model="deepseek-v4-pro",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            preserve_reasoning_content=True,
        )

        result = llm._create_chat_result(
            {
                "id": "chatcmpl-test",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "",
                            "content": "Market conditions are mixed.",
                        },
                    }
                ],
            }
        )

        self.assertIsInstance(result.generations[0].message, AIMessage)
        self.assertEqual(result.generations[0].message.tool_calls, [])


if __name__ == "__main__":
    unittest.main()
