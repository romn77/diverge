from __future__ import annotations

import pandas as pd
import pytest

from diverge.valuation.schemas import AssumptionValue


class _FakeTicker:
    def __init__(self):
        self.info = {
            "beta": 1.15,
            "sharesOutstanding": 100.0,
            "impliedSharesOutstanding": 110.0,
            "currentPrice": 50.0,
            "marketCap": 5_000.0,
            "enterpriseValue": 5_150.0,
            "currency": "USD",
            "quoteType": "EQUITY",
            "forwardPE": 25.0,
            "forwardEps": 2.0,
        }
        self.income_stmt = pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): {
                    "Total Revenue": 1_000.0,
                    "EBITDA": 220.0,
                    "Net Income": 120.0,
                },
                pd.Timestamp("2024-12-31"): {
                    "Total Revenue": 950.0,
                    "EBITDA": 210.0,
                    "Net Income": 110.0,
                },
            }
        )
        self.cashflow = pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): {
                    "Free Cash Flow": 100.0,
                    "Operating Cash Flow": 150.0,
                    "Capital Expenditure": -50.0,
                },
                pd.Timestamp("2024-12-31"): {
                    "Free Cash Flow": 95.0,
                    "Operating Cash Flow": 140.0,
                    "Capital Expenditure": -45.0,
                },
            }
        )
        self.balance_sheet = pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): {
                    "Cash And Cash Equivalents": 50.0,
                    "Total Debt": 200.0,
                    "Stockholders Equity": 800.0,
                },
                pd.Timestamp("2024-12-31"): {
                    "Cash And Cash Equivalents": 45.0,
                    "Total Debt": 210.0,
                    "Stockholders Equity": 760.0,
                },
            }
        )
        self.earnings_estimate = pd.DataFrame(
            {
                "avg": [2.0, 2.4],
                "growth": [0.18, 0.20],
                "numberOfAnalysts": [12, 12],
            },
            index=["0y", "+1y"],
        )
        self.revenue_estimate = pd.DataFrame(
            {"growth": [0.22, 0.15]},
            index=["0y", "+1y"],
        )
        self.growth_estimates = pd.DataFrame(
            {"stock": [0.14]},
            index=["+5y"],
        )


def test_build_yfinance_valuation_input_collects_growth_beta_and_treasury(
    monkeypatch,
):
    from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input

    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation.yf.Ticker",
        lambda symbol: _FakeTicker(),
    )
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(
            value=0.042,
            source="yfinance:^TNX",
            confidence="medium",
        ),
    )

    valuation_input = build_yfinance_valuation_input(
        "AAPL",
        curr_date="2026-03-24",
        freq="annual",
    )

    assert valuation_input.market.market == "us"
    assert valuation_input.market.beta == 1.15
    assert valuation_input.market.enterprise_value == 5_150.0
    assert valuation_input.market.diluted_shares_outstanding == 110.0
    assert valuation_input.assumptions["risk_free_rate"].source == "yfinance:^TNX"
    assert valuation_input.assumptions["short_term_growth"].source.startswith("yfinance")
    assert len(valuation_input.financials) == 2
    assert valuation_input.assumptions["forward_pe"].value == 25.0
    assert valuation_input.assumptions["eps_growth_1y"].value == pytest.approx(0.20)
    assert valuation_input.assumptions["eps_growth_long_term"].value == 0.14


def test_build_yfinance_valuation_input_marks_missing_beta_as_low_confidence(
    monkeypatch,
):
    from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input

    ticker = _FakeTicker()
    ticker.info["beta"] = None

    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation.yf.Ticker",
        lambda symbol: ticker,
    )
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(
            value=0.042,
            source="yfinance:^TNX",
            confidence="medium",
        ),
    )

    valuation_input = build_yfinance_valuation_input("AAPL", curr_date="2026-03-24")

    assert valuation_input.market.beta is None
    assert valuation_input.assumptions["beta"].confidence == "low"


def test_build_yfinance_valuation_input_marks_etf_as_not_applicable(monkeypatch):
    from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input

    ticker = _FakeTicker()
    ticker.info["quoteType"] = "ETF"

    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation.yf.Ticker",
        lambda symbol: ticker,
    )
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(
            value=0.042,
            source="yfinance:^TNX",
            confidence="medium",
        ),
    )

    valuation_input = build_yfinance_valuation_input("SPY", curr_date="2026-03-24")

    assert valuation_input.instrument_type == "etf"
    assert valuation_input.valuation_applicability == "not_applicable"


def test_build_yfinance_valuation_input_marks_reit_as_not_applicable(monkeypatch):
    from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input

    ticker = _FakeTicker()
    ticker.info["industry"] = "REIT - Industrial"

    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation.yf.Ticker",
        lambda symbol: ticker,
    )
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(
            value=0.042,
            source="yfinance:^TNX",
            confidence="medium",
        ),
    )

    valuation_input = build_yfinance_valuation_input("PLD", curr_date="2026-03-24")

    assert valuation_input.instrument_type == "reit"
    assert valuation_input.valuation_applicability == "not_applicable"


def test_build_yfinance_valuation_input_marks_insurance_as_not_applicable(monkeypatch):
    from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input

    ticker = _FakeTicker()
    ticker.info["industry"] = "Insurance - Diversified"

    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation.yf.Ticker",
        lambda symbol: ticker,
    )
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(
            value=0.042,
            source="yfinance:^TNX",
            confidence="medium",
        ),
    )

    valuation_input = build_yfinance_valuation_input("BRK-A", curr_date="2026-03-24")

    assert valuation_input.instrument_type == "insurance"
    assert valuation_input.valuation_applicability == "not_applicable"


def test_build_yfinance_valuation_input_marks_bank_as_not_applicable(monkeypatch):
    from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input

    ticker = _FakeTicker()
    ticker.info["industry"] = "Banks - Regional"

    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation.yf.Ticker",
        lambda symbol: ticker,
    )
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(
            value=0.042,
            source="yfinance:^TNX",
            confidence="medium",
        ),
    )

    valuation_input = build_yfinance_valuation_input("JPM", curr_date="2026-03-24")

    assert valuation_input.instrument_type == "bank"
    assert valuation_input.valuation_applicability == "not_applicable"
