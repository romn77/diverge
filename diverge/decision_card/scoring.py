from __future__ import annotations


def compute_conviction_score(
    *,
    rating: str,
    confidence: str,
    evidence_count: int,
    risk_count: int,
    data_quality_issue_count: int,
) -> int:
    """Score the multi-agent conviction behind the final ruling."""
    base = {
        "BUY": 82,
        "OVERWEIGHT": 72,
        "HOLD": 55,
        "UNDERWEIGHT": 38,
        "SELL": 25,
    }.get(rating, 50)

    if confidence == "high":
        base += 8
    elif confidence == "low":
        base -= 10

    base += min(evidence_count, 5) * 2
    base -= min(risk_count, 5) * 3
    base -= min(data_quality_issue_count, 5) * 4

    return max(0, min(100, base))
