from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from web.backend.schemas.market_resolution import MarketResolutionPayload


class AnalysisReferencePayload(BaseModel):
    analysis_date: str
    report_path: str
    full_state_log_path: Optional[str] = ""


class TradeRecordCreatePayload(BaseModel):
    raw_symbol: str
    side: str = "long"
    entry_timestamp: str
    entry_price: float
    size: float
    strategy_tags: list[str] = Field(min_length=1)
    entry_reason: str
    invalidation_condition: str
    planned_horizon: str = "unknown"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    plan_execution: str = "unknown"
    initial_thesis: str = ""
    notes: str = ""
    execution_note: str = ""
    market_resolution: Optional[MarketResolutionPayload] = None
    analysis_references: list[AnalysisReferencePayload] = Field(default_factory=list)


class TradeRecordUpdatePayload(BaseModel):
    raw_symbol: Optional[str] = None
    side: Optional[str] = None
    entry_timestamp: Optional[str] = None
    entry_price: Optional[float] = None
    size: Optional[float] = None
    strategy_tags: Optional[list[str]] = None
    entry_reason: Optional[str] = None
    invalidation_condition: Optional[str] = None
    planned_horizon: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    plan_execution: Optional[str] = None
    initial_thesis: Optional[str] = None
    notes: Optional[str] = None
    execution_note: Optional[str] = None
    market_resolution: Optional[MarketResolutionPayload] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


class TradePlanCreatePayload(BaseModel):
    raw_symbol: str
    side: str = "long"
    source: str = "manual"
    strategy_tags: list[str] = Field(min_length=1)
    entry_condition: str
    thesis: str
    invalidation_condition: str
    risk_rule: str
    reward_target: str
    position_plan: str
    planned_horizon: str = "unknown"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    expires_at: str
    notes: str = ""
    market_resolution: Optional[MarketResolutionPayload] = None
    analysis_references: list[AnalysisReferencePayload] = Field(default_factory=list)


class TradePlanUpdatePayload(BaseModel):
    raw_symbol: Optional[str] = None
    side: Optional[str] = None
    source: Optional[str] = None
    strategy_tags: Optional[list[str]] = None
    entry_condition: Optional[str] = None
    thesis: Optional[str] = None
    invalidation_condition: Optional[str] = None
    risk_rule: Optional[str] = None
    reward_target: Optional[str] = None
    position_plan: Optional[str] = None
    planned_horizon: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    market_resolution: Optional[MarketResolutionPayload] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


class TradePlanExecutePayload(BaseModel):
    entry_timestamp: str
    entry_price: float
    size: float
    notes: str = ""
    execution_note: str = ""


class TradePlanLinkPayload(BaseModel):
    plan_id: str
    execution_note: str = ""


class TradeReviewGeneratePayload(BaseModel):
    analysis_date: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None
    output_language: Optional[Literal["en", "cn"]] = None


class TradeReviewSavePayload(BaseModel):
    thesis_assessment: str
    timing_assessment: str
    sizing_assessment: str
    discipline_assessment: str
    outcome_summary: str
    improvement_actions: str | list[str]
    ticker_specific_lessons: str | list[str]
    cross_ticker_tags: str | list[str]
    analysis_date: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None
