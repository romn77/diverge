from __future__ import annotations

from types import SimpleNamespace

from google.adk.apps import App
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.workflow import FunctionNode, Workflow
from google.adk.workflow import START
from langchain_core.messages import AIMessage

from diverge.runtime.adk_native import runner as adk_native_runner
from diverge.runtime.adk_native.progress_adapter import state_delta_from_event
from diverge.runtime.adk_native.runner import stream_analysis_state_chunks
from diverge.runtime.adk_native.state_adapter import merge_state_delta
from diverge.runtime.adk_native.web_app import initialize_adk_web_state
from diverge.runtime.adk_native.workflow import build_analysis_workflow
from diverge.runtime.analysis_schema import HISTORICAL_TRADE_FEEDBACK_KEY
from diverge.runtime.state import create_initial_state
from diverge.runtime.tool_loop import looks_like_incomplete_tool_preface
from diverge.runtime.tools import AdkToolCollection


def test_state_adapter_applies_adk_state_delta_without_mutating_input():
    original = {"market_report": "", "nested": {"value": 1}}
    merged = merge_state_delta(original, {"market_report": "Updated"})

    assert merged["market_report"] == "Updated"
    assert original["market_report"] == ""
    assert merged["nested"] == {"value": 1}


def test_progress_adapter_extracts_event_actions_state_delta():
    event = SimpleNamespace(
        actions=SimpleNamespace(
            state_delta={
                "runtime_progress_events": [
                    {
                        "id": "runtime-progress-1",
                        "current_agent": "Market Analyst",
                        "message": "Market Analyst started.",
                    }
                ]
            }
        )
    )

    assert (
        state_delta_from_event(event)["runtime_progress_events"][0]["current_agent"]
        == "Market Analyst"
    )


def test_tool_preface_detector_retries_chinese_literal_tool_calls():
    content = (
        "我们需要先获取股票数据，然后调用指标。"
        + "需要确认参数。" * 120
        + "\n\n```python\nget_stock_data(ticker='AMD', days=120)\n```"
    )

    assert looks_like_incomplete_tool_preface(AIMessage(content=content))


def test_tool_preface_detector_accepts_completed_highlight_report():
    content = (
        "使用 get_stock_data 和 get_indicators 得到的证据显示趋势偏强。\n\n"
        "```json-highlights\n"
        '{"category":"market","signal":"HOLD","signal_confidence":"medium"}\n'
        "```"
    )

    assert not looks_like_incomplete_tool_preface(AIMessage(content=content))


def test_analysis_workflow_uses_native_nodes_without_bridge():
    def node(_ctx):
        return None

    workflow = build_analysis_workflow([FunctionNode(func=node, name="native_node")])

    assert isinstance(workflow, Workflow)
    assert workflow.name == "diverge_adk_native_analysis"
    assert workflow.max_concurrency == 1


def test_adk_web_app_entry_loads_with_standard_agent_loader(monkeypatch):
    import sys

    from diverge.runtime.adk_native import web_app

    def noop(_ctx):
        return None

    def fake_build_native_analysis_workflow(
        *,
        selected_analysts,
        config,
        name,
        prefix_nodes=(),
    ):
        del selected_analysts, config
        return Workflow(
            name=name,
            edges=[
                (START, node)
                for node in [
                    *prefix_nodes,
                    FunctionNode(func=noop, name="noop_analysis"),
                ]
            ],
            max_concurrency=1,
        )

    monkeypatch.setattr(
        web_app,
        "build_native_analysis_workflow",
        fake_build_native_analysis_workflow,
    )
    sys.modules.pop("diverge_analysis", None)
    sys.modules.pop("diverge_analysis.agent", None)

    loaded = AgentLoader("adk_apps").load_agent("diverge_analysis")

    assert isinstance(loaded, App)
    assert loaded.name == "diverge_analysis"
    assert isinstance(loaded.root_agent, Workflow)
    assert loaded.root_agent.name == "diverge_adk_web_analysis"


