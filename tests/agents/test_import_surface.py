from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_uses_direct_agent_module_imports_for_editor_navigation():
    native_runner = (ROOT / "diverge/runtime/adk_native/runner.py").read_text()

    assert "from diverge.agents import (" not in native_runner
    assert "create_bear_researcher" not in native_runner
    assert "create_market_analyst" not in native_runner
    assert (
        "from diverge.agents.researchers.bear_researcher import BearResearcher"
        in native_runner
    )
    assert (
        "from diverge.agents.analysts.market_analyst import MarketAnalyst"
        in native_runner
    )


def test_agents_package_keeps_static_type_stub_for_lazy_exports():
    stub = (ROOT / "diverge/agents/__init__.pyi").read_text()

    assert "diverge.agents.researchers.bear_researcher" in stub
    assert "BearResearcher" in stub
    assert "create_bear_researcher" not in stub
    assert "from diverge.agents.base import DivergeAgentNode" in stub
