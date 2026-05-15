from __future__ import annotations

from typing import Any

from diverge.opportunity.config import load_watchlist_policy


def build_watchlist_snapshot(candidate_pool: dict[str, Any]) -> dict[str, Any]:
    policy = load_watchlist_policy()
    auto_add = policy.get("auto_add", {}) if isinstance(policy, dict) else {}
    min_score = float(auto_add.get("min_score", 80))
    allowed_types = set(auto_add.get("candidate_types", ["leader", "confirmed"]))
    max_items = int(auto_add.get("max_new_items_per_run", 20))
    items: list[dict[str, Any]] = []
    for candidate in candidate_pool.get("candidates") or []:
        if len(items) >= max_items:
            break
        score = float(candidate.get("stock_score") or 0)
        candidate_type = str(candidate.get("candidate_type") or "watch")
        if not auto_add.get("enabled", True):
            continue
        if score < min_score or candidate_type not in allowed_types:
            continue
        items.append(
            {
                "symbol": candidate.get("symbol"),
                "name": candidate.get("name"),
                "theme_id": candidate.get("theme_id"),
                "status": "NEW",
                "days_in_pool": 0,
                "last_event": "candidate_auto_added",
                "score_change": 0,
                "theme_score_change": 0,
                "triggered_actions": [],
                "risk_flags": candidate.get("risk_flags") or [],
                "reason": candidate.get("reason")
                or "Added by watchlist auto-add policy.",
            }
        )
    return {"trade_date": candidate_pool.get("trade_date"), "items": items}