def test_adk_web_initializer_creates_diverge_state_from_user_content():
    class State(dict):
        def to_dict(self):
            return dict(self)

    ctx = SimpleNamespace(
        state=State(
            {
                "output_language": "zh-CN",
                "portfolio_context": "cash: 50%",
                HISTORICAL_TRADE_FEEDBACK_KEY: "Previous trades preferred quality.",
            }
        ),
        user_content=SimpleNamespace(
            parts=[SimpleNamespace(text="Analyze MSFT with full debate.")]
        ),
    )

    initialize_adk_web_state(
        ctx,
        config={"output_language": "en"},
        selected_analysts=["market", "news"],
    )

    assert ctx.state["company_of_interest"] == "MSFT"
    assert ctx.state["output_language"] == "zh-CN"
    assert ctx.state["portfolio_context"] == "cash: 50%"
    assert ctx.state["selected_analysts"] == ["market", "news"]
    assert ctx.state["adk_runtime"] == "adk_native"
    assert ctx.state["investment_debate_state"]
    assert ctx.state["risk_debate_state"]
    assert ctx.state["messages"][0] == (
        "human",
        "Previous trades preferred quality.",
    )
    assert ctx.state["messages"][1] == ("human", "MSFT")


def test_adk_native_runner_streams_native_workflow_chunks(monkeypatch):
    class FakeLlm:
        def __init__(self):
            self.invocations = 0

        def invoke(self, _prompt):
            self.invocations += 1
            return AIMessage(content=f"llm response {self.invocations}")

    class FakeMemory:
        def get_memories(self, _current_situation, n_matches=2):
            return []

    class FakeAnalyst:
        def __init__(self, _llm, *, name, report_key, content):
            self.name = name
            self.report_key = report_key
            self.content = content

        def __call__(self, _state):
            return {
                "messages": [AIMessage(content=self.content, tool_calls=[])],
                self.report_key: self.content,
            }

    fake_analyst_classes = {
        "market": lambda llm: FakeAnalyst(
            llm,
            name="market_analyst",
            report_key="market_report",
            content="ADK native market report",
        ),
        "social": lambda llm: FakeAnalyst(
            llm,
            name="social_media_analyst",
            report_key="sentiment_report",
            content="ADK native sentiment report",
        ),
        "news": lambda llm: FakeAnalyst(
            llm,
            name="news_analyst",
            report_key="news_report",
            content="ADK native news report",
        ),
        "fundamentals": lambda llm: FakeAnalyst(
            llm,
            name="fundamentals_analyst",
            report_key="fundamentals_report",
            content="ADK native fundamentals report",
        ),
    }

    captured_resource_configs = []

    def fake_create_runtime_resources(config):
        captured_resource_configs.append(dict(config))
        return adk_native_runner._NativeRuntimeResources(
            quick_thinking_llm=FakeLlm(),
            deep_thinking_llm=FakeLlm(),
            tool_nodes={
                "market": AdkToolCollection(()),
                "social": AdkToolCollection(()),
                "news": AdkToolCollection(()),
                "fundamentals": AdkToolCollection(()),
            },
            bull_memory=FakeMemory(),
            bear_memory=FakeMemory(),
            trader_memory=FakeMemory(),
            invest_judge_memory=FakeMemory(),
            portfolio_manager_memory=FakeMemory(),
        )

    monkeypatch.setattr(
        adk_native_runner,
        "_NATIVE_ANALYST_CLASSES",
        fake_analyst_classes,
    )
    monkeypatch.setattr(
        adk_native_runner,
        "_create_runtime_resources",
        fake_create_runtime_resources,
    )

    chunks = list(
        stream_analysis_state_chunks(
            selected_analysts=["market", "social", "news", "fundamentals"],
            config={"max_recur_limit": 10},
            init_agent_state=create_initial_state("MSFT", "2026-04-03"),
            graph_args={},
        )
    )

    assert captured_resource_configs == [{"max_recur_limit": 10}]
    assert any(chunk["market_report"] == "ADK native market report" for chunk in chunks)
    assert any(
        chunk["sentiment_report"] == "ADK native sentiment report" for chunk in chunks
    )
    assert any(
        chunk["news_report"].startswith("ADK native news report") for chunk in chunks
    )
    assert any(
        chunk["fundamentals_report"].startswith("ADK native fundamentals report")
        for chunk in chunks
    )
    assert chunks[-1]["investment_plan"]
    assert chunks[-1]["trader_investment_plan"]
    assert chunks[-1]["final_trade_decision"]
