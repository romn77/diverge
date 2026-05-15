from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MarketBriefMarket = Literal["cn", "hk", "us"]
MarketBriefTrigger = Literal["manual", "scheduled"]


class MarketCalendarItem(BaseModel):
    market: MarketBriefMarket
    label: str
    timezone: str
    local_date: str
    trading_day: str | None
    is_trading_day: bool
    open_time: str
    close_time: str
    minutes_to_open: int | None = None
    session_status: str


class MarketSnapshot(BaseModel):
    market: MarketBriefMarket
    label: str
    index_symbol: str
    index_name: str
    trading_day: str | None = None
    retrieved_at: str
    source: str
    currency: str | None = None
    last_close: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    status: Literal["ok", "unavailable"] = "unavailable"
    warning: str | None = None


class MarketBriefSource(BaseModel):
    title: str
    url: str
    source: str | None = None
    provider: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    market: MarketBriefMarket | None = None
    snippet: str | None = None


class MarketBriefTheme(BaseModel):
    title: str
    summary: str
    markets: list[MarketBriefMarket] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    validation_signals: list[str] = Field(default_factory=list)
    invalidation_signals: list[str] = Field(default_factory=list)


class MarketBriefRisk(BaseModel):
    risk: str
    severity: Literal["low", "medium", "high"] = "medium"
    markets: list[MarketBriefMarket] = Field(default_factory=list)
    mitigation: str | None = None


class MarketBriefSignal(BaseModel):
    signal: str
    markets: list[MarketBriefMarket] = Field(default_factory=list)
    why_it_matters: str | None = None


class MarketBriefSchedule(BaseModel):
    trigger: MarketBriefTrigger
    slot: str | None = None
    provider: str | None = None
    automation_key: str | None = None


class PremarketBrief(BaseModel):
    type: Literal["premarket_brief"] = "premarket_brief"
    brief_id: str
    title: str
    summary: str
    markets: list[MarketBriefMarket]
    trading_day: str | None = None
    trading_days: dict[MarketBriefMarket, str | None] = Field(default_factory=dict)
    generated_at: str
    information_cutoff_at: str
    data_quality_level: Literal["high", "medium", "low"]
    schedule: MarketBriefSchedule
    market_calendar: list[MarketCalendarItem] = Field(default_factory=list)
    market_snapshots: list[MarketSnapshot] = Field(default_factory=list)
    overnight_moves: list[str] = Field(default_factory=list)
    yesterday_review: list[str] = Field(default_factory=list)
    today_variables: list[str] = Field(default_factory=list)
    main_themes: list[MarketBriefTheme] = Field(default_factory=list)
    ambush_directions: list[MarketBriefTheme] = Field(default_factory=list)
    risks: list[MarketBriefRisk] = Field(default_factory=list)
    opening_validation_signals: list[MarketBriefSignal] = Field(default_factory=list)
    sources: list[MarketBriefSource] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
