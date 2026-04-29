from datetime import date

from diverge.valuation.formatter import format_valuation_sections
from diverge.valuation.schemas import (
    AssumptionValue,
    FinancialSnapshot,
    MarketContext,
    ValuationInput,
)


def test_format_valuation_sections_marks_etf_as_dcf_not_applicable():
    valuation_input = ValuationInput(
        ticker="SPY",
        market=MarketContext(
            market="us",
            currency="USD",
            market_cap=500_000.0,
            shares_outstanding=1_000.0,
        ),
        financials=[
            FinancialSnapshot(
                period="annual",
                report_date=date(2025, 12, 31),
                revenue=None,
                ebitda=None,
                net_income=None,
                free_cash_flow=None,
            )
        ],
        instrument_type="etf",
        valuation_applicability="not_applicable",
        valuation_applicability_reason="ETF instruments do not have operating cash flows suitable for DCF.",
    )

    rendered = format_valuation_sections(valuation_input)

    assert "## DCF Applicability" in rendered
    assert "DCF Not Applicable" in rendered
    assert "## DCF Summary" not in rendered
    assert "## Sensitivity Summary" not in rendered
    assert "## Valuation Assumptions" not in rendered
    assert "## Multiples Summary" in rendered


def test_format_valuation_sections_renders_assumption_provenance():
    valuation_input = ValuationInput(
        ticker="AAPL",
        market=MarketContext(
            market="us",
            currency="USD",
            market_cap=5_000.0,
            shares_outstanding=100.0,
        ),
        financials=[
            FinancialSnapshot(
                period="annual",
                report_date=date(2025, 12, 31),
                revenue=1_000.0,
                ebitda=220.0,
                net_income=120.0,
                free_cash_flow=100.0,
                cash_and_equivalents=50.0,
                total_debt=200.0,
                shareholders_equity=600.0,
            )
        ],
        assumptions={
            "short_term_growth": AssumptionValue(
                value=0.12,
                source="yfinance.earnings_estimate",
            ),
            "forward_pe": AssumptionValue(
                value=25.0,
                source="yfinance.info",
            ),
            "eps_growth_1y": AssumptionValue(
                value=0.20,
                source="yfinance.earnings_estimate",
            ),
            "eps_growth_long_term": AssumptionValue(
                value=0.15,
                source="yfinance.growth_estimates",
            ),
            "risk_free_rate": AssumptionValue(
                value=0.042,
                source="yfinance:^TNX",
            ),
            "equity_risk_premium": AssumptionValue(
                value=0.05,
                source="internal-config",
                fallback_reason="House ERP assumption.",
            ),
        },
    )

    rendered = format_valuation_sections(valuation_input)

    assert "## Valuation Assumptions" in rendered
    assert "## DCF Scenario Summary" in rendered
    assert "PEG (1Y Forward)" in rendered
    assert "PEG (Long-Term Forward)" in rendered
    assert "yfinance:^TNX" in rendered
    assert "House ERP assumption." in rendered
