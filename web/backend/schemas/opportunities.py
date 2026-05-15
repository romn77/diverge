from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OpportunityRunPayload(BaseModel):
    trade_date: str | None = None
    market: str = "cn"
    strategy_ids: list[str] = Field(
        default_factory=lambda: ["theme_capital_breakout_v1"]
    )
    factor_snapshot_path: str | None = None
    price_history_path: str | None = None
    cost_model_id: str | None = None
    force: bool = False


class WatchlistMutationPayload(BaseModel):
    symbol: str
    market: str = "cn"
    name: str | None = None
    theme_id: str | None = None
    status: str = "NEW"
    reason: str | None = None
    source_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateAnalyzePayload(BaseModel):
    run_id: str | None = None
    analysis_date: str | None = None
    output_language: str | None = None
    model_profile: str | None = None
    opportunity_context: dict[str, Any] | None = None
    report_visibility: Literal["private", "workspace"] = "private"
