from __future__ import annotations

from pydantic import BaseModel, Field


class ScreenTaskCreatePayload(BaseModel):
    markets: list[str]
    as_of_date: str
    top_k: int
    cn_data_source: str = "tushare"
    us_data_source: str = "massive"
    history_cache_policy: str = "cache_only"
    breakout_types: list[str] = Field(default_factory=list)
    filter_preset_selections: dict[str, str] = Field(default_factory=dict)
    ranking_profile_id: str | None = None
    include_fundamentals: bool = False
    cn_fundamental_source: str = "tushare"
    us_fundamental_source: str = "simfin"
