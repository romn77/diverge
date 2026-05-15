from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


PortfolioRating = Literal[
    "BUY",
    "OVERWEIGHT",
    "HOLD",
    "UNDERWEIGHT",
    "SELL",
]

PortfolioAction = Literal[
    "OPEN",
    "ADD",
    "MAINTAIN",
    "TRIM",
    "EXIT",
    "WATCH",
    "NO_ACTION",
    "AVOID",
]

ConfidenceLevel = Literal["high", "medium", "low"]

TradeReadiness = Literal[
    "READY",
    "WAITING_FOR_TRIGGER",
    "BLOCKED_BY_RISK",
    "DATA_INSUFFICIENT",
    "NO_ACTION_REQUIRED",
]

DataQualityLevel = Literal["complete", "partial", "weak", "insufficient"]

EvidencePillar = Literal[
    "opportunity",
    "technical",
    "fundamentals",
    "valuation",
    "news",
    "sentiment",
    "risk",
    "portfolio",
    "macro",
]


class EvidenceItem(BaseModel):
    pillar: EvidencePillar
    point: str
    evidence: str
    strength: Literal["strong", "medium", "weak"] = "medium"
    source: str | None = None
    data_date: str | None = None
    confidence: ConfidenceLevel | None = None
    limitation: str | None = None


class PricePlan(BaseModel):
    current_price: float | None = None
    entry_zone: list[float] | None = None
    add_condition: str | None = None
    stop_loss: float | None = None
    take_profit: list[float] | None = None
    invalidation: list[str] = Field(default_factory=list)
    risk_reward_note: str | None = None


class WhyNot(BaseModel):
    why_not_more_bullish: str | None = None
    why_not_more_bearish: str | None = None
    why_not_act_now: str | None = None


class ActionPlaybook(BaseModel):
    do_now: list[str] = Field(default_factory=list, max_length=5)
    trigger_to_act: list[str] = Field(default_factory=list, max_length=5)
    invalidation: list[str] = Field(default_factory=list, max_length=5)
    execution_notes: list[str] = Field(default_factory=list, max_length=5)


class PositionGuidance(BaseModel):
    suggested_exposure: str | None = None
    max_exposure: str | None = None
    sizing_rationale: str | None = None
    risk_budget_note: str | None = None


class OpportunityEvidence(BaseModel):
    trigger: str | None = None
    theme_id: str | None = None
    theme_name: str | None = None
    candidate_type: str | None = None
    source_run_id: str | None = None
    backtest_summary: dict | None = None
    risk_flags: list[str] = Field(default_factory=list)


class DecisionCard(BaseModel):
    card_version: str = "1.2"

    report_id: str | None = None
    symbol: str
    name: str | None = None
    market: Literal["cn", "us", "hk", "unknown"] = "unknown"

    analysis_date: date | None = None
    generated_at: datetime

    rating: PortfolioRating
    action: PortfolioAction
    confidence: ConfidenceLevel
    conviction_score: int = Field(ge=0, le=100)
    time_horizon: str

    one_line_summary: str
    thesis: str

    price_plan: PricePlan = Field(default_factory=PricePlan)
    suggested_position: str | None = None

    key_reasons: list[EvidenceItem] = Field(default_factory=list, max_length=5)
    key_risks: list[str] = Field(default_factory=list, max_length=5)
    catalysts: list[str] = Field(default_factory=list, max_length=5)
    watch_items: list[str] = Field(default_factory=list, max_length=5)

    data_quality_notes: list[str] = Field(default_factory=list)
    source_report_paths: list[str] = Field(default_factory=list)

    raw_signal: str | None = None

    trade_readiness: TradeReadiness | None = None
    trade_readiness_reason: str | None = None
    blocking_items: list[str] = Field(default_factory=list, max_length=5)

    data_quality_level: DataQualityLevel | None = None
    data_quality_summary: str | None = None

    why_not: WhyNot | None = None
    action_playbook: ActionPlaybook | None = None
    position_guidance: PositionGuidance | None = None
    opportunity_evidence: OpportunityEvidence | None = None
