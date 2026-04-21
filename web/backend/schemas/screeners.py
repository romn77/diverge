from __future__ import annotations

from pydantic import BaseModel, Field


class ScreenTaskCreatePayload(BaseModel):
    markets: list[str]
    as_of_date: str
    top_k: int
    cn_data_source: str = "tushare"
    breakout_types: list[str] = Field(default_factory=list)
