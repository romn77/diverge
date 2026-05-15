from __future__ import annotations

import json
from typing import Any

import pandas as pd


def build_signal_events(
    results: pd.DataFrame, *, strategy_id: str, trade_date: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, row in enumerate(results.to_dict(orient="records"), start=1):
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        evidence = row.get("matched_rules") or row.get("matched_conditions") or []
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except Exception:
                evidence = [evidence]
        events.append(
            {
                "event_id": f"{trade_date.replace('-', '')}-{strategy_id}-{index:04d}",
                "strategy_id": strategy_id,
                "trade_date": trade_date,
                "symbol": symbol,
                "market": row.get("market") or "cn",
                "signal_type": "entry_candidate",
                "score": row.get("score"),
                "rank": row.get("rank") or row.get("global_rank") or index,
                "candidate_type": row.get("candidate_type") or "watch",
                "theme_id": row.get("theme_id"),
                "evidence": evidence,
                "data_quality_flags": row.get("data_quality_flags") or [],
            }
        )
    return events
