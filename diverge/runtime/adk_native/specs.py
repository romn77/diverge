from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from diverge.agents.analysts.fundamentals_analyst import (
    build_fundamentals_analyst_prompt,
)
from diverge.agents.analysts.market_analyst import build_market_analyst_prompt
from diverge.agents.analysts.news_analyst import build_news_analyst_prompt
from diverge.agents.analysts.social_media_analyst import (
    build_social_media_analyst_prompt,
)
from diverge.agents.report_output import (
    FundamentalsReportStructuredOutput,
    MarketReportStructuredOutput,
    NewsReportStructuredOutput,
    SentimentReportStructuredOutput,
)
from diverge.analysis.options import ANALYST_ORDER


@dataclass(frozen=True, slots=True)
class NativeAnalystSpec:
    analyst_key: str
    agent_name: str
    display_name: str
    output_schema: Any
    output_key: str
    build_prompt: Callable[..., Any]
    evidence_output_key: str
    report_key: str
    structured_agent_name: str


NATIVE_ANALYST_SPECS: Mapping[str, NativeAnalystSpec] = {
    "market": NativeAnalystSpec(
        analyst_key="market",
        agent_name="market_analyst",
        display_name="Market Analyst",
        output_schema=MarketReportStructuredOutput,
        output_key="market_report_structured",
        build_prompt=build_market_analyst_prompt,
        evidence_output_key="market_evidence_notes",
        report_key="market_report",
        structured_agent_name="market_analyst",
    ),
    "social": NativeAnalystSpec(
        analyst_key="social",
        agent_name="social_media_analyst",
        display_name="Social Analyst",
        output_schema=SentimentReportStructuredOutput,
        output_key="sentiment_report_structured",
        build_prompt=build_social_media_analyst_prompt,
        evidence_output_key="sentiment_evidence_notes",
        report_key="sentiment_report",
        structured_agent_name="social_media_analyst",
    ),
    "news": NativeAnalystSpec(
        analyst_key="news",
        agent_name="news_analyst",
        display_name="News Analyst",
        output_schema=NewsReportStructuredOutput,
        output_key="news_report_structured",
        build_prompt=build_news_analyst_prompt,
        evidence_output_key="news_evidence_notes",
        report_key="news_report",
        structured_agent_name="news_analyst",
    ),
    "fundamentals": NativeAnalystSpec(
        analyst_key="fundamentals",
        agent_name="fundamentals_analyst",
        display_name="Fundamentals Analyst",
        output_schema=FundamentalsReportStructuredOutput,
        output_key="fundamentals_report_structured",
        build_prompt=build_fundamentals_analyst_prompt,
        evidence_output_key="fundamentals_evidence_notes",
        report_key="fundamentals_report",
        structured_agent_name="fundamentals_analyst",
    ),
}


def ordered_native_analysts(selected_analysts: Sequence[str]) -> list[str]:
    selected = [analyst for analyst in ANALYST_ORDER if analyst in selected_analysts]
    native_analysts = [
        analyst for analyst in selected if analyst in NATIVE_ANALYST_SPECS
    ]
    remaining_analysts = [
        analyst for analyst in selected if analyst not in NATIVE_ANALYST_SPECS
    ]
    if remaining_analysts:
        raise ValueError(
            f"Unsupported analysts for ADK-native runtime: {remaining_analysts}"
        )
    return native_analysts
