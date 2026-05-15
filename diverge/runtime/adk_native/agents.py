from __future__ import annotations

from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from pydantic import Field

from diverge.agents.base import DivergeAgentNode
from diverge.runtime.adk_native.state_adapter import snapshot_state
from diverge.runtime.tool_loop import (
    contextual_tool_args,
    human_message,
    looks_like_incomplete_tool_preface,
    normalize_tool_args,
    tool_message,
    tool_retry_instruction,
)
from diverge.runtime.tools import AdkToolCollection


_ANALYST_REPORT_KEYS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

_AGENT_DISPLAY_NAMES = {
    "market_analyst": "Market Analyst",
    "social_media_analyst": "Social Analyst",
    "news_analyst": "News Analyst",
    "fundamentals_analyst": "Fundamentals Analyst",
    "bull_researcher": "Bull Researcher",
    "bear_researcher": "Bear Researcher",
    "research_manager": "Research Manager",
    "trader": "Trader",
    "aggressive_analyst": "Aggressive Analyst",
    "conservative_analyst": "Conservative Analyst",
    "neutral_analyst": "Neutral Analyst",
    "portfolio_manager": "Portfolio Manager",
    "summary_agent": "Summary Agent",
}

_DELTA_REPORT_LABELS = {
    "market_report": "market report",
    "sentiment_report": "sentiment report",
    "news_report": "news report",
    "fundamentals_report": "fundamentals report",
    "investment_plan": "research decision",
    "trader_investment_plan": "trading plan",
    "final_trade_decision": "portfolio decision",
    "report_summary": "summary",
}


