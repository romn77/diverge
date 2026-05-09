import sys
import types
from pathlib import Path
from unittest.mock import patch

from diverge.graph.trading_graph import DivergeGraph


def test_pyproject_pins_adk_2_beta_and_removes_langgraph():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'requires-python = ">=3.11"' in pyproject
    assert '"google-adk==2.0.0b1"' in pyproject
    assert '"litellm>=1.83.14"' in pyproject
    assert "langgraph" not in pyproject


def test_lockfile_locks_adk_and_removes_langgraph_packages():
    lockfile = Path("uv.lock").read_text(encoding="utf-8")

    assert 'name = "google-adk"' in lockfile
    assert 'name = "langgraph"' not in lockfile
    assert 'name = "langgraph-checkpoint"' not in lockfile
    assert 'name = "langgraph-prebuilt"' not in lockfile
    assert 'name = "langgraph-sdk"' not in lockfile


def test_agent_state_is_framework_owned_not_langgraph_owned():
    source = Path("diverge/agents/utils/agent_states.py").read_text(encoding="utf-8")

    assert "MessagesState" not in source
    assert "langgraph" not in source


def test_diverge_graph_exposes_runtime_facade_without_nested_graph_stream():
    graph = DivergeGraph.__new__(DivergeGraph)

    assert hasattr(graph, "stream")
    assert hasattr(graph, "invoke")
    assert not hasattr(graph, "graph")


def test_runner_uses_diverge_graph_stream_facade():
    source = Path("diverge/runner.py").read_text(encoding="utf-8")

    assert ".graph.stream" not in source
    assert "graph.stream(" in source


def test_runtime_agents_use_adk_prompt_envelope_not_langchain_templates():
    prompt_agent_paths = [
        *Path("diverge/agents/analysts").glob("*_analyst.py"),
        *Path("diverge/agents/researchers").glob("*_researcher.py"),
        Path("diverge/agents/managers/research_manager.py"),
        Path("diverge/agents/managers/portfolio_manager.py"),
        Path("diverge/agents/managers/summary_agent.py"),
        Path("diverge/agents/trader/trader.py"),
        Path("diverge/agents/risk_mgmt/aggressive_debator.py"),
        Path("diverge/agents/risk_mgmt/conservative_debator.py"),
        Path("diverge/agents/risk_mgmt/neutral_debator.py"),
    ]

    for path in prompt_agent_paths:
        source = path.read_text(encoding="utf-8")

        assert "ChatPromptTemplate" not in source, path
        assert "MessagesPlaceholder" not in source, path
        assert "langchain_core.prompts" not in source, path
        assert "AdkPrompt" in source, path
        assert "llm.invoke(prompt)" not in source, path
        assert "llm.invoke(messages)" not in source, path


def test_agent_tools_use_local_tool_wrapper_not_langchain_tool_decorator():
    tool_paths = [
        Path("diverge/agents/utils/core_stock_tools.py"),
        Path("diverge/agents/utils/technical_indicators_tools.py"),
        Path("diverge/agents/utils/fundamental_data_tools.py"),
        Path("diverge/agents/utils/news_data_tools.py"),
        Path("diverge/agents/utils/search_tools.py"),
    ]

    for path in tool_paths:
        source = path.read_text(encoding="utf-8")
        assert "langchain_core.tools" not in source, path
        assert "diverge.agents.utils.tooling import tool" in source, path


def test_adk_tool_registry_builds_function_tools():
    from google.adk.tools import FunctionTool

    from diverge.runtime.tools import create_adk_tool_registry

    registry = create_adk_tool_registry()

    assert isinstance(registry["market"][0], FunctionTool)
    assert registry["market"][0].name == "get_stock_data"
    assert "get_insider_transactions" in {
        tool.name for tool in registry["fundamentals"]
    }


def test_adk_model_factory_uses_gemini_for_google_and_litellm_for_others():
    from google.adk.models.google_llm import Gemini
    from google.adk.models.lite_llm import LiteLlm
    from google.genai import types

    from diverge.runtime.model_factory import (
        create_adk_generation_config,
        create_adk_model,
    )

    google_model = create_adk_model(
        provider="google",
        model="gemini-3.1-pro-preview",
        base_url=None,
    )
    openai_model = create_adk_model(
        provider="openai",
        model="gpt-5.4-mini",
        base_url="https://api.openai.com/v1",
    )

    assert isinstance(google_model, Gemini)
    assert google_model.model == "gemini-3.1-pro-preview"
    assert isinstance(openai_model, LiteLlm)
    assert openai_model.model == "openai/gpt-5.4-mini"

    google_config = create_adk_generation_config(
        provider="google",
        thinking_level="high",
    )
    assert google_config.thinking_config.thinking_level == types.ThinkingLevel.HIGH


