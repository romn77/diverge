from __future__ import annotations

from diverge.market_brief.schema import PremarketBrief


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items if item]


def render_market_brief_markdown(brief: PremarketBrief) -> str:
    lines = [
        "# Trading Analysis Report: MARKET_BRIEF",
        "",
        f"Generated: {brief.information_cutoff_at[:10]} {brief.information_cutoff_at[11:19]}",
        "",
        f"# {brief.title}",
        "",
        brief.summary,
        "",
        "## Market Calendar",
    ]
    for item in brief.market_calendar:
        countdown = (
            f", opens in {item.minutes_to_open} min"
            if item.minutes_to_open is not None
            else ""
        )
        lines.append(
            f"- {item.label}: {item.local_date}, trading day {item.trading_day or 'n/a'}, "
            f"{item.session_status}{countdown}"
        )

    lines.extend(["", "## Overnight Moves"])
    lines.extend(
        _bullet_lines(brief.overnight_moves) or ["- No market snapshot available."]
    )

    lines.extend(["", "## Today Variables"])
    lines.extend(_bullet_lines(brief.today_variables))

    lines.extend(["", "## Main Themes"])
    for theme in brief.main_themes:
        lines.extend([f"### {theme.title}", "", theme.summary])
        if theme.evidence:
            lines.extend(["", "Evidence:"])
            lines.extend(_bullet_lines(theme.evidence))
        if theme.validation_signals:
            lines.extend(["", "Validation:"])
            lines.extend(_bullet_lines(theme.validation_signals))
        if theme.invalidation_signals:
            lines.extend(["", "Invalidation:"])
            lines.extend(_bullet_lines(theme.invalidation_signals))
        lines.append("")

    lines.extend(["## Ambush Directions"])
    for direction in brief.ambush_directions:
        lines.extend([f"### {direction.title}", "", direction.summary, ""])
        if direction.validation_signals:
            lines.extend(_bullet_lines(direction.validation_signals))
            lines.append("")

    lines.extend(["## Risks"])
    for risk in brief.risks:
        suffix = f" Mitigation: {risk.mitigation}" if risk.mitigation else ""
        lines.append(f"- [{risk.severity}] {risk.risk}{suffix}")

    lines.extend(["", "## Opening Validation Signals"])
    for signal in brief.opening_validation_signals:
        suffix = f" - {signal.why_it_matters}" if signal.why_it_matters else ""
        lines.append(f"- {signal.signal}{suffix}")

    lines.extend(["", "## Sources"])
    if brief.sources:
        for index, source in enumerate(brief.sources, start=1):
            label = source.source or source.provider or "source"
            lines.append(f"{index}. [{source.title}]({source.url}) - {label}")
    else:
        lines.append("- No source links collected.")

    if brief.quality_warnings:
        lines.extend(["", "## Quality Warnings"])
        lines.extend(_bullet_lines(brief.quality_warnings))

    return "\n".join(lines).rstrip() + "\n"
