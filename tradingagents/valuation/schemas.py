from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class FinancialSnapshot:
    period: str
    report_date: date | None = None
    revenue: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    free_cash_flow: float | None = None
    cash_and_equivalents: float | None = None
    total_debt: float | None = None
    shareholders_equity: float | None = None
    currency: str | None = None
    frequency: str | None = None


@dataclass(slots=True)
class MarketContext:
    market: str
    currency: str
    share_price: float | None = None
    shares_outstanding: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    report_date: date | None = None


@dataclass(slots=True)
class ValuationInput:
    ticker: str
    market: MarketContext
    financials: list[FinancialSnapshot] = field(default_factory=list)

    @property
    def latest_financial(self) -> FinancialSnapshot:
        if not self.financials:
            raise ValueError("valuation input requires at least one financial snapshot")
        return max(
            self.financials,
            key=lambda snapshot: snapshot.report_date or date.min,
        )
