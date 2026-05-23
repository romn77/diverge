from __future__ import annotations

import json
from types import SimpleNamespace
from typing import ClassVar

from google.adk.apps import App
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import FunctionTool
from google.adk.workflow import FunctionNode, Workflow
from google.adk.workflow import START
from google.genai import types
from langchain_core.messages import AIMessage

from diverge.agents.analysts.fundamentals_analyst import FUNDAMENTALS_ANALYST_AGENT
from diverge.agents.analysts.market_analyst import MARKET_ANALYST_AGENT
from diverge.agents.analysts.news_analyst import NEWS_ANALYST_AGENT
from diverge.agents.analysts.news_analyst import build_news_analyst_prompt
from diverge.agents.analysts.social_media_analyst import SOCIAL_MEDIA_ANALYST_AGENT
from diverge.agents.managers.portfolio_manager import (
    PORTFOLIO_MANAGER_AGENT,
    PortfolioManagerStructuredOutput,
)
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
from diverge.runtime.adk_native.agents import append_runtime_progress_event
from diverge.runtime.adk_native import callbacks as adk_callbacks
from diverge.runtime.adk_native import evidence as adk_evidence
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


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    del symbol, start_date, end_date
    return "stock data"


def get_indicators(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    del symbol, indicator, curr_date, look_back_days
    return "indicators"


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    del ticker, start_date, end_date
    return "news"


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    del curr_date, look_back_days, limit
    return "global news"


def web_search_evidence(
    query: str = "",
    purpose: str = "default",
    max_results: int = 5,
) -> str:
    del query, purpose, max_results
    return "search evidence"


def get_fundamentals(ticker: str, curr_date: str) -> str:
    del ticker, curr_date
    return "fundamentals"


def get_balance_sheet(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
) -> str:
    del ticker, freq, curr_date
    return "balance sheet"


def get_cashflow(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
) -> str:
    del ticker, freq, curr_date
    return "cashflow"


def get_income_statement(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
) -> str:
    del ticker, freq, curr_date
    return "income statement"


def get_insider_transactions(ticker: str) -> str:
    del ticker
    return "insider transactions"


def _tool_collection(*tools) -> AdkToolCollection:
    return AdkToolCollection(tuple(FunctionTool(tool) for tool in tools))


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


def test_runtime_progress_event_append_reassigns_state_list_for_adk_deltas():
    state = {
        "runtime_progress_events": [
            {
                "id": "runtime-progress-1",
                "current_agent": "News Analyst Evidence",
                "message": "News Analyst Evidence started.",
            }
        ]
    }
    original_events = state["runtime_progress_events"]

    append_runtime_progress_event(
        state,
        current_agent="News Analyst Report",
        message="News Analyst Report started.",
    )

    assert state["runtime_progress_events"] is not original_events
    assert original_events == [
        {
            "id": "runtime-progress-1",
            "current_agent": "News Analyst Evidence",
            "message": "News Analyst Evidence started.",
        }
    ]
    assert state["runtime_progress_events"][-1] == {
        "id": "runtime-progress-2",
        "current_agent": "News Analyst Report",
        "message": "News Analyst Report started.",
    }


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


def test_native_analysts_use_two_stage_evidence_report_contract():
    class FakeModel(BaseLlm):
        async def generate_content_async(self, llm_request, stream=False):
            raise AssertionError(
                "model should not be invoked by node construction test"
            )

    resources = adk_native_runner._NativeRuntimeResources(
        tool_nodes={
            "market": _tool_collection(get_stock_data, get_indicators),
            "social": _tool_collection(get_news, web_search_evidence),
            "news": _tool_collection(
                get_news,
                get_global_news,
                web_search_evidence,
            ),
            "fundamentals": _tool_collection(
                get_fundamentals,
                get_balance_sheet,
                get_cashflow,
                get_income_statement,
                get_insider_transactions,
            ),
        },
        bull_memory=object(),
        bear_memory=object(),
        trader_memory=object(),
        invest_judge_memory=object(),
        portfolio_manager_memory=object(),
        quick_model=FakeModel(model="fake-quick-model"),
        deep_model=FakeModel(model="fake-deep-model"),
        generation_config=None,
    )
    cases = {
        "market": (
            MARKET_ANALYST_AGENT,
            "market_analyst",
            "market_evidence_notes",
            MarketReportStructuredOutput,
            "market_report_structured",
        ),
        "social": (
            SOCIAL_MEDIA_ANALYST_AGENT,
            "social_media_analyst",
            "sentiment_evidence_notes",
            SentimentReportStructuredOutput,
            "sentiment_report_structured",
        ),
        "news": (
            NEWS_ANALYST_AGENT,
            "news_analyst",
            "news_evidence_notes",
            NewsReportStructuredOutput,
            "news_report_structured",
        ),
        "fundamentals": (
            FUNDAMENTALS_ANALYST_AGENT,
            "fundamentals_analyst",
            "fundamentals_evidence_notes",
            FundamentalsReportStructuredOutput,
            "fundamentals_report_structured",
        ),
    }

    for analyst, (
        turn,
        agent_name,
        evidence_key,
        output_schema,
        output_key,
    ) in cases.items():
        del analyst
        nodes = adk_native_runner._build_native_analyst_nodes(turn, resources)
        evidence_agent = nodes[1]
        report_agent = nodes[4]

        assert [node.name for node in nodes] == [
            f"{agent_name}_evidence_start",
            f"{agent_name}_evidence",
            f"{agent_name}_evidence_finalize",
            f"{agent_name}_report_start",
            f"{agent_name}_report",
            f"{agent_name}_finalize",
        ]
        assert evidence_agent.output_schema is None
        assert evidence_agent.output_key == evidence_key
        assert [tool.name for tool in evidence_agent.tools] == list(turn.tool_names)
        assert report_agent.output_schema is output_schema
        assert report_agent.output_key == output_key
        assert report_agent.tools == []


def test_news_evidence_tool_callback_counts_evidence_tool_calls():
    state = {"runtime_warnings": []}
    callback = adk_evidence.analyst_after_tool_callback(
        "News Analyst Evidence",
        evidence_tool_calls_key="news_evidence_notes_evidence_tool_calls",
    )

    callback(
        SimpleNamespace(name="get_news"),
        {},
        SimpleNamespace(state=state),
        "news evidence",
    )

    assert state["news_evidence_notes_evidence_tool_calls"] == 1
    assert state["runtime_progress_events"][-1]["current_agent"] == (
        "News Analyst Evidence"
    )


def test_news_evidence_finalize_warns_when_no_evidence_tool_was_called():
    state = {"runtime_warnings": []}
    finalize = adk_evidence.finalize_evidence_turn(
        evidence_output_key="news_evidence_notes",
        evidence_tool_calls_key="news_evidence_notes_evidence_tool_calls",
        display_name="News Analyst Evidence",
    )

    finalize(SimpleNamespace(state=state))

    assert state["news_evidence_notes"].startswith("No evidence-gathering tool")
    assert state["runtime_warnings"][-1] == {
        "stage": "News Analyst Evidence",
        "kind": "missing_evidence_tool_call",
        "message": (
            "News Analyst Evidence did not complete any evidence-gathering "
            "tool call; the report phase will receive a data-insufficient "
            "evidence note."
        ),
    }


def test_news_report_instruction_receives_evidence_notes():
    state = create_initial_state("CEG", "2026-05-20", output_language="cn")
    state["news_evidence_notes"] = "get_news: CEG had mixed source-backed news."
    instruction = adk_native_runner._native_report_prompt_instruction(
        build_news_analyst_prompt,
        evidence_output_key="news_evidence_notes",
    )

    prompt = instruction(SimpleNamespace(state=state))

    assert "Report phase contract" in prompt
    assert "You have no tools" in prompt
    assert "get_news: CEG had mixed source-backed news." in prompt


def test_news_evidence_model_error_callback_returns_data_insufficient_notes():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})

    replacement = adk_callbacks.evidence_model_error_callback(
        "news_evidence_notes",
        "News Analyst Evidence",
    )(
        callback_context=callback_context,
        llm_request=object(),
        error=Exception("504 Gateway Time-out"),
    )

    assert replacement is not None
    assert "data-insufficient" in replacement.content.parts[0].text
    assert callback_context.state["news_evidence_notes"].endswith(
        "data-insufficient unless regenerated."
    )
    assert callback_context.state["runtime_warnings"][-1]["kind"] == (
        "transient_llm_error"
    )


