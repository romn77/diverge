from __future__ import annotations

import json
from types import SimpleNamespace
from typing import ClassVar

from google.adk.apps import App
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.workflow import FunctionNode, Workflow
from google.adk.workflow import START
from google.genai import types
from langchain_core.messages import AIMessage

from diverge.agents.managers.portfolio_manager import PortfolioManagerStructuredOutput
from diverge.agents.report_output import (
    AggressiveRiskStructuredOutput,
    BearCaseStructuredOutput,
    BullCaseStructuredOutput,
    ConservativeRiskStructuredOutput,
    FundamentalsReportStructuredOutput,
    MarketReportStructuredOutput,
    NeutralRiskStructuredOutput,
    NewsReportStructuredOutput,
    ResearchDecisionStructuredOutput,
    SentimentReportStructuredOutput,
    TraderStructuredOutput,
)
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


def test_native_portfolio_callback_replaces_invalid_schema_response():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text='{"decision_report":"raw report","decision_card":{"rating":"HOLD"}}'
                )
            ],
        )
    )

    replacement = adk_native_runner._portfolio_after_model_callback(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["decision_report"].startswith('{"decision_report"')
    assert payload["decision_card"]["trade_readiness"] == "DATA_INSUFFICIENT"
    assert callback_context.state["runtime_warnings"][0]["kind"] == (
        "structured_output_validation_failed"
    )


def test_native_portfolio_callback_recovers_partial_json_card():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    raw_payload = {
        "decision_report": "raw report",
        "decision_card": {
            "rating": "HOLD",
            "action": "WATCH",
            "confidence": "low",
            "conviction_score": 42,
            "thesis": "TLN 显示出单季度盈利与经营现金流修复，但证据仍停留在单点改善。",
            "key_reasons": ["2026 年一季度经营现金流为正。"],
            "risk_summary": "高杠杆可能放大股权波动。",
        },
    }
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(text=json.dumps(raw_payload, ensure_ascii=False))
            ],
        )
    )

    replacement = adk_native_runner._portfolio_after_model_callback(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["decision_report"] == "raw report"
    assert payload["decision_card"]["rating"] == "HOLD"
    assert payload["decision_card"]["one_line_summary"].startswith("TLN 显示出")
    assert payload["decision_card"]["key_reasons"][0]["evidence"].startswith(
        "2026 年一季度"
    )
    assert payload["decision_card"]["key_risks"] == ["高杠杆可能放大股权波动。"]
    assert callback_context.state["runtime_warnings"][0]["kind"] == (
        "structured_output_validation_failed"
    )


def test_native_portfolio_callback_normalizes_partial_card_evidence_enums():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    raw_payload = {
        "decision_report": "raw report",
        "decision_card": {
            "rating": "HOLD",
            "action": "WATCH",
            "confidence": "low",
            "conviction_score": 50,
            "time_horizon": "Not specified",
            "one_line_summary": "维持核心持有，暂停新增敞口。",
            "thesis": "趋势仍在，但动能降温和信息缺口压低新增仓位赔率。",
            "key_reasons": [
                {
                    "pillar": "risk",
                    "point": "高位回撤风险",
                    "evidence": "短线动能降温。",
                    "strength": "high",
                },
                {
                    "pillar": "momentum",
                    "point": "动能边际走弱",
                    "evidence": "MACD 柱状图转负。",
                    "strength": "high",
                },
                {
                    "pillar": "data_quality",
                    "point": "关键数据缺失",
                    "evidence": "缺少资金流和持仓集中度。",
                    "strength": "low",
                },
            ],
        },
    }
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(text=json.dumps(raw_payload, ensure_ascii=False))
            ],
        )
    )

    replacement = adk_native_runner._portfolio_after_model_callback(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    reasons = payload["decision_card"]["key_reasons"]
    assert reasons[0]["pillar"] == "risk"
    assert reasons[0]["strength"] == "strong"
    assert reasons[1]["pillar"] == "technical"
    assert reasons[1]["strength"] == "strong"
    assert reasons[2]["pillar"] == "portfolio"
    assert reasons[2]["strength"] == "weak"


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
    class FakeMemory:
        def get_memories(self, _current_situation, n_matches=2):
            return []

    def structured_payload_for_schema(schema):
        report = f"## {schema.__name__}\n\nNative structured response."
        common = {
            "signal": "HOLD",
            "signal_confidence": "medium",
            "summary": "Structured native runtime response.",
            "evidence_blocks": [],
            "unknowns": [],
        }
        if schema is MarketReportStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "market",
                    "stance": "neutral",
                    "trend_direction": "neutral",
                    "key_levels": {"support": [], "resistance": []},
                    "indicators": [],
                    "volatility": "moderate",
                },
            }
        if schema is SentimentReportStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "sentiment",
                    "stance": "neutral",
                    "overall_sentiment": "neutral",
                    "sentiment_score": None,
                    "key_topics": [],
                    "social_buzz": None,
                },
            }
        if schema is NewsReportStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "news",
                    "stance": "neutral",
                    "market_impact": "neutral",
                    "key_events": [],
                    "macro_outlook": None,
                },
            }
        if schema is FundamentalsReportStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "fundamentals",
                    "stance": "neutral",
                    "metrics": [],
                    "financial_health": None,
                },
            }
        if schema is BullCaseStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "bull_case",
                    "stance": "bullish",
                    "contrary_evidence": [],
                    "key_arguments": [],
                    "counterpoints": [],
                },
            }
        if schema is BearCaseStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "bear_case",
                    "stance": "bearish",
                    "contrary_evidence": [],
                    "key_arguments": [],
                    "counterpoints": [],
                },
            }
        if schema is ResearchDecisionStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "research_decision",
                    "stance": "neutral",
                    "decision": "HOLD",
                    "aligned_with": "bull",
                    "rationale": "The native fake model is neutral.",
                    "action_items": ["Wait for stronger evidence."],
                },
            }
        if schema is TraderStructuredOutput:
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": "trader",
                    "stance": "neutral",
                    "entry_exit": {
                        "action": "Watch",
                        "entry_condition": "Wait for confirmation.",
                        "exit_target": None,
                        "stop_loss": None,
                        "invalidation": "Evidence weakens.",
                        "re_entry": None,
                    },
                    "position_sizing": "Small or none.",
                    "risk_budget": "Low.",
                    "risk_factors": ["Execution risk"],
                },
            }
        if schema in {
            AggressiveRiskStructuredOutput,
            ConservativeRiskStructuredOutput,
            NeutralRiskStructuredOutput,
        }:
            category = {
                AggressiveRiskStructuredOutput: "risk_aggressive",
                ConservativeRiskStructuredOutput: "risk_conservative",
                NeutralRiskStructuredOutput: "risk_neutral",
            }[schema]
            stance_label = {
                AggressiveRiskStructuredOutput: "Aggressive",
                ConservativeRiskStructuredOutput: "Conservative",
                NeutralRiskStructuredOutput: "Neutral",
            }[schema]
            risk_assessment = {
                AggressiveRiskStructuredOutput: "high",
                ConservativeRiskStructuredOutput: "low",
                NeutralRiskStructuredOutput: "moderate",
            }[schema]
            return {
                "report_markdown": report,
                "highlights": {
                    **common,
                    "category": category,
                    "stance": "neutral",
                    "stance_label": stance_label,
                    "core_argument": "Keep risk controlled in the fake runtime.",
                    "risk_assessment": risk_assessment,
                    "key_recommendations": ["Keep risk contained."],
                    "risk_budget": None,
                },
            }
        if schema is PortfolioManagerStructuredOutput:
            return {
                "decision_report": "## Portfolio Manager Decision\n\nRating: HOLD.",
                "decision_card": {
                    "rating": "HOLD",
                    "action": "WATCH",
                    "confidence": "medium",
                    "conviction_score": 55,
                    "time_horizon": "5-20 trading days",
                    "one_line_summary": "Watch for cleaner confirmation.",
                    "thesis": "The debate supports caution until stronger evidence arrives.",
                    "key_reasons": [
                        {
                            "pillar": "portfolio",
                            "point": "Balanced risk",
                            "evidence": "Risk debate did not support immediate action.",
                            "strength": "medium",
                        }
                    ],
                    "key_risks": ["Execution risk"],
                    "trade_readiness": "WAITING_FOR_TRIGGER",
                    "data_quality_level": "partial",
                },
            }
        raise AssertionError(f"Unexpected response schema: {schema!r}")

    class FakeNativeStructuredModel(BaseLlm):
        seen_response_schemas: ClassVar[set] = set()

        async def generate_content_async(self, llm_request, stream=False):
            schema = llm_request.config.response_schema
            type(self).seen_response_schemas.add(schema)
            payload = structured_payload_for_schema(schema)
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text=json.dumps(payload, ensure_ascii=False)
                        )
                    ],
                )
            )

    captured_resource_configs = []
    quick_model = FakeNativeStructuredModel(model="fake-quick-model")
    deep_model = FakeNativeStructuredModel(model="fake-deep-model")

    def fake_create_runtime_resources(config):
        captured_resource_configs.append(dict(config))
        return adk_native_runner._NativeRuntimeResources(
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
            quick_model=quick_model,
            deep_model=deep_model,
            generation_config=None,
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
    assert any("MarketReportStructuredOutput" in chunk["market_report"] for chunk in chunks)
    assert any(
        "SentimentReportStructuredOutput" in chunk["sentiment_report"]
        for chunk in chunks
    )
    assert any(
        "NewsReportStructuredOutput" in chunk["news_report"] for chunk in chunks
    )
    assert any(
        "FundamentalsReportStructuredOutput" in chunk["fundamentals_report"]
        for chunk in chunks
    )
    assert chunks[-1]["investment_plan"]
    assert chunks[-1]["trader_investment_plan"]
    assert chunks[-1]["final_trade_decision"]
    assert chunks[-1]["portfolio_decision_card"]["rating"] == "HOLD"
    assert {
        MarketReportStructuredOutput,
        SentimentReportStructuredOutput,
        NewsReportStructuredOutput,
        FundamentalsReportStructuredOutput,
        BullCaseStructuredOutput,
        BearCaseStructuredOutput,
        ResearchDecisionStructuredOutput,
        TraderStructuredOutput,
        AggressiveRiskStructuredOutput,
        ConservativeRiskStructuredOutput,
        NeutralRiskStructuredOutput,
        PortfolioManagerStructuredOutput,
    }.issubset(FakeNativeStructuredModel.seen_response_schemas)
