from __future__ import annotations

from .dcf import calculate_dcf, calculate_dcf_cases
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
    sections = [_format_dcf_applicability(valuation_input)]

    if valuation_input.valuation_applicability == "not_applicable":
        multiples = calculate_multiples(valuation_input.market, latest)
        sections.append(
            _format_multiples_summary(multiples, valuation_input.market.currency)
        )
        return "\n\n".join(section.strip() for section in sections if section).strip()

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
        sections.append(f"## DCF Summary\n\nInsufficient data to calculate DCF: {exc}")

    multiples = calculate_multiples(
        valuation_input.market,
        latest,
        assumptions=valuation_input.assumptions,
    )
    sections.append(_format_multiples_summary(multiples, valuation_input.market.currency))
    sections.append(_format_assumptions(valuation_input, config))
    sections.append(_format_dcf_scenarios(valuation_input, config))

    return "\n\n".join(section.strip() for section in sections if section).strip()


def _format_dcf_applicability(valuation_input: ValuationInput) -> str:
    if valuation_input.valuation_applicability == "not_applicable":
        reason = (
            valuation_input.valuation_applicability_reason
            or "This instrument is not suitable for operating-company DCF valuation."
        )
        return "\n".join(
            [
                "## DCF Applicability",
                "",
                "Status: DCF Not Applicable",
                f"Reason: {reason}",
            ]
        )

    return "\n".join(
        [
            "## DCF Applicability",
            "",
            "Status: DCF Applicable",
        ]
    )


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
        "peg_forward_1y": "PEG (1Y Forward)",
        "peg_forward_long_term": "PEG (Long-Term Forward)",
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
        elif key.startswith("peg_"):
            rendered = "N/A" if value is None else f"{value:.2f}x"
        elif value is None:
            rendered = "N/A"
        else:
            rendered = f"{value:.2f}x"
        lines.append(f"| {label} | {rendered} |")
    return "\n".join(lines)


def _format_assumptions(
    valuation_input: ValuationInput,
    config: dict[str, float | int],
) -> str:
    assumption_rows: list[tuple[str, str, str, str, str]] = []
    labels = [
        ("short_term_growth", "Growth Rate"),
        ("terminal_growth_rate", "Terminal Growth Rate"),
        ("risk_free_rate", "Risk-Free Rate"),
        ("equity_risk_premium", "Equity Risk Premium"),
        ("cost_of_debt", "Cost of Debt"),
        ("tax_rate", "Tax Rate"),
        ("beta", "Beta"),
    ]
    for key, label in labels:
        assumption = valuation_input.assumptions.get(key)
        if not assumption or assumption.value is None:
            continue
        value = _format_assumption_value(key, assumption.value)
        assumption_rows.append(
            (
                label,
                value,
                assumption.source,
                assumption.confidence,
                assumption.fallback_reason or "No",
            )
        )

    if not assumption_rows:
        assumption_rows.extend(
            [
                (
                    "Growth Rate",
                    _format_percent(float(config["growth_rate"])),
                    "legacy-config",
                    "medium",
                    "No",
                ),
                (
                    "Terminal Growth Rate",
                    _format_percent(float(config["terminal_growth_rate"])),
                    "legacy-config",
                    "medium",
                    "No",
                ),
                (
                    "WACC",
                    _format_percent(float(config["wacc"])),
                    "legacy-config",
                    "medium",
                    "No",
                ),
                (
                    "Projection Years",
                    str(int(config["projection_years"])),
                    "legacy-config",
                    "medium",
                    "No",
                ),
            ]
        )

    lines = [
        "## Valuation Assumptions",
        "",
        "| Assumption | Value | Source | Confidence | Fallback Used |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label, value, source, confidence, fallback in assumption_rows:
        lines.append(f"| {label} | {value} | {source} | {confidence} | {fallback} |")
    return "\n".join(lines)


def _format_assumption_value(key: str, value: float | int | str | None) -> str:
    if value is None:
        return "N/A"
    if key in {
        "short_term_growth",
        "terminal_growth_rate",
        "risk_free_rate",
        "equity_risk_premium",
        "cost_of_debt",
        "tax_rate",
    }:
        return _format_percent(float(value))
    if key == "beta":
        return f"{float(value):.2f}"
    return str(value)


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


def _format_dcf_scenarios(
    valuation_input: ValuationInput,
    config: dict[str, float | int],
) -> str:
    cases = calculate_dcf_cases(valuation_input, base_assumptions=config)
    lines = [
        "## DCF Scenario Summary",
        "",
        "| Case | Growth Rate | WACC | Terminal Growth | Fair Value / Share |",
        "| --- | --- | --- | --- | --- |",
    ]
    case_labels = {
        "bear": "Bear Case",
        "base": "Base Case",
        "bull": "Bull Case",
    }
    for key in ("bear", "base", "bull"):
        result = cases[key]
        lines.append(
            "| "
            f"{case_labels[key]} | "
            f"{_format_percent(float(result.assumptions['growth_rate']))} | "
            f"{_format_percent(float(result.assumptions['wacc']))} | "
            f"{_format_percent(float(result.assumptions['terminal_growth_rate']))} | "
            f"{_format_currency(result.fair_value_per_share, valuation_input.market.currency)} |"
        )
    return "\n".join(lines)


def _format_currency(value: float | None, currency: str) -> str:
    if value is None:
        return "N/A"
    symbol = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    return f"{symbol}{value:,.2f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"
