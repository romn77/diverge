from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_uses_direct_agent_module_imports_for_editor_navigation():
    native_runner = (ROOT / "diverge/runtime/adk_native/runner.py").read_text()
    native_specs = (ROOT / "diverge/runtime/adk_native/specs.py").read_text()

    assert "from diverge.agents import (" not in native_runner
    assert "create_bear_researcher" not in native_runner
    assert "create_market_analyst" not in native_runner
    assert "build_bear_researcher_prompt" in native_runner
    assert "build_market_analyst_prompt" not in native_specs
    assert "MARKET_ANALYST_AGENT" in native_specs
    assert "SOCIAL_MEDIA_ANALYST_AGENT" in native_specs
    assert "build_news_analyst_prompt" not in native_specs
    assert "NEWS_ANALYST_AGENT" in native_specs
    assert "FUNDAMENTALS_ANALYST_AGENT" in native_specs
    assert "BearResearcher" not in native_runner
    assert "MarketAnalyst" not in native_runner


def test_agents_package_keeps_static_type_stub_for_direct_function_exports():
    stub = (ROOT / "diverge/agents/__init__.pyi").read_text()

    assert "diverge.agents.researchers.bear_researcher" in stub
    assert "build_bear_researcher_prompt" in stub
    assert "create_bear_researcher" not in stub
    assert "DivergeAgentNode" not in stub
