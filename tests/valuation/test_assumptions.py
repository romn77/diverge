from diverge.valuation.assumptions import (
    resolve_assumption,
    resolve_short_term_growth,
)
from diverge.valuation.schemas import AssumptionValue


def test_resolve_short_term_growth_prefers_provider_estimate():
    assumptions = {
        "short_term_growth": AssumptionValue(value=0.18, source="provider"),
        "historical_revenue_cagr": AssumptionValue(value=0.10, source="history"),
    }

    result = resolve_short_term_growth(assumptions)

    assert result.value == 0.18
    assert result.source == "provider"


def test_resolve_assumption_returns_existing_value_when_present():
    assumptions = {
        "risk_free_rate": AssumptionValue(value=0.04, source="provider"),
    }

    result = resolve_assumption(assumptions, "risk_free_rate", default=0.03)

    assert result.value == 0.04
    assert result.source == "provider"


def test_resolve_assumption_returns_default_with_low_confidence_when_missing():
    result = resolve_assumption({}, "risk_free_rate", default=0.03)

    assert result.value == 0.03
    assert result.confidence == "low"
    assert "Missing 'risk_free_rate'" in (result.fallback_reason or "")
