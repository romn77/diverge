from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class TaskCreatePayload(BaseModel):
    ticker: str
    analysis_date: str
    analysts: list[str]
    research_depth: int
    llm_provider: str
    quick_think_llm: str
    deep_think_llm: str
    output_language: str
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    market_data_source: str = "massive"
    report_visibility: Literal["private", "workspace"] = "private"
