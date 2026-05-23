from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from diverge.agents.utils.agent_utils import (
    build_instrument_context,
    format_untrusted_context_block,
    get_evidence_rules_instruction,
    get_language_instruction,
    get_memory_skepticism_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)


@dataclass(frozen=True, slots=True)
class AgentPromptContext:
    ticker: str
    trade_date: str
    output_language: str
    instrument_context: str
    language_instruction: str
    style_instruction: str
    trade_feedback_message: str
    evidence_rules_instruction: str
    decision_boundary_instruction: str
    memory_skepticism_instruction: str


@dataclass(frozen=True, slots=True)
class UpstreamReportsContext:
    market: str
    sentiment: str
    news: str
    fundamentals: str

    @property
    def combined(self) -> str:
        return f"{self.market}\n\n{self.sentiment}\n\n{self.news}\n\n{self.fundamentals}"

    def block(self, name: str, *, label: str | None = None, limit: int = 4000) -> str:
        return format_untrusted_context_block(
            label or name,
            getattr(self, name),
            limit=limit,
        )


@dataclass(frozen=True, slots=True)
class InvestmentDebateContext:
    raw: Mapping[str, Any]
    history: str
    bull_history: str
    bear_history: str
    current_bull_response: str
    current_bear_response: str
    count: int

    @property
    def latest_bull_argument(self) -> str:
        return self.current_bull_response or str(self.raw.get("current_response", ""))

    @property
    def latest_bear_argument(self) -> str:
        return self.current_bear_response or str(self.raw.get("current_response", ""))

    def metadata(self) -> dict[str, Any]:
        return {
            "history": self.history,
            "bear_history": self.bear_history,
            "bull_history": self.bull_history,
            "current_bull_response": self.current_bull_response,
            "current_bear_response": self.current_bear_response,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class RiskDebateContext:
    raw: Mapping[str, Any]
    history: str
    aggressive_history: str
    conservative_history: str
    neutral_history: str
    current_aggressive_response: str
    current_conservative_response: str
    current_neutral_response: str
    count: int

    def metadata(self) -> dict[str, Any]:
        return {
            "history": self.history,
            "aggressive_history": self.aggressive_history,
            "conservative_history": self.conservative_history,
            "neutral_history": self.neutral_history,
            "current_aggressive_response": self.current_aggressive_response,
            "current_conservative_response": self.current_conservative_response,
            "current_neutral_response": self.current_neutral_response,
            "count": self.count,
        }


def build_agent_prompt_context(state: Mapping[str, Any]) -> AgentPromptContext:
    output_language = str(state.get("output_language") or "en")
    ticker = str(state.get("company_of_interest") or "")
    trade_date = str(state.get("trade_date") or "")
    return AgentPromptContext(
        ticker=ticker,
        trade_date=trade_date,
        output_language=output_language,
        instrument_context=build_instrument_context(ticker) if ticker else "",
        language_instruction=get_language_instruction(output_language),
        style_instruction=get_research_note_style_instruction(output_language),
        trade_feedback_message=get_trade_feedback_message(state),
        evidence_rules_instruction=get_evidence_rules_instruction(),
        decision_boundary_instruction=get_upstream_decision_boundary_instruction(),
        memory_skepticism_instruction=get_memory_skepticism_instruction(),
    )


def upstream_reports_from_state(state: Mapping[str, Any]) -> UpstreamReportsContext:
    return UpstreamReportsContext(
        market=str(state["market_report"]),
        sentiment=str(state["sentiment_report"]),
        news=str(state["news_report"]),
        fundamentals=str(state["fundamentals_report"]),
    )


def investment_debate_from_state(state: Mapping[str, Any]) -> InvestmentDebateContext:
    debate = state["investment_debate_state"]
    return InvestmentDebateContext(
        raw=debate,
        history=str(debate.get("history", "")),
        bull_history=str(debate.get("bull_history", "")),
        bear_history=str(debate.get("bear_history", "")),
        current_bull_response=str(debate.get("current_bull_response", "")),
        current_bear_response=str(debate.get("current_bear_response", "")),
        count=int(debate["count"]),
    )


def risk_debate_from_state(state: Mapping[str, Any]) -> RiskDebateContext:
    debate = state["risk_debate_state"]
    return RiskDebateContext(
        raw=debate,
        history=str(debate.get("history", "")),
        aggressive_history=str(debate.get("aggressive_history", "")),
        conservative_history=str(debate.get("conservative_history", "")),
        neutral_history=str(debate.get("neutral_history", "")),
        current_aggressive_response=str(
            debate.get("current_aggressive_response", "")
        ),
        current_conservative_response=str(
            debate.get("current_conservative_response", "")
        ),
        current_neutral_response=str(debate.get("current_neutral_response", "")),
        count=int(debate["count"]),
    )


def memory_recommendations_text(
    memory: Any,
    situation: str,
    *,
    n_matches: int = 2,
    default: str = "",
) -> str:
    memories = memory.get_memories(situation, n_matches=n_matches)
    if not memories:
        return default
    return "".join(f"{rec['recommendation']}\n\n" for rec in memories)


def memory_recommendations_block(
    memory: Any,
    situation: str,
    *,
    label: str = "past_decision_memory",
    limit: int = 4000,
    n_matches: int = 2,
    default: str = "",
) -> str:
    return format_untrusted_context_block(
        label,
        memory_recommendations_text(
            memory,
            situation,
            n_matches=n_matches,
            default=default,
        ),
        limit=limit,
    )


def context_block(label: str, content: str, *, limit: int = 4000) -> str:
    return format_untrusted_context_block(label, content, limit=limit)