class NativeAnalystAgent(BaseAgent):
    """ADK BaseAgent wrapper for Diverge analyst nodes during migration."""

    analyst_key: str
    node: Any = Field(exclude=True)
    tool_collection: AdkToolCollection = Field(exclude=True)
    max_tool_iterations: int = 12

    async def _run_async_impl(self, ctx: InvocationContext):
        state = snapshot_state(ctx.session.state)
        agent_name = _agent_display_name(self.node)
        report_key = _ANALYST_REPORT_KEYS[self.analyst_key]

        _append_runtime_progress_event(
            state,
            current_agent=agent_name,
            message=f"{agent_name} started.",
        )
        yield _state_event(self.name, state)

        for _ in range(self.max_tool_iterations):
            delta = self.node(state) or {}
            _merge_node_delta(state, delta)
            last_message = _last_message(state)
            tool_calls = list(getattr(last_message, "tool_calls", []) or [])

            if (
                state.get(report_key)
                and not tool_calls
                and looks_like_incomplete_tool_preface(last_message)
            ):
                state[report_key] = ""
                state.setdefault("messages", []).append(
                    human_message(tool_retry_instruction(state, self.analyst_key))
                )
                yield _state_event(self.name, state)
                continue

            if state.get(report_key) or not tool_calls:
                _append_runtime_progress_event(
                    state,
                    current_agent=agent_name,
                    message=f"{agent_name} completed{_delta_summary(delta)}.",
                )
                yield _state_event(self.name, state)
                return

            tool_names = _tool_call_names(tool_calls)
            _append_runtime_progress_event(
                state,
                current_agent=agent_name,
                message=f"{agent_name} requested tools: {', '.join(tool_names)}.",
            )
            yield _state_event(self.name, state)

            tool_summaries = self._append_tool_results(state, tool_calls)
            _append_runtime_progress_event(
                state,
                current_agent=agent_name,
                message=(
                    f"{agent_name} tool results ready: {'; '.join(tool_summaries)}."
                ),
            )
            yield _state_event(self.name, state)

        state.setdefault("runtime_warnings", []).append(
            {
                "stage": f"{self.analyst_key}_analyst",
                "message": "Tool loop reached the configured iteration limit.",
            }
        )
        yield _state_event(self.name, state)

    async def _run_live_impl(self, ctx: InvocationContext):
        raise NotImplementedError("NativeAnalystAgent does not support live mode.")
        yield

    def _append_tool_results(
        self,
        state: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> list[str]:
        summaries: list[str] = []
        for tool_call in tool_calls:
            tool_name = str(tool_call.get("name") or "")
            if tool_name not in self.tool_collection.tools_by_name:
                content = (
                    f"Tool `{tool_name}` is not registered for {self.analyst_key}."
                )
                summaries.append(f"{tool_name or 'unknown tool'} unavailable")
            else:
                try:
                    content = self.tool_collection.invoke(
                        tool_name,
                        contextual_tool_args(
                            state,
                            tool_name,
                            normalize_tool_args(tool_call.get("args")),
                        ),
                    )
                    summaries.append(f"{tool_name} returned {len(str(content))} chars")
                except Exception as exc:
                    content = f"Tool `{tool_name}` failed: {exc}"
                    summaries.append(f"{tool_name} failed")
            state.setdefault("messages", []).append(
                tool_message(
                    content,
                    name=tool_name,
                    tool_call_id=str(tool_call.get("id") or tool_name or "tool"),
                )
            )
        return summaries


class NativeStateAgent(BaseAgent):
    """ADK BaseAgent wrapper for non-tool-loop Diverge state nodes."""

    node: Any = Field(exclude=True)

    async def _run_async_impl(self, ctx: InvocationContext):
        state = snapshot_state(ctx.session.state)
        agent_name = _agent_display_name(self.node)
        _append_runtime_progress_event(
            state,
            current_agent=agent_name,
            message=f"{agent_name} started.",
        )
        yield _state_event(self.name, state)

        delta = self.node(state) or {}
        _merge_node_delta(state, delta)
        _append_runtime_progress_event(
            state,
            current_agent=agent_name,
            message=f"{agent_name} completed{_delta_summary(delta)}.",
        )
        yield _state_event(self.name, state)

    async def _run_live_impl(self, ctx: InvocationContext):
        raise NotImplementedError("NativeStateAgent does not support live mode.")
        yield


def _state_event(author: str, state: dict[str, Any]) -> Event:
    return Event(
        author=author,
        actions=EventActions(state_delta=snapshot_state(state)),
    )


def _merge_node_delta(state: dict[str, Any], delta: dict[str, Any]) -> None:
    for key, value in delta.items():
        if key == "messages":
            state.setdefault("messages", []).extend(value or [])
        else:
            state[key] = value


def _last_message(state: dict[str, Any]) -> Any:
    messages = state.get("messages") or []
    return messages[-1] if messages else None


def _append_runtime_progress_event(
    state: dict[str, Any],
    *,
    current_agent: str,
    message: str,
) -> None:
    events = state.setdefault("runtime_progress_events", [])
    if not isinstance(events, list):
        events = []
        state["runtime_progress_events"] = events
    events.append(
        {
            "id": f"runtime-progress-{len(events) + 1}",
            "current_agent": current_agent,
            "message": message,
        }
    )


def _tool_call_names(tool_calls: list[dict[str, Any]]) -> list[str]:
    names = [str(tool_call.get("name") or "").strip() for tool_call in tool_calls]
    return [name for name in names if name] or ["unknown tool"]


def _agent_display_name(node: DivergeAgentNode) -> str:
    raw_name = str(getattr(node, "name", "") or node.__class__.__name__)
    if raw_name in _AGENT_DISPLAY_NAMES:
        return _AGENT_DISPLAY_NAMES[raw_name]
    return raw_name.replace("_", " ").strip().title() or "Agent"


def _delta_summary(delta: dict[str, Any]) -> str:
    labels: list[str] = []
    for key, label in _DELTA_REPORT_LABELS.items():
        value = delta.get(key)
        if isinstance(value, str) and value.strip():
            labels.append(label)

    if not labels:
        return ""
    return f" with {', '.join(labels)}"
