from __future__ import annotations

from .schemas import AssumptionValue


def resolve_short_term_growth(
    assumptions: dict[str, AssumptionValue],
) -> AssumptionValue:
    for key in ("short_term_growth", "historical_revenue_cagr", "historical_fcf_cagr"):
        assumption = assumptions.get(key)
        if assumption and assumption.value is not None:
            return assumption
    return AssumptionValue(
        value=0.05,
        source="internal-default",
        confidence="low",
        fallback_reason="No provider or historical growth signals available.",
    )


def resolve_assumption(
    assumptions: dict[str, AssumptionValue],
    key: str,
    *,
    default: float,
    source: str = "internal-default",
) -> AssumptionValue:
    assumption = assumptions.get(key)
    if assumption and assumption.value is not None:
        return assumption
    return AssumptionValue(
        value=default,
        source=source,
        confidence="low",
        fallback_reason=f"Missing '{key}' in valuation_input.assumptions.",
    )
