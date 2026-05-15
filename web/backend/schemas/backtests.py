from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BacktestSnapshotPayload(BaseModel):
    strategy_id: str = "theme_capital_breakout_v1"
    market: str = "cn"
    signal_events_path: str | None = None
    price_history_path: str | None = None
    cost_model: dict[str, Any] | None = None
    horizons: list[int] = Field(default_factory=lambda: [1, 3, 5, 10, 20])
