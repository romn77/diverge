from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MarketBriefMarket = Literal["cn", "us"]


class MarketBriefCreatePayload(BaseModel):
    markets: list[MarketBriefMarket] = Field(default_factory=lambda: ["cn", "us"])
    output_language: str = "zh-CN"
    report_visibility: Literal["private", "workspace"] = "workspace"
