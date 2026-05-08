from __future__ import annotations

from google.adk.workflow import Workflow
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from diverge.runtime.state import create_initial_state
from diverge.runtime.workflow_runner import (
    AdkWorkflowRunner,
    _contextual_tool_args,
    _looks_like_incomplete_tool_preface,
)


class FakeMemory:
    def get_memories(self, _current_situation, n_matches=2):
        return []


class FakeLlm:
    def __init__(self):
        self.bound_tool_calls: list[list[str]] = []
        self.invocations = 0

    def bind_tools(self, tools):
        self.bound_tool_calls.append([tool.name for tool in tools])
        return RunnableLambda(
            lambda _messages: AIMessage(
                content=f"analyst report {len(self.bound_tool_calls)}",
                tool_calls=[],
            )
        )

    def invoke(self, _prompt):
        self.invocations += 1
        return AIMessage(content=f"llm response {self.invocations}")


def test_adk_workflow_runner_preserves_round_limits_and_final_state_schema():
    quick_llm = FakeLlm()
    deep_llm = FakeLlm()
    memory = FakeMemory()
    runner = AdkWorkflowRunner(
        selected_analysts=["market"],
        quick_llm=quick_llm,
        deep_llm=deep_llm,
        bull_memory=memory,
        bear_memory=memory,
        trader_memory=memory,
        invest_judge_memory=memory,
        portfolio_manager_memory=memory,
        max_debate_rounds=2,
        max_risk_discuss_rounds=1,
    )

    final_state = runner.invoke(create_initial_state("MSFT", "2026-03-20"))

    assert isinstance(runner.workflow, Workflow)
    assert quick_llm.bound_tool_calls[0] == ["get_stock_data", "get_indicators"]
    assert final_state["market_report"].startswith("analyst report")
    assert final_state["investment_debate_state"]["count"] == 4
    assert final_state["risk_debate_state"]["count"] == 6
    assert final_state["investment_plan"]
    assert final_state["trader_investment_plan"]
    assert final_state["final_trade_decision"]
    assert final_state["report_summary"]


def test_contextual_tool_args_repair_textual_sub2api_tool_arguments():
    state = {
        "company_of_interest": "SPY",
        "trade_date": "2026-05-08",
    }

    args = _contextual_tool_args(
        state,
        "get_news",
        {"query": "SPY ETF news sentiment"},
    )
    stock_args = _contextual_tool_args(
        state,
        "get_stock_data",
        {"ticker": "spy"},
    )

    assert args["ticker"] == "SPY"
    assert args["start_date"] == "2026-05-01"
    assert args["end_date"] == "2026-05-08"
    assert stock_args["symbol"] == "spy"


def test_incomplete_tool_preface_is_not_accepted_as_final_report():
    message = AIMessage(
        content=(
            "I’ll first pull the last 120 trading days of SPY data, "
            "then calculate indicators."
        )
    )

    assert _looks_like_incomplete_tool_preface(message)
