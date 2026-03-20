from __future__ import annotations

from dataclasses import dataclass

from .schemas import ValuationInput


@dataclass(slots=True)
class DCFResult:
    forecast_cash_flows: list[float]
    discounted_cash_flows: list[float]
    terminal_value: float
    discounted_terminal_value: float
    enterprise_value: float
    net_debt: float
    equity_value: float
    fair_value_per_share: float | None
    assumptions: dict[str, float | int]


def calculate_dcf(
    valuation_input: ValuationInput,
    *,
    growth_rate: float = 0.05,
    terminal_growth_rate: float = 0.02,
    wacc: float = 0.10,
    projection_years: int = 5,
) -> DCFResult:
    if wacc <= terminal_growth_rate:
        raise ValueError("wacc must be greater than terminal_growth_rate")
    if projection_years < 1:
        raise ValueError("projection_years must be positive")

    latest = valuation_input.latest_financial
    base_fcf = latest.free_cash_flow
    if base_fcf is None:
        raise ValueError("free_cash_flow is required for DCF")

    forecast_cash_flows: list[float] = []
    discounted_cash_flows: list[float] = []

    for year in range(1, projection_years + 1):
        projected_fcf = base_fcf * ((1 + growth_rate) ** year)
        forecast_cash_flows.append(projected_fcf)
        discounted_cash_flows.append(projected_fcf / ((1 + wacc) ** year))

    terminal_cash_flow = forecast_cash_flows[-1] * (1 + terminal_growth_rate)
    terminal_value = terminal_cash_flow / (wacc - terminal_growth_rate)
    discounted_terminal_value = terminal_value / ((1 + wacc) ** projection_years)
    enterprise_value = sum(discounted_cash_flows) + discounted_terminal_value

    total_debt = latest.total_debt or 0.0
    cash = latest.cash_and_equivalents or 0.0
    net_debt = total_debt - cash
    equity_value = enterprise_value - net_debt

    shares_outstanding = valuation_input.market.shares_outstanding
    fair_value_per_share = None
    if shares_outstanding and shares_outstanding > 0:
        fair_value_per_share = equity_value / shares_outstanding

    return DCFResult(
        forecast_cash_flows=forecast_cash_flows,
        discounted_cash_flows=discounted_cash_flows,
        terminal_value=terminal_value,
        discounted_terminal_value=discounted_terminal_value,
        enterprise_value=enterprise_value,
        net_debt=net_debt,
        equity_value=equity_value,
        fair_value_per_share=fair_value_per_share,
        assumptions={
            "growth_rate": growth_rate,
            "terminal_growth_rate": terminal_growth_rate,
            "wacc": wacc,
            "projection_years": projection_years,
        },
    )
