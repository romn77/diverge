from __future__ import annotations

from .dcf import calculate_dcf
from .multiples import calculate_multiples
from .schemas import ValuationInput
from .sensitivity import run_dcf_sensitivity


DEFAULT_ASSUMPTIONS = {
    "growth_rate": 0.05,
    "terminal_growth_rate": 0.02,
    "wacc": 0.10,
    "projection_years": 5,
}


def format_valuation_sections(
    valuation_input: ValuationInput,
    *,
    assumptions: dict[str, float | int] | None = None,
) -> str:
    config = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    latest = valuation_input.latest_financial
    sections = []

    try:
        dcf_result = calculate_dcf(
            valuation_input,
            growth_rate=float(config["growth_rate"]),
            terminal_growth_rate=float(config["terminal_growth_rate"]),
            wacc=float(config["wacc"]),
            projection_years=int(config["projection_years"]),
        )
        sections.append(
            "\n".join(
                [
                    "## DCF Summary",
                    "",
                    "| Metric | Value |",
                    "| --- | --- |",
                    f"| Enterprise Value | {_format_currency(dcf_result.enterprise_value, valuation_input.market.currency)} |",
                    f"| Equity Value | {_format_currency(dcf_result.equity_value, valuation_input.market.currency)} |",
                    f"| Net Debt | {_format_currency(dcf_result.net_debt, valuation_input.market.currency)} |",
                    f"| Fair Value / Share | {_format_currency(dcf_result.fair_value_per_share, valuation_input.market.currency)} |",
                ]
            )
        )
        sections.append(
            _format_sensitivity_summary(
                valuation_input,
                terminal_growth_rate=float(config["terminal_growth_rate"]),
                projection_years=int(config["projection_years"]),
            )
        )
    except ValueError as exc:
        sections.append(f"## DCF Summary\n\nUnable to calculate DCF: {exc}")

    multiples = calculate_multiples(valuation_input.market, latest)
    sections.append(_format_multiples_summary(multiples, valuation_input.market.currency))
    sections.append(_format_assumptions(config))

    return "\n\n".join(section.strip() for section in sections if section).strip()


def inject_valuation_sections(report: str, valuation_sections: str) -> str:
    base_report = (report or "").strip()
    additions = valuation_sections.strip()
    if not additions:
        return base_report
    if not base_report:
        return additions

    highlights_index = base_report.rfind("```json-highlights")
    if highlights_index == -1:
        return f"{base_report}\n\n{additions}"

    before = base_report[:highlights_index].rstrip()
    after = base_report[highlights_index:].lstrip()
    return f"{before}\n\n{additions}\n\n{after}".strip()


def _format_multiples_summary(
    multiples: dict[str, float | None],
    currency: str,
) -> str:
    labels = {
        "p_e": "P/E",
        "p_b": "P/B",
        "ev_ebitda": "EV/EBITDA",
        "ev_sales": "EV/Sales",
        "fcf_yield": "FCF Yield",
    }
    lines = [
        "## Multiples Summary",
        "",
        "| Multiple | Value |",
        "| --- | --- |",
    ]
    for key, label in labels.items():
        value = multiples.get(key)
        if key == "fcf_yield":
            rendered = _format_percent(value)
        elif value is None:
            rendered = "N/A"
        else:
            rendered = f"{value:.2f}x"
        lines.append(f"| {label} | {rendered} |")
    return "\n".join(lines)


def _format_assumptions(assumptions: dict[str, float | int]) -> str:
    return "\n".join(
        [
            "## Valuation Assumptions",
            "",
            "| Assumption | Value |",
            "| --- | --- |",
            f"| Growth Rate | {_format_percent(float(assumptions['growth_rate']))} |",
            f"| Terminal Growth Rate | {_format_percent(float(assumptions['terminal_growth_rate']))} |",
            f"| WACC | {_format_percent(float(assumptions['wacc']))} |",
            f"| Projection Years | {int(assumptions['projection_years'])} |",
        ]
    )


def _format_sensitivity_summary(
    valuation_input: ValuationInput,
    *,
    terminal_growth_rate: float,
    projection_years: int,
) -> str:
    sensitivity = run_dcf_sensitivity(
        valuation_input,
        growth_rates=[0.03, 0.05, 0.07],
        waccs=[0.09, 0.10, 0.11],
        terminal_growth_rate=terminal_growth_rate,
        projection_years=projection_years,
    )
    fair_values = [
        result.fair_value_per_share
        for result in sensitivity.values()
        if result.fair_value_per_share is not None
    ]
    if not fair_values:
        return "## Sensitivity Summary\n\nFair value per share is unavailable because shares outstanding is missing."

    return "\n".join(
        [
            "## Sensitivity Summary",
            "",
            f"Fair value per share range: {_format_currency(min(fair_values), valuation_input.market.currency)} to {_format_currency(max(fair_values), valuation_input.market.currency)}.",
        ]
    )


def _format_currency(value: float | None, currency: str) -> str:
    if value is None:
        return "N/A"
    symbol = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    return f"{symbol}{value:,.2f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"
