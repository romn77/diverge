from datetime import date

from tradingagents.valuation.multiples import calculate_multiples
from tradingagents.valuation.schemas import AssumptionValue, FinancialSnapshot, MarketContext


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


def test_calculate_multiples_returns_two_peg_versions_only_when_eps_growth_is_reliable():
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
        net_income=10.0,
        shareholders_equity=80.0,
        ebitda=50.0,
        revenue=100.0,
        free_cash_flow=10.0,
    )

    result = calculate_multiples(
        market,
        snapshot,
        assumptions={
            "forward_pe": AssumptionValue(value=25.0, source="provider"),
            "eps_growth_1y": AssumptionValue(value=0.20, source="provider"),
            "eps_growth_long_term": AssumptionValue(value=0.15, source="provider"),
        },
    )

    assert result["peg_forward_1y"] == 1.25
    assert result["peg_forward_long_term"] == 25.0 / 15.0


def test_calculate_multiples_omits_peg_when_eps_growth_is_not_reliable():
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
        net_income=10.0,
        shareholders_equity=80.0,
        ebitda=50.0,
        revenue=100.0,
        free_cash_flow=10.0,
    )

    result = calculate_multiples(
        market,
        snapshot,
        assumptions={
            "forward_pe": AssumptionValue(value=25.0, source="provider"),
            "eps_growth_1y": AssumptionValue(value=None, source="provider"),
            "eps_growth_long_term": AssumptionValue(value=-0.10, source="provider"),
        },
    )

    assert result["peg_forward_1y"] is None
    assert result["peg_forward_long_term"] is None