def test_sub2api_litellm_api_base_uses_openai_compatible_v1_endpoint():
    from diverge.runtime.model_factory import _litellm_kwargs

    kwargs = _litellm_kwargs(
        "sub2api",
        base_url="https://cc.z2blog.com",
        api_key=None,
        timeout=None,
        max_retries=None,
        extra={},
    )
    already_versioned_kwargs = _litellm_kwargs(
        "sub2api",
        base_url="https://cc.z2blog.com/v1/",
        api_key=None,
        timeout=None,
        max_retries=None,
        extra={},
    )

    assert kwargs["api_base"] == "https://cc.z2blog.com/v1"
    assert already_versioned_kwargs["api_base"] == "https://cc.z2blog.com/v1"


def test_sync_adk_invoke_flushes_litellm_logging_worker():
    import asyncio

    from diverge.runtime.model_factory import _run_coro_blocking

    class Worker:
        def __init__(self):
            self.flushed = False

        async def flush(self):
            self.flushed = True

    worker = Worker()
    module = types.SimpleNamespace(GLOBAL_LOGGING_WORKER=worker)

    with patch.dict(
        sys.modules,
        {"litellm.litellm_core_utils.logging_worker": module},
    ):
        result = _run_coro_blocking(asyncio.sleep(0, result="ok"))

    assert result == "ok"
    assert worker.flushed is True


def test_adk_adapter_extracts_sub2api_textual_tool_calls():
    from diverge.runtime.model_factory import _response_text_and_tools
    from diverge.runtime.tools import get_global_news, get_news

    class Part:
        def __init__(self, text):
            self.text = text
            self.function_call = None

    class Content:
        parts = [
            Part(
                'to=get_news query="SPY ETF news sentiment" '
                'start_date="2026-05-01" end_date="2026-05-08"'
            ),
            Part(
                " to=get_global_news "
                '{"curr_date":"2026-05-08","look_back_days":7,"limit":10}'
            ),
        ]

    class Response:
        content = Content()

    text, tool_calls = _response_text_and_tools(Response(), [get_news, get_global_news])

    assert "to=get_news" in text
    assert [call["name"] for call in tool_calls] == ["get_news", "get_global_news"]
    assert tool_calls[0]["args"]["query"] == "SPY ETF news sentiment"
    assert tool_calls[0]["args"]["start_date"] == "2026-05-01"
    assert tool_calls[1]["args"]["look_back_days"] == 7


def test_adk_prompt_conversion_preserves_tool_call_ids_for_litellm():
    from langchain_core.messages import AIMessage, ToolMessage

    from diverge.runtime.model_factory import _contents_from_prompt

    contents = _contents_from_prompt(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_stock_data",
                        "args": {"symbol": "SPY"},
                        "id": "call_market_1",
                    }
                ],
            ),
            ToolMessage(
                content="Date,Close\n2026-05-08,600",
                name="get_stock_data",
                tool_call_id="call_market_1",
            ),
        ]
    )

    assert contents[0].parts[0].function_call.id == "call_market_1"
    assert contents[1].parts[0].function_response.id == "call_market_1"


def test_diverge_graph_passes_round_limits_to_adk_runtime():
    with (
        patch("diverge.graph.trading_graph.set_config"),
        patch("diverge.graph.trading_graph.FinancialSituationMemory"),
        patch("diverge.graph.trading_graph.create_adk_model") as create_adk_model,
        patch("diverge.graph.trading_graph.AdkWorkflowRunner") as runner_cls,
    ):
        create_adk_model.return_value = object()
        config = {
            "llm_provider": "google",
            "quick_think_llm": "gemini-3.1-flash-preview",
            "deep_think_llm": "gemini-3.1-pro-preview",
            "backend_url": None,
            "data_cache_dir": "/tmp/diverge-cache",
            "eval_results_dir": "/tmp/diverge-eval",
            "max_debate_rounds": 2,
            "max_risk_discuss_rounds": 4,
        }

        DivergeGraph(selected_analysts=["market"], config=config)

    kwargs = runner_cls.call_args.kwargs
    assert kwargs["max_debate_rounds"] == 2
    assert kwargs["max_risk_discuss_rounds"] == 4
