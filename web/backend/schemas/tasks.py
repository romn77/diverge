from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class TaskCreatePayload(BaseModel):
    ticker: str
    analysis_date: str
    analysts: list[str]
    research_depth: int
    model_profile: Optional[str] = None
    llm_provider: Optional[str] = None
    quick_think_llm: Optional[str] = None
    deep_think_llm: Optional[str] = None
    output_language: str
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    market_data_source: str = "massive"
    report_visibility: Literal["private", "workspace"] = "private"
