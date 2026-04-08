from __future__ import annotations

from .dcf import DCFResult, calculate_dcf
from .schemas import ValuationInput


def run_dcf_sensitivity(
    valuation_input: ValuationInput,
    *,
    growth_rates: list[float],
    waccs: list[float],
    terminal_growth_rate: float,
    projection_years: int = 5,
) -> dict[tuple[float, float], DCFResult]:
    results: dict[tuple[float, float], DCFResult] = {}

    for growth_rate in growth_rates:
        for wacc in waccs:
            results[(growth_rate, wacc)] = calculate_dcf(
                valuation_input,
                growth_rate=growth_rate,
                terminal_growth_rate=terminal_growth_rate,
                wacc=wacc,
                projection_years=projection_years,
            )

    return results
