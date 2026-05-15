from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from diverge.opportunity.config import load_strategy_config as _load_strategy_payload


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    name: str
    field: str
    weight: float
    direction: str = "higher"
    transform: str = "zscore"


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    strategy_id: str
    strategy_name: str
    market: str
    version: int
    filters: dict[str, Any]
    score_components: tuple[ScoreComponent, ...]
    output: dict[str, Any]
    raw: dict[str, Any]


def parse_strategy_config(payload: dict[str, Any]) -> StrategyConfig:
    strategy_id = str(payload.get("strategy_id") or "").strip()
    if not strategy_id:
        raise ValueError("strategy_id is required")
    raw_components = (payload.get("score") or {}).get("components") or []
    components: list[ScoreComponent] = []
    for raw in raw_components:
        if not isinstance(raw, dict):
            raise ValueError("score components must be mappings")
        components.append(
            ScoreComponent(
                name=str(raw.get("name") or raw.get("field") or "").strip(),
                field=str(raw.get("field") or "").strip(),
                weight=float(raw.get("weight") or 0),
                direction=str(raw.get("direction") or "higher").strip().lower(),
                transform=str(raw.get("transform") or "zscore").strip().lower(),
            )
        )
    if not components:
        raise ValueError("at least one score component is required")
    if any(not component.field for component in components):
        raise ValueError("score component field is required")
    return StrategyConfig(
        strategy_id=strategy_id,
        strategy_name=str(payload.get("strategy_name") or strategy_id),
        market=str(payload.get("market") or "cn").strip().lower(),
        version=int(payload.get("version") or 1),
        filters=payload.get("filters") or {},
        score_components=tuple(components),
        output=payload.get("output") or {},
        raw=payload,
    )


def load_strategy_config(strategy_id: str) -> StrategyConfig:
    return parse_strategy_config(_load_strategy_payload(strategy_id))
