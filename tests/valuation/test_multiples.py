from datetime import date

from tradingagents.valuation.multiples import calculate_multiples
from tradingagents.valuation.schemas import FinancialSnapshot, MarketContext


def test_calculate_multiples_returns_none_for_missing_or_zero_denominators():
    market = MarketContext(
        market="us",
        currency="USD",
        share_price=25.0,
        shares_outstanding=10.0,
        market_cap=250.0,
        enterprise_value=400.0,
    )
    snapshot = FinancialSnapshot(
        period="FY2025",
        report_date=date(2025, 12, 31),
        net_income=0.0,
        shareholders_equity=None,
        ebitda=None,
        revenue=100.0,
        free_cash_flow=None,
    )

    result = calculate_multiples(market, snapshot)

    assert result["p_e"] is None
    assert result["p_b"] is None
    assert result["ev_ebitda"] is None
    assert result["ev_sales"] == 4.0
    assert result["fcf_yield"] is None
