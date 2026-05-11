from __future__ import annotations

from pydantic import BaseModel, Field


class DataSyncOhlcvPayload(BaseModel):
    markets: list[str]
    as_of_date: str
    top_k: int = Field(default=100, ge=1, le=100)
    cn_data_source: str = "tushare"
    cn_data_source_fallbacks: list[str] = Field(default_factory=list)
    us_data_source: str = "yfinance"
    us_data_source_fallbacks: list[str] = Field(default_factory=list)
    cn_manifest_path: str | None = None
    us_manifest_path: str | None = None
    run_screener_prewarm: bool = False


class DataSyncFundamentalsPayload(BaseModel):
    market: str
    source: str
    symbols: list[str] = Field(default_factory=list)
    as_of_date: str | None = None
    data_dir: str | None = None
    manifest_path: str | None = None
