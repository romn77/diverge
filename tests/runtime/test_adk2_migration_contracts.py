from pathlib import Path
from unittest.mock import patch

from diverge.graph.trading_graph import DivergeGraph


def test_pyproject_pins_adk_2_beta_and_removes_langgraph():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'requires-python = ">=3.11"' in pyproject
    assert '"google-adk==2.0.0b1"' in pyproject
    assert '"litellm>=1.83.14"' in pyproject
    assert "langgraph" not in pyproject


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


def test_adk_tool_registry_builds_function_tools():
    from google.adk.tools import FunctionTool

    from diverge.runtime.tools import create_adk_tool_registry

    registry = create_adk_tool_registry()

    assert isinstance(registry["market"][0], FunctionTool)
    assert registry["market"][0].name == "get_stock_data"
    assert "get_insider_transactions" in {tool.name for tool in registry["fundamentals"]}


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
