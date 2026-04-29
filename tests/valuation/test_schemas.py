from datetime import date

from diverge.valuation.schemas import (
    AssumptionValue,
    FinancialSnapshot,
    MarketContext,
    ValuationInput,
)


def test_latest_financial_prefers_newest_report_date_and_tracks_assumptions():
    valuation_input = ValuationInput(
        ticker="AAPL",
        market=MarketContext(
            market="us",
            currency="USD",
            beta=1.2,
            diluted_shares_outstanding=110.0,
        ),
        financials=[
            FinancialSnapshot(period="FY2024", report_date=date(2024, 9, 30)),
            FinancialSnapshot(period="FY2025", report_date=date(2025, 9, 30)),
        ],
        assumptions={
            "beta": AssumptionValue(
                value=1.2,
                source="yfinance.info",
                as_of=date(2026, 3, 24),
            ),
        },
    )

    assert valuation_input.latest_financial.period == "FY2025"
    assert valuation_input.assumptions["beta"].source == "yfinance.info"
    assert valuation_input.market.beta == 1.2
    assert valuation_input.market.diluted_shares_outstanding == 110.0
