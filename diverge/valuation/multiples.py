from __future__ import annotations

from .schemas import AssumptionValue, FinancialSnapshot, MarketContext


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def calculate_multiples(
    market: MarketContext,
    snapshot: FinancialSnapshot,
    assumptions: dict[str, AssumptionValue] | None = None,
) -> dict[str, float | None]:
    market_cap = market.market_cap
    enterprise_value = market.enterprise_value

    if (
        market_cap is None
        and market.share_price is not None
        and market.shares_outstanding
    ):
        market_cap = market.share_price * market.shares_outstanding

    if enterprise_value is None:
        total_debt = snapshot.total_debt or 0.0
        cash = snapshot.cash_and_equivalents or 0.0
        if market_cap is not None:
            enterprise_value = market_cap + total_debt - cash

    multiples = {
        "p_e": _safe_divide(market_cap, snapshot.net_income),
        "p_b": _safe_divide(market_cap, snapshot.shareholders_equity),
        "ev_ebitda": _safe_divide(enterprise_value, snapshot.ebitda),
        "ev_sales": _safe_divide(enterprise_value, snapshot.revenue),
        "fcf_yield": _safe_divide(snapshot.free_cash_flow, market_cap),
    }
    assumptions = assumptions or {}

    forward_pe_assumption = assumptions.get("forward_pe")
    eps_growth_1y_assumption = assumptions.get("eps_growth_1y")
    eps_growth_long_term_assumption = assumptions.get("eps_growth_long_term")

    forward_pe = _safe_divide(
        forward_pe_assumption.value if forward_pe_assumption else None,
        1,
    )
    eps_growth_1y = _safe_divide(
        eps_growth_1y_assumption.value if eps_growth_1y_assumption else None,
        1,
    )
    eps_growth_long_term = _safe_divide(
        eps_growth_long_term_assumption.value
        if eps_growth_long_term_assumption
        else None,
        1,
    )

    multiples["peg_forward_1y"] = _safe_divide(
        forward_pe,
        eps_growth_1y * 100 if eps_growth_1y and eps_growth_1y > 0 else None,
    )
    multiples["peg_forward_long_term"] = _safe_divide(
        forward_pe,
        eps_growth_long_term * 100
        if eps_growth_long_term and eps_growth_long_term > 0
        else None,
    )
    return multiples
