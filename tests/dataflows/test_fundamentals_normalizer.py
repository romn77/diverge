from datetime import date

import pytest

from tradingagents.dataflows.fundamentals_normalizer import (
    normalize_fundamentals_payload,
)


def test_normalize_alpha_vantage_style_payload():
    result = normalize_fundamentals_payload(
        {
            "fundamentals": {
                "Symbol": "MSFT",
                "AssetType": "Common Stock",
                "MarketCapitalization": "2500",
                "SharesOutstanding": "100",
                "Currency": "USD",
            },
            "balance_sheet": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2025-12-31",
                        "cashAndCashEquivalentsAtCarryingValue": "80",
                        "shortLongTermDebtTotal": "150",
                        "totalShareholderEquity": "600",
                    }
                ]
            },
            "cashflow": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2025-12-31",
                        "operatingCashflow": "160",
                        "capitalExpenditures": "-40",
                    }
                ]
            },
            "income_statement": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2025-12-31",
                        "totalRevenue": "1000",
                        "ebitda": "220",
                        "netIncome": "120",
                    }
                ]
            },
        },
        vendor="alpha_vantage",
        market="us",
        ticker="MSFT",
        frequency="annual",
    )

    assert result.ticker == "MSFT"
    assert result.instrument_type == "operating_company"
    assert result.valuation_applicability == "applicable"
    assert result.market.market_cap == 2500.0
    assert result.market.shares_outstanding == 100.0
    assert result.market.currency == "USD"
    assert result.latest_financial.report_date == date(2025, 12, 31)
    assert result.latest_financial.free_cash_flow == 120.0
    assert result.latest_financial.total_debt == 150.0


def test_normalize_yfinance_style_payload():
    result = normalize_fundamentals_payload(
        {
            "fundamentals": (
                "# Company Fundamentals for AAPL\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                "Quote Type: EQUITY\n"
                "Market Cap: 3000\n"
                "Free Cash Flow: 140\n"
                "EBITDA: 400\n"
                "Net Income: 200\n"
            ),
            "balance_sheet": (
                "# Balance Sheet data for AAPL (annual)\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                ",2025-12-31\n"
                "Cash And Cash Equivalents,100\n"
                "Total Debt,250\n"
                "Stockholders Equity,900\n"
                "Ordinary Shares Number,50\n"
            ),
            "cashflow": (
                "# Cash Flow data for AAPL (annual)\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                ",2025-12-31\n"
                "Free Cash Flow,140\n"
            ),
            "income_statement": (
                "# Income Statement data for AAPL (annual)\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                ",2025-12-31\n"
                "Total Revenue,1200\n"
                "EBITDA,400\n"
                "Net Income,200\n"
            ),
        },
        market="us",
        ticker="AAPL",
        frequency="annual",
    )

    assert result.ticker == "AAPL"
    assert result.instrument_type == "operating_company"
    assert result.valuation_applicability == "applicable"
    assert result.market.market_cap == 3000.0
    assert result.market.shares_outstanding == 50.0
    assert result.latest_financial.report_date == date(2025, 12, 31)
    assert result.latest_financial.cash_and_equivalents == 100.0
    assert result.latest_financial.shareholders_equity == 900.0


def test_normalize_cn_payload_keeps_missing_fields_optional():
    result = normalize_fundamentals_payload(
        {
            "fundamentals": (
                "# CN Company Fundamentals\n\n"
                "Ticker: 600519.SH\n"
                "Report Date: 2025-12-31\n"
                "营业总收入: 1800\n"
                "净利润: 900\n"
            ),
            "balance_sheet": (
                "# CN Balance Sheet data for 600519 (quarterly)\n"
                "# Total records: 1\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                "报告日,货币资金,负债合计\n"
                "2025-12-31,500,700\n"
            ),
            "cashflow": (
                "# CN Cash Flow data for 600519 (quarterly)\n"
                "# Total records: 1\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                "报告日,经营活动产生的现金流量净额\n"
                "2025-12-31,650\n"
            ),
            "income_statement": (
                "# CN Income Statement data for 600519 (quarterly)\n"
                "# Total records: 1\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                "报告日,营业收入,净利润\n"
                "2025-12-31,1800,900\n"
            ),
        },
        market="cn",
        ticker="600519.SH",
        frequency="quarterly",
    )

    assert result.market.market == "cn"
    assert result.instrument_type == "operating_company"
    assert result.valuation_applicability == "applicable"
    assert result.latest_financial.report_date == date(2025, 12, 31)
    assert result.latest_financial.revenue == 1800.0
    assert result.latest_financial.free_cash_flow == 650.0
    assert result.latest_financial.shareholders_equity is None


def test_normalize_etf_payload_marks_dcf_as_not_applicable():
    result = normalize_fundamentals_payload(
        {
            "fundamentals": (
                "# Company Fundamentals for SPY\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                "Quote Type: ETF\n"
                "Fund Family: SPDR\n"
                "Market Cap: 500000\n"
                "Shares Outstanding: 1000\n"
            ),
            "balance_sheet": "",
            "cashflow": "",
            "income_statement": "",
        },
        vendor="yfinance",
        market="us",
        ticker="SPY",
        frequency="annual",
    )

    assert result.instrument_type == "etf"
    assert result.valuation_applicability == "not_applicable"
    assert "etf" in (result.valuation_applicability_reason or "").lower()


def test_normalizer_raises_explicit_error_for_unknown_payload():
    with pytest.raises(ValueError, match="Could not normalize fundamentals payload"):
        normalize_fundamentals_payload(
            {"fundamentals": "completely unstructured text"},
            ticker="BAD",
        )
