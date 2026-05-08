from __future__ import annotations

import copy
import json
from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from google.adk.workflow import START, FunctionNode, Workflow

from diverge.agents import (
    create_aggressive_debator,
    create_bear_researcher,
    create_bull_researcher,
    create_conservative_debator,
    create_fundamentals_analyst,
    create_market_analyst,
    create_neutral_debator,
    create_news_analyst,
    create_portfolio_manager,
    create_research_manager,
    create_social_media_analyst,
    create_summary_agent,
    create_trader,
)
from diverge.agents.risk_mgmt.debate_phase import get_total_risk_turn_limit
from diverge.runtime.messages import AdkMessage
from diverge.runtime.tools import AdkToolCollection, create_adk_tool_collections


ANALYST_NODE_FACTORIES: dict[str, Callable[[Any], Callable[[dict], dict]]] = {
    "market": create_market_analyst,
    "social": create_social_media_analyst,
    "news": create_news_analyst,
    "fundamentals": create_fundamentals_analyst,
}


class AdkWorkflowRunner:
    """ADK 2.0 workflow facade for Diverge's multi-agent state machine."""

    def __init__(
        self,
        *,
        selected_analysts: list[str],
        quick_llm: Any,
        deep_llm: Any,
        tool_nodes: Optional[dict[str, AdkToolCollection]] = None,
        bull_memory: Any = None,
        bear_memory: Any = None,
        trader_memory: Any = None,
        invest_judge_memory: Any = None,
        portfolio_manager_memory: Any = None,
        max_debate_rounds: int = 1,
        max_risk_discuss_rounds: int = 1,
        max_tool_iterations: int = 12,
    ) -> None:
        if not selected_analysts:
            raise ValueError("Diverge ADK Workflow Error: no analysts selected!")

        unsupported = [
            analyst for analyst in selected_analysts if analyst not in ANALYST_NODE_FACTORIES
        ]
        if unsupported:
            raise ValueError(f"Unsupported analysts for ADK workflow: {unsupported}")

        self.selected_analysts = list(selected_analysts)
        self.quick_llm = quick_llm
        self.deep_llm = deep_llm
        self.tool_nodes = tool_nodes or create_adk_tool_collections()
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds
        self.max_tool_iterations = max_tool_iterations

        self.analyst_nodes = {
            analyst: ANALYST_NODE_FACTORIES[analyst](self.quick_llm)
            for analyst in self.selected_analysts
        }
        self.bull_researcher = create_bull_researcher(self.quick_llm, bull_memory)
        self.bear_researcher = create_bear_researcher(self.quick_llm, bear_memory)
        self.research_manager = create_research_manager(
            self.deep_llm,
            invest_judge_memory,
        )
        self.trader = create_trader(self.quick_llm, trader_memory)
        self.aggressive_analyst = create_aggressive_debator(self.quick_llm)
        self.conservative_analyst = create_conservative_debator(self.quick_llm)
        self.neutral_analyst = create_neutral_debator(self.quick_llm)
        self.portfolio_manager = create_portfolio_manager(
            self.deep_llm,
            portfolio_manager_memory,
        )
        self.summary_agent = create_summary_agent(self.quick_llm)
        self.workflow = self._build_workflow_definition()

    def _build_workflow_definition(self) -> Workflow:
        nodes = {
            f"{name}_analyst": FunctionNode(
                func=_identity_node,
                name=f"{name}_analyst",
            )
            for name in self.selected_analysts
        }
        for name in [
            "bull_researcher",
            "bear_researcher",
            "research_manager",
            "trader",
            "aggressive_analyst",
            "conservative_analyst",
            "neutral_analyst",
            "portfolio_manager",
            "summary_agent",
        ]:
            nodes[name] = FunctionNode(func=_identity_node, name=name)

        ordered_names = [f"{name}_analyst" for name in self.selected_analysts]
        ordered_names.extend(
            [
                "bull_researcher",
                "bear_researcher",
                "research_manager",
                "trader",
                "aggressive_analyst",
                "conservative_analyst",
                "neutral_analyst",
                "portfolio_manager",
                "summary_agent",
            ]
        )
        edges: list[tuple[Any, Any]] = []
        previous: Any = START
        for name in ordered_names:
            current = nodes[name]
            edges.append((previous, current))
            previous = current

        return Workflow(name="diverge_adk_workflow", edges=edges, max_concurrency=1)

    def invoke(self, init_state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        final_state = None
        for final_state in self.stream(init_state, **kwargs):
            pass
        return final_state if final_state is not None else copy.deepcopy(init_state)

    def stream(
        self,
        init_state: dict[str, Any],
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, None]:
        state = copy.deepcopy(init_state)
        max_iterations = _recursion_limit(kwargs) or self.max_tool_iterations

        for analyst in self.selected_analysts:
            yield from self._run_analyst(
                state,
                analyst,
                max_tool_iterations=max_iterations,
            )
            self._clear_messages(state)

        yield from self._run_node(state, self.bull_researcher)
        while self._should_continue_research_debate(state):
            next_node = (
                self.bear_researcher
                if state["investment_debate_state"].get("current_response", "").startswith(
                    "Bull"
                )
                else self.bull_researcher
            )
            yield from self._run_node(state, next_node)

        yield from self._run_node(state, self.research_manager)
        yield from self._run_node(state, self.trader)

        yield from self._run_node(state, self.aggressive_analyst)
        while self._should_continue_risk_debate(state):
            latest_speaker = state["risk_debate_state"].get("latest_speaker", "")
            if latest_speaker.startswith("Aggressive"):
                next_node = self.conservative_analyst
            elif latest_speaker.startswith("Conservative"):
                next_node = self.neutral_analyst
            else:
                next_node = self.aggressive_analyst
            yield from self._run_node(state, next_node)

        yield from self._run_node(state, self.portfolio_manager)
        yield from self._run_node(state, self.summary_agent)

    def _run_analyst(
        self,
        state: dict[str, Any],
        analyst: str,
        *,
        max_tool_iterations: int,
    ) -> Generator[dict[str, Any], None, None]:
        node = self.analyst_nodes[analyst]
        report_key = _analyst_report_key(analyst)
        for _ in range(max_tool_iterations):
            yield from self._run_node(state, node)
            last_message = _last_message(state)
            tool_calls = list(getattr(last_message, "tool_calls", []) or [])
            if (
                state.get(report_key)
                and not tool_calls
                and _looks_like_incomplete_tool_preface(last_message)
            ):
                state[report_key] = ""
                state.setdefault("messages", []).append(
                    _human_message(_tool_retry_instruction(state, analyst))
                )
                yield _snapshot(state)
                continue
            if state.get(report_key) or not tool_calls:
                return
            self._append_tool_results(state, analyst, tool_calls)
            yield _snapshot(state)

        warning = {
            "stage": f"{analyst}_analyst",
            "message": "Tool loop reached the configured iteration limit.",
        }
        state.setdefault("runtime_warnings", []).append(warning)
        yield _snapshot(state)

    def _run_node(
        self,
        state: dict[str, Any],
        node: Callable[..., dict[str, Any]],
    ) -> Generator[dict[str, Any], None, None]:
        delta = node(state)
        _merge_state_delta(state, delta or {})
        yield _snapshot(state)

    def _append_tool_results(
        self,
        state: dict[str, Any],
        analyst: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        collection = self.tool_nodes[analyst]
        for tool_call in tool_calls:
            tool_name = str(tool_call.get("name") or "")
            if tool_name not in collection.tools_by_name:
                content = f"Tool `{tool_name}` is not registered for {analyst}."
            else:
                try:
                    content = collection.invoke(
                        tool_name,
                        _contextual_tool_args(
                            state,
                            tool_name,
                            _normalize_tool_args(tool_call.get("args")),
                        ),
                    )
                except Exception as exc:
                    content = f"Tool `{tool_name}` failed: {exc}"
            state.setdefault("messages", []).append(
                _tool_message(
                    content,
                    name=tool_name,
                    tool_call_id=str(tool_call.get("id") or tool_name or "tool"),
                )
            )

    def _clear_messages(self, state: dict[str, Any]) -> None:
        messages: list[Any] = []
        trade_feedback = str(state.get("historical_trade_feedback") or "").strip()
        if trade_feedback:
            messages.append(_human_message(trade_feedback))
        messages.append(_human_message("Continue"))
        state["messages"] = messages

    def _should_continue_research_debate(self, state: dict[str, Any]) -> bool:
        debate = state["investment_debate_state"]
        return debate.get("count", 0) < 2 * self.max_debate_rounds

    def _should_continue_risk_debate(self, state: dict[str, Any]) -> bool:
        risk = state["risk_debate_state"]
        return risk.get("count", 0) < get_total_risk_turn_limit(
            self.max_risk_discuss_rounds
        )


def _identity_node(state: dict[str, Any]) -> dict[str, Any]:
    return state


def _analyst_report_key(analyst: str) -> str:
    return {
        "market": "market_report",
        "social": "sentiment_report",
        "news": "news_report",
        "fundamentals": "fundamentals_report",
    }[analyst]


def _merge_state_delta(state: dict[str, Any], delta: dict[str, Any]) -> None:
    for key, value in delta.items():
        if key == "messages":
            state.setdefault("messages", []).extend(value or [])
        else:
            state[key] = value


def _last_message(state: dict[str, Any]) -> Any:
    messages = state.get("messages") or []
    return messages[-1] if messages else AdkMessage(content="")


def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
    try:
        return copy.deepcopy(state)
    except Exception:
        return dict(state)


def _normalize_tool_args(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _contextual_tool_args(
    state: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(args)
    ticker = str(state.get("company_of_interest") or "").strip().upper()
    trade_date = str(state.get("trade_date") or "").strip()

    if tool_name in {"get_news", "get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement", "get_insider_transactions"}:
        if "ticker" not in normalized and "symbol" in normalized:
            normalized["ticker"] = normalized["symbol"]
        if "ticker" not in normalized and ticker:
            normalized["ticker"] = ticker

    if tool_name in {"get_stock_data", "get_indicators"}:
        if "symbol" not in normalized and "ticker" in normalized:
            normalized["symbol"] = normalized["ticker"]
        if "symbol" not in normalized and ticker:
            normalized["symbol"] = ticker

    if tool_name in {"get_news", "get_stock_data"} and trade_date:
        normalized.setdefault("end_date", trade_date)
        normalized.setdefault("start_date", _date_days_before(trade_date, 7))

    if tool_name == "get_global_news" and trade_date:
        normalized.setdefault("curr_date", trade_date)

    if tool_name == "get_indicators" and trade_date:
        normalized.setdefault("curr_date", trade_date)

    return normalized


def _date_days_before(date_text: str, days: int) -> str:
    try:
        parsed = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    return (parsed - timedelta(days=days)).strftime("%Y-%m-%d")


def _looks_like_incomplete_tool_preface(message: Any) -> bool:
    content = str(getattr(message, "content", "") or "").strip()
    if not content or "json-highlights" in content or len(content) > 800:
        return False

    lowered = content.lower()
    intent_markers = (
        "i'll",
        "i’ll",
        "i will",
        "let me",
        "i need to",
        "first pull",
        "first retrieve",
        "first gather",
    )
    tool_markers = ("tool", "get_", "pull", "retrieve", "gather", "calculate")
    return any(marker in lowered for marker in intent_markers) and any(
        marker in lowered for marker in tool_markers
    )


def _tool_retry_instruction(state: dict[str, Any], analyst: str) -> str:
    ticker = str(state.get("company_of_interest") or "").strip().upper()
    trade_date = str(state.get("trade_date") or "").strip()
    return (
        "Your previous response described tool use but did not issue an executable "
        f"tool call. For the {analyst} analyst step, call the required tool now "
        f"using ticker/symbol {ticker} and current date {trade_date}. Do not write "
        "the final report until tool results have been returned."
    )


def _human_message(content: str) -> Any:
    try:
        from langchain_core.messages import HumanMessage

        return HumanMessage(content=content)
    except Exception:
        return ("human", content)


def _tool_message(content: str, *, name: str, tool_call_id: str) -> Any:
    try:
        from langchain_core.messages import ToolMessage

        return ToolMessage(content=content, name=name, tool_call_id=tool_call_id)
    except Exception:
        return AdkMessage(content=content, role="tool")


def _recursion_limit(kwargs: dict[str, Any]) -> Optional[int]:
    config = kwargs.get("config")
    if not isinstance(config, dict):
        return None
    limit = config.get("recursion_limit")
    return limit if isinstance(limit, int) and limit > 0 else None
