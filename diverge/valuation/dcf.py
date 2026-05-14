from __future__ import annotations

from dataclasses import dataclass

from .assumptions import resolve_assumption, resolve_short_term_growth
from .fcff import normalize_fcff
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
    growth_rate: float | None = None,
    terminal_growth_rate: float | None = None,
    wacc: float | None = None,
    projection_years: int | None = None,
    high_growth_years: int = 3,
    fade_years: int = 2,
) -> DCFResult:
    if (
        growth_rate is not None
        or terminal_growth_rate is not None
        or wacc is not None
        or projection_years is not None
    ):
        return _calculate_legacy_dcf(
            valuation_input,
            growth_rate=growth_rate or 0.05,
            terminal_growth_rate=terminal_growth_rate or 0.02,
            wacc=wacc or 0.10,
            projection_years=projection_years or 5,
        )

    if high_growth_years < 1:
        raise ValueError("high_growth_years must be positive")
    if fade_years < 0:
        raise ValueError("fade_years must be non-negative")

    latest = valuation_input.latest_financial
    base_fcff = normalize_fcff(valuation_input.financials).value
    if base_fcff is None:
        raise ValueError("free_cash_flow is required for DCF")

    short_term_growth = float(
        resolve_short_term_growth(valuation_input.assumptions).value
    )
    resolved_terminal_growth_rate = float(
        resolve_assumption(
            valuation_input.assumptions,
            "terminal_growth_rate",
            default=0.03,
        ).value
    )
    resolved_risk_free_rate = float(
        resolve_assumption(
            valuation_input.assumptions,
            "risk_free_rate",
            default=0.04,
        ).value
    )
    resolved_equity_risk_premium = float(
        resolve_assumption(
            valuation_input.assumptions,
            "equity_risk_premium",
            default=0.05,
        ).value
    )
    resolved_cost_of_debt = float(
        resolve_assumption(
            valuation_input.assumptions,
            "cost_of_debt",
            default=resolved_risk_free_rate + 0.015,
        ).value
    )
    resolved_tax_rate = float(
        resolve_assumption(
            valuation_input.assumptions,
            "tax_rate",
            default=0.25,
        ).value
    )

    beta = valuation_input.market.beta or 1.0
    cost_of_equity = resolved_risk_free_rate + beta * resolved_equity_risk_premium
    market_cap = valuation_input.market.market_cap or 0.0
    total_debt = latest.total_debt or 0.0
    capital_base = market_cap + total_debt
    if capital_base > 0:
        resolved_wacc = (
            market_cap / capital_base * cost_of_equity
            + total_debt
            / capital_base
            * resolved_cost_of_debt
            * (1 - resolved_tax_rate)
        )
    else:
        resolved_wacc = cost_of_equity

    if resolved_wacc <= resolved_terminal_growth_rate:
        raise ValueError("wacc must be greater than terminal_growth_rate")

    growth_path = [short_term_growth] * high_growth_years
    for fade_year in range(1, fade_years + 1):
        fade_ratio = fade_year / (fade_years + 1)
        growth_path.append(
            short_term_growth
            + (resolved_terminal_growth_rate - short_term_growth) * fade_ratio
        )

    forecast_cash_flows: list[float] = []
    discounted_cash_flows: list[float] = []
    running_cash_flow = base_fcff
    for year, year_growth in enumerate(growth_path, start=1):
        running_cash_flow = running_cash_flow * (1 + year_growth)
        forecast_cash_flows.append(running_cash_flow)
        discounted_cash_flows.append(running_cash_flow / ((1 + resolved_wacc) ** year))

    projection_years = len(growth_path)
    terminal_cash_flow = forecast_cash_flows[-1] * (1 + resolved_terminal_growth_rate)
    terminal_value = terminal_cash_flow / (
        resolved_wacc - resolved_terminal_growth_rate
    )
    discounted_terminal_value = terminal_value / (
        (1 + resolved_wacc) ** projection_years
    )
    enterprise_value = sum(discounted_cash_flows) + discounted_terminal_value

    cash = latest.cash_and_equivalents or 0.0
    net_debt = total_debt - cash
    equity_value = enterprise_value - net_debt

    shares_outstanding = (
        valuation_input.market.diluted_shares_outstanding
        or valuation_input.market.shares_outstanding
    )
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
            "growth_rate": short_term_growth,
            "terminal_growth_rate": resolved_terminal_growth_rate,
            "wacc": resolved_wacc,
            "projection_years": projection_years,
        },
    )


def calculate_dcf_cases(
    valuation_input: ValuationInput,
    *,
    base_assumptions: dict[str, float | int] | None = None,
) -> dict[str, DCFResult]:
    base = {
        "growth_rate": 0.05,
        "terminal_growth_rate": 0.02,
        "wacc": 0.10,
        "projection_years": 5,
    }
    if base_assumptions:
        base.update(base_assumptions)

    bear = {
        "growth_rate": max(float(base["growth_rate"]) - 0.02, 0.0),
        "terminal_growth_rate": max(float(base["terminal_growth_rate"]) - 0.005, 0.0),
        "wacc": float(base["wacc"]) + 0.01,
        "projection_years": int(base["projection_years"]),
    }
    bull_terminal_growth = float(base["terminal_growth_rate"]) + 0.005
    bull_wacc = max(float(base["wacc"]) - 0.01, bull_terminal_growth + 0.01)
    bull = {
        "growth_rate": float(base["growth_rate"]) + 0.02,
        "terminal_growth_rate": bull_terminal_growth,
        "wacc": bull_wacc,
        "projection_years": int(base["projection_years"]),
    }
    cases = {
        "bear": bear,
        "base": {
            "growth_rate": float(base["growth_rate"]),
            "terminal_growth_rate": float(base["terminal_growth_rate"]),
            "wacc": float(base["wacc"]),
            "projection_years": int(base["projection_years"]),
        },
        "bull": bull,
    }
    return {
        name: calculate_dcf(valuation_input, **case_assumptions)
        for name, case_assumptions in cases.items()
    }


def _calculate_legacy_dcf(
    valuation_input: ValuationInput,
    *,
    growth_rate: float,
    terminal_growth_rate: float,
    wacc: float,
    projection_years: int,
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
