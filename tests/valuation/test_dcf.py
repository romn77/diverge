from datetime import date

import pytest

from diverge.valuation.schemas import (
    AssumptionValue,
    FinancialSnapshot,
    MarketContext,
    ValuationInput,
)
from diverge.valuation.dcf import calculate_dcf, calculate_dcf_cases


def _build_input(shares_outstanding: float | None = 100.0) -> ValuationInput:
    return ValuationInput(
        ticker="ACME",
        market=MarketContext(
            market="us",
            currency="USD",
            share_price=50.0,
            shares_outstanding=shares_outstanding,
            market_cap=5_000.0,
        ),
        financials=[
            FinancialSnapshot(
                period="FY2025",
                report_date=date(2025, 12, 31),
                revenue=1_000.0,
                ebitda=240.0,
                net_income=120.0,
                free_cash_flow=100.0,
                cash_and_equivalents=50.0,
                total_debt=200.0,
                shareholders_equity=800.0,
            )
        ],
    )


def test_calculate_dcf_returns_expected_base_case():
    valuation_input = _build_input()

    result = calculate_dcf(
        valuation_input,
        growth_rate=0.10,
        terminal_growth_rate=0.03,
        wacc=0.10,
        projection_years=3,
    )

    assert result.enterprise_value == pytest.approx(1_771.428571, rel=1e-6)
    assert result.equity_value == pytest.approx(1_621.428571, rel=1e-6)
    assert result.fair_value_per_share == pytest.approx(16.21428571, rel=1e-6)
    assert len(result.forecast_cash_flows) == 3


def test_calculate_dcf_rejects_invalid_discount_rate_inputs():
    with pytest.raises(ValueError, match="wacc"):
        calculate_dcf(
            _build_input(),
            growth_rate=0.08,
            terminal_growth_rate=0.04,
            wacc=0.04,
        )


def test_calculate_dcf_allows_missing_shares_outstanding():
    result = calculate_dcf(
        _build_input(shares_outstanding=None),
        growth_rate=0.10,
        terminal_growth_rate=0.03,
        wacc=0.10,
        projection_years=3,
    )

    assert result.equity_value == pytest.approx(1_621.428571, rel=1e-6)
    assert result.fair_value_per_share is None


def test_calculate_dcf_bridges_enterprise_value_to_equity_value_with_net_debt():
    result = calculate_dcf(
        _build_input(),
        growth_rate=0.10,
        terminal_growth_rate=0.03,
        wacc=0.10,
        projection_years=3,
    )

    assert result.net_debt == pytest.approx(150.0)
    assert result.equity_value == pytest.approx(result.enterprise_value - 150.0)


def test_calculate_dcf_uses_multi_stage_growth_and_dynamic_cost_of_equity():
    valuation_input = ValuationInput(
        ticker="ACME",
        market=MarketContext(
            market="us",
            currency="USD",
            shares_outstanding=100,
            market_cap=5_000,
            beta=1.2,
        ),
        financials=[
            FinancialSnapshot(
                period="FY2023",
                report_date=date(2023, 12, 31),
                free_cash_flow=90,
                cash_and_equivalents=50,
                total_debt=200,
            ),
            FinancialSnapshot(
                period="FY2024",
                report_date=date(2024, 12, 31),
                free_cash_flow=100,
                cash_and_equivalents=50,
                total_debt=200,
            ),
            FinancialSnapshot(
                period="FY2025",
                report_date=date(2025, 12, 31),
                free_cash_flow=110,
                cash_and_equivalents=50,
                total_debt=200,
            ),
        ],
        assumptions={
            "short_term_growth": AssumptionValue(value=0.12, source="provider"),
            "terminal_growth_rate": AssumptionValue(
                value=0.03,
                source="internal-default",
            ),
            "risk_free_rate": AssumptionValue(value=0.04, source="provider"),
            "equity_risk_premium": AssumptionValue(
                value=0.05,
                source="internal-config",
            ),
            "cost_of_debt": AssumptionValue(value=0.05, source="internal-config"),
            "tax_rate": AssumptionValue(value=0.25, source="internal-config"),
        },
    )

    result = calculate_dcf(valuation_input, high_growth_years=3, fade_years=2)

    assert result.assumptions["wacc"] > result.assumptions["terminal_growth_rate"]
    assert len(result.forecast_cash_flows) == 5
    assert result.fair_value_per_share is not None


def test_calculate_dcf_cases_returns_bear_base_and_bull_in_value_order():
    cases = calculate_dcf_cases(_build_input())

    assert list(cases.keys()) == ["bear", "base", "bull"]
    assert cases["bear"].fair_value_per_share < cases["base"].fair_value_per_share
    assert cases["base"].fair_value_per_share < cases["bull"].fair_value_per_share
