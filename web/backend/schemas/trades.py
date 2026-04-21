from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AnalysisReferencePayload(BaseModel):
    analysis_date: str
    report_path: str
    full_state_log_path: str


class TradeRecordCreatePayload(BaseModel):
    ticker: str
    exchange_or_market: str
    side: str
    status: str
    entry_timestamp: Optional[str] = None
    entry_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    size: Optional[float] = None
    initial_thesis: str
    planned_horizon: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: str = ""
    analysis_references: list[AnalysisReferencePayload] = Field(default_factory=list)


class TradeRecordUpdatePayload(BaseModel):
    ticker: Optional[str] = None
    exchange_or_market: Optional[str] = None
    side: Optional[str] = None
    status: Optional[str] = None
    entry_timestamp: Optional[str] = None
    entry_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    size: Optional[float] = None
    initial_thesis: Optional[str] = None
    planned_horizon: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


class TradeReviewCreatePayload(BaseModel):
    review_type: str
    llm_provider: str
    model: str
    output_language: str = "en"
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    analysis_date: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


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
