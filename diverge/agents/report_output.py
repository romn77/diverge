from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TradeSignal = Literal["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
SignalConfidence = Literal["high", "medium", "low"]
ResearchStance = Literal["bullish", "neutral", "bearish", "mixed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceBlockOutput(StrictModel):
    claim: str
    evidence: str
    source: str | None = None
    data_date: str | None = None
    confidence: SignalConfidence | None = None
    limitation: str | None = None


class BaseHighlightsOutput(StrictModel):
    signal: TradeSignal
    summary: str
    signal_confidence: SignalConfidence | None = None
    stance: ResearchStance | None = None
    evidence_blocks: list[EvidenceBlockOutput] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class MarketKeyLevelsOutput(StrictModel):
    support: list[str] = Field(default_factory=list)
    resistance: list[str] = Field(default_factory=list)


class MarketIndicatorOutput(StrictModel):
    name: str
    value: str
    interpretation: str


class MarketHighlightsOutput(BaseHighlightsOutput):
    category: Literal["market"]
    trend_direction: ResearchStance
    key_levels: MarketKeyLevelsOutput
    indicators: list[MarketIndicatorOutput] = Field(default_factory=list)
    volatility: str | None = None


class FundamentalsMetricOutput(StrictModel):
    name: str
    value: str
    assessment: str


class FundamentalsHighlightsOutput(BaseHighlightsOutput):
    category: Literal["fundamentals"]
    metrics: list[FundamentalsMetricOutput] = Field(default_factory=list)
    financial_health: str | None = None


class SentimentHighlightsOutput(BaseHighlightsOutput):
    category: Literal["sentiment"]
    overall_sentiment: Literal["positive", "negative", "neutral", "mixed"]
    sentiment_score: str | None = None
    key_topics: list[str] = Field(default_factory=list)
    social_buzz: str | None = None


class NewsKeyEventOutput(StrictModel):
    event: str
    impact: str


class NewsHighlightsOutput(BaseHighlightsOutput):
    category: Literal["news"]
    market_impact: Literal["positive", "negative", "neutral", "mixed"]
    key_events: list[NewsKeyEventOutput] = Field(default_factory=list)
    macro_outlook: str | None = None


class ResearchArgumentOutput(StrictModel):
    point: str
    evidence: str


class BullCaseHighlightsOutput(BaseHighlightsOutput):
    category: Literal["bull_case"]
    stance: Literal["bullish"]
    contrary_evidence: list[str] = Field(default_factory=list)
    key_arguments: list[ResearchArgumentOutput] = Field(default_factory=list)
    counterpoints: list[str] = Field(default_factory=list)


class BearCaseHighlightsOutput(BaseHighlightsOutput):
    category: Literal["bear_case"]
    stance: Literal["bearish"]
    contrary_evidence: list[str] = Field(default_factory=list)
    key_arguments: list[ResearchArgumentOutput] = Field(default_factory=list)
    counterpoints: list[str] = Field(default_factory=list)


class ResearchDecisionHighlightsOutput(BaseHighlightsOutput):
    category: Literal["research_decision"]
    decision: TradeSignal
    aligned_with: Literal["bull", "bear"]
    rationale: str
    action_items: list[str] = Field(default_factory=list)


class TraderEntryExitOutput(StrictModel):
    action: str
    entry_condition: str | None = None
    exit_target: str | None = None
    stop_loss: str | None = None
    invalidation: str | None = None
    re_entry: str | None = None


class TraderHighlightsOutput(BaseHighlightsOutput):
    category: Literal["trader"]
    decision: TradeSignal
    entry_exit: TraderEntryExitOutput
    position_sizing: str | None = None
    risk_budget: str | None = None
    risk_factors: list[str] = Field(default_factory=list)


class RiskBudgetOutput(StrictModel):
    max_position_size: str | None = None
    portfolio_exposure_impact: str | None = None
    stop_or_invalidation: list[str] = Field(default_factory=list)
    liquidity_risk: Literal["low", "medium", "high", "unknown"] | None = None
    event_risk: list[str] = Field(default_factory=list)
    correlation_or_factor_risk: list[str] = Field(default_factory=list)
    required_pm_adjustment: str | None = None


class RiskHighlightsOutput(BaseHighlightsOutput):
    stance_label: str
    core_argument: str
    risk_assessment: Literal["high", "moderate", "low"]
    key_recommendations: list[str] = Field(default_factory=list)
    risk_budget: RiskBudgetOutput | None = None


class AggressiveRiskHighlightsOutput(RiskHighlightsOutput):
    category: Literal["risk_aggressive"]


class ConservativeRiskHighlightsOutput(RiskHighlightsOutput):
    category: Literal["risk_conservative"]


class NeutralRiskHighlightsOutput(RiskHighlightsOutput):
    category: Literal["risk_neutral"]


class MarkdownReportOutput(StrictModel):
    report_markdown: str = Field(
        description=(
            "User-facing markdown report body only. Do not include any "
            "`json-highlights` or `json-decision-card` fenced block."
        )
    )


class MarketReportStructuredOutput(MarkdownReportOutput):
    highlights: MarketHighlightsOutput


class FundamentalsReportStructuredOutput(MarkdownReportOutput):
    highlights: FundamentalsHighlightsOutput


class SentimentReportStructuredOutput(MarkdownReportOutput):
    highlights: SentimentHighlightsOutput


class NewsReportStructuredOutput(MarkdownReportOutput):
    highlights: NewsHighlightsOutput


class BullCaseStructuredOutput(MarkdownReportOutput):
    highlights: BullCaseHighlightsOutput


class BearCaseStructuredOutput(MarkdownReportOutput):
    highlights: BearCaseHighlightsOutput


class ResearchDecisionStructuredOutput(MarkdownReportOutput):
    highlights: ResearchDecisionHighlightsOutput


class TraderStructuredOutput(MarkdownReportOutput):
    highlights: TraderHighlightsOutput


class AggressiveRiskStructuredOutput(MarkdownReportOutput):
    highlights: AggressiveRiskHighlightsOutput


class ConservativeRiskStructuredOutput(MarkdownReportOutput):
    highlights: ConservativeRiskHighlightsOutput


class NeutralRiskStructuredOutput(MarkdownReportOutput):
    highlights: NeutralRiskHighlightsOutput


def render_markdown_with_highlights(
    report_markdown: str,
    highlights: BaseModel,
) -> str:
    report = str(report_markdown or "").strip()
    highlights_block = json.dumps(
        highlights.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )
    if not report:
        return f"```json-highlights\n{highlights_block}\n```"
    return f"{report}\n\n```json-highlights\n{highlights_block}\n```"


def structured_agent_output_instruction() -> str:
    return """Return only the structured response requested by the runtime schema:
- `report_markdown`: the full user-facing markdown report in the requested language. Do not include planning text, tool-call scaffolding, `json-highlights`, or `json-decision-card` fenced blocks.
- `highlights`: the structured highlights object matching the schema described above."""


def merge_structured_agent_output(
    state: dict,
    *,
    agent_name: str,
    payload: dict,
) -> dict[str, dict]:
    outputs = dict(state.get("structured_agent_outputs") or {})
    outputs[agent_name] = payload
    return outputs
