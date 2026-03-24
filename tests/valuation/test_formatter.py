from datetime import date

from tradingagents.valuation.formatter import format_valuation_sections
from tradingagents.valuation.schemas import FinancialSnapshot, MarketContext, ValuationInput


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
