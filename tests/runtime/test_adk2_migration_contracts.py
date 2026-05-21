import os
import sys
import types
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


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


def test_runner_uses_adk_native_runtime_directly():
    source = Path("diverge/runner.py").read_text(encoding="utf-8")

    assert "DivergeGraph" not in source
    assert "graph.stream(" not in source
    assert "stream_analysis_state_chunks(" in source


def test_adk_web_standard_app_entrypoint_exists():
    agent_entrypoint = Path("adk_apps/diverge_analysis/agent.py").read_text(
        encoding="utf-8"
    )
    web_app = Path("diverge/runtime/adk_native/web_app.py").read_text(encoding="utf-8")

    assert "app = build_adk_web_app()" in agent_entrypoint
    assert "from google.adk.apps import App" in web_app
    assert "FunctionNode" in web_app
    assert "build_native_analysis_workflow(" in web_app


def test_legacy_graph_runtime_modules_are_removed():
    assert not list(Path("diverge/graph").glob("*.py"))
    assert not Path("diverge/runtime/workflow_runner.py").exists()


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
        if path.name != "portfolio_manager.py":
            assert "AdkPrompt" in source, path
        assert "def run(" not in source, path
        assert "def build_" in source, path
        assert "DivergeAgentNode" not in source, path
        assert "AgentCallSpec" not in source, path
        assert "def build_call(" not in source, path
        assert "def apply_response(" not in source, path
        assert ".invoke(" not in source, path
        assert "bind_tools(" not in source, path


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
    assert getattr(openai_model, "_diverge_timeout_seconds") == 300.0

    google_config = create_adk_generation_config(
        provider="google",
        thinking_level="high",
    )
    assert google_config.thinking_config.thinking_level == types.ThinkingLevel.HIGH


def test_adk_google_model_uses_gemini_base_url_env():
    from google.adk.models.google_llm import Gemini

    from diverge.runtime.model_factory import DivergeGemini, create_adk_model

    with patch.dict(
        "os.environ",
        {"GOOGLE_GEMINI_BASE_URL": "https://cc.z2blog.com"},
        clear=True,
    ):
        google_model = create_adk_model(
            provider="google",
            model="gemini-2.5-flash",
            base_url="https://generativelanguage.googleapis.com/v1",
        )

    assert isinstance(google_model, Gemini)
    assert isinstance(google_model, DivergeGemini)
    assert google_model.base_url == "https://cc.z2blog.com"


def test_diverge_gemini_api_client_uses_tracking_header_payload():
    from google.genai import Client

    from diverge.runtime.model_factory import DivergeGemini

    google_model = DivergeGemini(
        model="gemini-2.5-flash",
        base_url="https://cc.z2blog.com",
        api_key="test-key",
    )

    assert isinstance(google_model.api_client, Client)


def test_adk_model_factory_uses_env_timeout_fallback():
    from diverge.runtime.model_factory import create_adk_model

    with patch.dict(os.environ, {"DIVERGE_LLM_TIMEOUT_SECONDS": "12.5"}):
        model = create_adk_model(
            provider="openai",
            model="gpt-5.4-mini",
            base_url="https://api.openai.com/v1",
        )

    assert getattr(model, "_diverge_timeout_seconds") == 12.5


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


def test_mimo_litellm_uses_openai_compatible_base_and_api_key_env():
    from diverge.runtime.model_factory import _litellm_kwargs, _prefixed_litellm_model

    with patch.dict(os.environ, {"MIMO_API_KEY": "test-mimo-key"}, clear=True):
        kwargs = _litellm_kwargs(
            "mimo",
            base_url="https://api.xiaomimimo.com/v1",
            api_key=None,
            timeout=None,
            max_retries=None,
            extra={},
        )

    assert _prefixed_litellm_model("mimo", "mimo-v2.5-pro") == "openai/mimo-v2.5-pro"
    assert kwargs["api_base"] == "https://api.xiaomimimo.com/v1"
    assert kwargs["api_key"] == "test-mimo-key"
    assert kwargs["custom_llm_provider"] == "openai"


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


def test_litellm_blocking_runner_reuses_one_loop_across_threads():
    from diverge.runtime.model_factory import (
        _run_coro_blocking,
        _shutdown_litellm_loop_for_tests,
    )

    async def current_loop_id():
        await asyncio.sleep(0)
        return id(asyncio.get_running_loop())

    try:
        with ThreadPoolExecutor(max_workers=6) as executor:
            loop_ids = list(
                executor.map(
                    lambda _: _run_coro_blocking(
                        current_loop_id(),
                        persistent_loop=True,
                    ),
                    range(24),
                )
            )

        assert len(set(loop_ids)) == 1
    finally:
        _shutdown_litellm_loop_for_tests()


def test_adk_native_runner_builds_decision_nodes_from_round_limits():
    from diverge.runtime.adk_native.runner import (
        _NativeRuntimeResources,
        _build_native_decision_nodes,
    )

    resources = _NativeRuntimeResources(
        tool_nodes={},
        bull_memory=object(),
        bear_memory=object(),
        trader_memory=object(),
        invest_judge_memory=object(),
        portfolio_manager_memory=object(),
        quick_model="fake-quick-model",
        deep_model="fake-portfolio-model",
    )
    nodes = _build_native_decision_nodes(
        resources,
        {"max_debate_rounds": 2, "max_risk_discuss_rounds": 4},
    )
    names = [node.name for node in nodes]

    runner_source = Path("diverge/runtime/adk_native/runner.py").read_text(
        encoding="utf-8"
    )
    agents_source = Path("diverge/runtime/adk_native/agents.py").read_text(
        encoding="utf-8"
    )
    init_source = Path("diverge/runtime/adk_native/__init__.py").read_text(
        encoding="utf-8"
    )

    assert "NativeStateAgent" not in runner_source
    assert "NativeAnalystAgent" not in runner_source
    assert "AdkChatModel" not in runner_source
    assert "NativeAnalystAgent" not in agents_source
    assert "NativeAnalystAgent" not in init_source
    assert names[:6] == [
        "bull_researcher_1_start",
        "bull_researcher_1",
        "bull_researcher_1_finalize",
        "bear_researcher_1_start",
        "bear_researcher_1",
        "bear_researcher_1_finalize",
    ]
    assert names[6:12] == [
        "bull_researcher_2_start",
        "bull_researcher_2",
        "bull_researcher_2_finalize",
        "bear_researcher_2_start",
        "bear_researcher_2",
        "bear_researcher_2_finalize",
    ]
    assert names[12:18] == [
        "research_manager_start",
        "research_manager",
        "research_manager_finalize",
        "trader_start",
        "trader",
        "trader_finalize",
    ]
    risk_llm_names = [
        name
        for name in names
        if not name.endswith("_start") and not name.endswith("_finalize")
    ]
    assert len([name for name in risk_llm_names if name.startswith("aggressive_analyst")]) == 5
    assert len([name for name in risk_llm_names if name.startswith("conservative_analyst")]) == 5
    assert len([name for name in risk_llm_names if name.startswith("neutral_analyst")]) == 5
    assert names[-3:] == [
        "portfolio_manager_start",
        "portfolio_manager",
        "portfolio_manager_finalize",
    ]
