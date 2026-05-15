from __future__ import annotations

import json
from typing import Any

import pandas as pd


def _as_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def build_candidate_pool(
    results: pd.DataFrame,
    *,
    trade_date: str,
    market: str,
    strategy_ids: list[str],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    if not results.empty:
        for row in results.to_dict(orient="records"):
            symbol = str(row.get("symbol") or "")
            if not symbol:
                continue
            score = float(row.get("score") or row.get("total_score") or 0)
            candidate_type = str(
                row.get("candidate_type") or ("leader" if score >= 80 else "watch")
            )
            reason = str(
                row.get("reason")
                or "Candidate matched the configured opportunity strategy."
            )
            candidates.append(
                {
                    "symbol": symbol,
                    "name": row.get("name"),
                    "market": str(row.get("market") or market),
                    "theme_id": row.get("theme_id"),
                    "theme_name": row.get("theme_name"),
                    "candidate_type": candidate_type,
                    "stock_score": round(score, 2),
                    "theme_hot_score": row.get("theme_hot_score"),
                    "capital_score": row.get("capital_score")
                    or row.get("theme_capital_score"),
                    "technical_score": row.get("technical_score"),
                    "catalyst_score": row.get("catalyst_score"),
                    "backtest_signal": row.get("strategy_id")
                    or (strategy_ids[0] if strategy_ids else None),
                    "recommended_next_step": "ANALYZE" if score >= 80 else "WATCH",
                    "reason": reason,
                    "risk_flags": _as_json(row.get("risk_flags")) or [],
                    "data_quality_flags": _as_json(row.get("data_quality_flags")) or [],
                }
            )
    candidates.sort(key=lambda row: float(row.get("stock_score") or 0), reverse=True)
    return {
        "trade_date": trade_date,
        "market": market,
        "strategy_ids": strategy_ids,
        "candidates": candidates,
    }


def opportunity_events_from_candidates(
    candidate_pool: dict[str, Any], *, source_run_id: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    trade_date = str(candidate_pool.get("trade_date") or "")
    for index, candidate in enumerate(candidate_pool.get("candidates") or [], start=1):
        symbol = str(candidate.get("symbol") or "")
        events.append(
            {
                "event_id": f"{source_run_id}-{index:04d}",
                "trade_date": trade_date,
                "scope": "symbol",
                "event_type": "entry_candidate",
                "symbol": symbol,
                "theme_id": candidate.get("theme_id"),
                "score": candidate.get("stock_score"),
                "evidence": [
                    candidate.get("reason") or "Candidate matched configured rules."
                ],
                "source_run_id": source_run_id,
                "next_step": candidate.get("recommended_next_step") or "WATCH",
            }
        )
    return events