def test_native_structured_model_error_callback_returns_schema_fallback_for_timeout():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})

    replacement = adk_callbacks.structured_model_error_callback(
        NewsReportStructuredOutput,
        "News Analyst",
    )(
        callback_context=callback_context,
        llm_request=object(),
        error=Exception("504 Gateway Time-out"),
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["report_markdown"].startswith("## News Analyst Fallback")
    assert payload["highlights"]["category"] == "news"
    assert payload["highlights"]["signal"] == "HOLD"
    assert callback_context.state["runtime_warnings"] == [
        {
            "stage": "News Analyst",
            "kind": "transient_llm_error",
            "message": (
                "News Analyst used a conservative fallback because the LLM "
                "request failed with a transient connection error: "
                "504 Gateway Time-out"
            ),
        }
    ]


def test_native_structured_callback_repairs_json_with_trailing_characters():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    valid_payload = {
        "report_markdown": "## Bear case\n\nAMD has valuation risk.",
        "highlights": {
            "category": "bear_case",
            "signal": "UNDERWEIGHT",
            "signal_confidence": "medium",
            "summary": "Valuation risk offsets AI optimism.",
            "stance": "bearish",
            "contrary_evidence": ["AI demand remains strong."],
            "key_arguments": [
                {"point": "Valuation", "evidence": "Multiples remain elevated."}
            ],
            "counterpoints": ["Supply-chain improvements could help."],
            "evidence_blocks": [],
            "unknowns": [],
        },
    }
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text=json.dumps(valid_payload, ensure_ascii=False) + '"}'
                )
            ],
        )
    )

    replacement = adk_callbacks.structured_after_model_callback(
        BearCaseStructuredOutput,
        "Bear Researcher",
    )(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["report_markdown"] == valid_payload["report_markdown"]
    assert payload["highlights"]["category"] == "bear_case"
    assert payload["highlights"]["key_arguments"][0]["point"] == "Valuation"
    assert callback_context.state["runtime_warnings"] == []


def test_native_structured_callback_repairs_markdown_json_highlights_block():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    raw_response = """## AMD risk view\n\nKeep risk moderate until evidence improves.\n\n```json-highlights\n{
  "category": "risk_neutral",
  "signal": "HOLD",
  "signal_confidence": "medium",
  "summary": "Risk is balanced.",
  "stance": "neutral",
  "stance_label": "Neutral",
  "core_argument": "Wait for cleaner confirmation.",
  "risk_assessment": "moderate",
  "key_recommendations": ["Keep sizing moderate."],
  "risk_budget": null,
  "evidence_blocks": [],
  "unknowns": []
}\n```"""
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=raw_response)],
        )
    )

    replacement = adk_callbacks.structured_after_model_callback(
        NeutralRiskStructuredOutput,
        "Neutral Analyst",
    )(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["report_markdown"] == (
        "## AMD risk view\n\nKeep risk moderate until evidence improves."
    )
    assert payload["highlights"]["category"] == "risk_neutral"
    assert payload["highlights"]["risk_assessment"] == "moderate"
    assert "json-highlights" not in payload["report_markdown"]
    assert callback_context.state["runtime_warnings"] == []


def test_native_structured_callback_unwraps_report_markdown_when_schema_is_invalid():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    invalid_payload = {
        "report_markdown": "## News view\n\nCEG news flow is mixed.",
        "highlights": {
            "category": "news",
            "signal": "HOLD",
            "summary": "News is mixed.",
        },
    }
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text=json.dumps(invalid_payload, ensure_ascii=False)
                )
            ],
        )
    )

    replacement = adk_callbacks.structured_after_model_callback(
        NewsReportStructuredOutput,
        "News Analyst",
    )(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["report_markdown"] == "## News view\n\nCEG news flow is mixed."
    assert not payload["report_markdown"].lstrip().startswith("{")
    assert payload["highlights"]["category"] == "news"
    assert callback_context.state["runtime_warnings"][0]["stage"] == "News Analyst"


def test_native_portfolio_callback_repairs_json_with_trailing_characters():
    callback_context = SimpleNamespace(state={"runtime_warnings": []})
    valid_payload = {
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
    invalid_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text=json.dumps(valid_payload, ensure_ascii=False) + '"}'
                )
            ],
        )
    )

    replacement = adk_callbacks.turn_after_model_callback(PORTFOLIO_MANAGER_AGENT)(
        callback_context=callback_context,
        llm_response=invalid_response,
    )

    assert replacement is not None
    payload = json.loads(replacement.content.parts[0].text)
    assert payload["decision_report"] == valid_payload["decision_report"]
    assert payload["decision_card"]["rating"] == "HOLD"
    assert payload["decision_card"]["key_reasons"][0]["point"] == "Balanced risk"
    assert callback_context.state["runtime_warnings"] == []


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

    replacement = adk_callbacks.turn_after_model_callback(PORTFOLIO_MANAGER_AGENT)(
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

    replacement = adk_callbacks.turn_after_model_callback(PORTFOLIO_MANAGER_AGENT)(
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

    replacement = adk_callbacks.turn_after_model_callback(PORTFOLIO_MANAGER_AGENT)(
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
        if schema is None:
            return {"message": "Fake evidence notes from schema-free evidence agent."}
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
        evidence_response_count: ClassVar[int] = 0
        seen_response_schemas: ClassVar[set] = set()

        async def generate_content_async(self, llm_request, stream=False):
            schema = llm_request.config.response_schema
            type(self).seen_response_schemas.add(schema)
            if schema is None:
                type(self).evidence_response_count += 1
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
                "market": _tool_collection(get_stock_data, get_indicators),
                "social": _tool_collection(get_news, web_search_evidence),
                "news": _tool_collection(
                    get_news,
                    get_global_news,
                    web_search_evidence,
                ),
                "fundamentals": _tool_collection(
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                    get_insider_transactions,
                ),
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
        )
    )
    progress_events = [
        event
        for chunk in chunks
        for event in chunk.get("runtime_progress_events", [])
    ]

    assert captured_resource_configs == [{"max_recur_limit": 10}]
    assert any(
        "MarketReportStructuredOutput" in chunk["market_report"] for chunk in chunks
    )
    assert any(
        "SentimentReportStructuredOutput" in chunk["sentiment_report"]
        for chunk in chunks
    )
    assert any("NewsReportStructuredOutput" in chunk["news_report"] for chunk in chunks)
    assert any(
        "FundamentalsReportStructuredOutput" in chunk["fundamentals_report"]
        for chunk in chunks
    )
    assert chunks[-1]["investment_plan"]
    assert chunks[-1]["trader_investment_plan"]
    assert chunks[-1]["final_trade_decision"]
    assert chunks[-1]["portfolio_decision_card"]["rating"] == "HOLD"
    assert {
        ("News Analyst Evidence", "News Analyst Evidence started."),
        ("News Analyst Report", "News Analyst Report started."),
        ("News Analyst Report", "News Analyst Report completed."),
    }.issubset(
        {
            (event.get("current_agent"), event.get("message"))
            for event in progress_events
        }
    )
    assert {
        MarketReportStructuredOutput,
        SentimentReportStructuredOutput,
        FundamentalsReportStructuredOutput,
        NewsReportStructuredOutput,
        BullCaseStructuredOutput,
        BearCaseStructuredOutput,
        ResearchDecisionStructuredOutput,
        TraderStructuredOutput,
        AggressiveRiskStructuredOutput,
        ConservativeRiskStructuredOutput,
        NeutralRiskStructuredOutput,
        PortfolioManagerStructuredOutput,
    }.issubset(FakeNativeStructuredModel.seen_response_schemas)
    assert None in FakeNativeStructuredModel.seen_response_schemas
    assert FakeNativeStructuredModel.evidence_response_count == 4
