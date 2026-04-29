from diverge.valuation.fcff import normalize_fcff
from diverge.valuation.schemas import FinancialSnapshot


def test_normalize_fcff_uses_multi_year_median_for_outlier_case():
    financials = [
        FinancialSnapshot(period="FY2023", free_cash_flow=100),
        FinancialSnapshot(period="FY2024", free_cash_flow=-300),
        FinancialSnapshot(period="FY2025", free_cash_flow=110),
    ]

    result = normalize_fcff(financials)

    assert result.value == 100
