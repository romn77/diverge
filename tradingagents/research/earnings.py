from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping


@dataclass(slots=True)
class EarningsWorkflowContext:
    mode: str
    prompt_instruction: str
    report_section: str


def build_earnings_workflow_context(
    *,
    trade_date: str,
    ticker: str,
    earnings_event: Mapping[str, object] | None = None,
) -> EarningsWorkflowContext:
    trade_day = _parse_date(trade_date)
    event = dict(earnings_event or {})
    earnings_day = _parse_date(event.get("earnings_date"))
    fiscal_period = _string_or_none(event.get("fiscal_period")) or "upcoming period"

    if earnings_day and trade_day and trade_day < earnings_day:
        consensus_revenue = _string_or_none(event.get("consensus_revenue")) or "N/A"
        consensus_eps = _string_or_none(event.get("consensus_eps")) or "N/A"
        return EarningsWorkflowContext(
            mode="preview",
            prompt_instruction="\n".join(
                [
                    "Earnings mode: preview",
                    "Frame the analysis as a pre-earnings setup. Focus on expectations, scenario framing, watch items, and what could change sentiment after the print.",
                    f"Upcoming earnings date: {earnings_day.isoformat()}",
                    f"Fiscal period: {fiscal_period}",
                    f"Consensus revenue: {consensus_revenue}",
                    f"Consensus EPS: {consensus_eps}",
                ]
            ),
            report_section="\n".join(
                [
                    "## Earnings Preview Focus",
                    "",
                    f"- Upcoming report: {earnings_day.isoformat()} ({fiscal_period})",
                    f"- Consensus revenue: {consensus_revenue}",
                    f"- Consensus EPS: {consensus_eps}",
                    "- Primary watch items: guidance tone, demand durability, and management commentary.",
                ]
            ),
        )

    if earnings_day and trade_day and trade_day >= earnings_day:
        reported_revenue = _string_or_none(event.get("reported_revenue")) or "N/A"
        reported_eps = _string_or_none(event.get("reported_eps")) or "N/A"
        guidance_change = _string_or_none(event.get("guidance_change")) or "No explicit guidance update supplied."
        return EarningsWorkflowContext(
            mode="review",
            prompt_instruction="\n".join(
                [
                    "Earnings mode: review",
                    "Compare reported results, guidance, and quality of earnings versus what the market likely expected. Highlight beats or misses, guidance changes, and what matters next.",
                    f"Reported earnings date: {earnings_day.isoformat()}",
                    f"Fiscal period: {fiscal_period}",
                    f"Reported revenue: {reported_revenue}",
                    f"Reported EPS: {reported_eps}",
                    f"Guidance change: {guidance_change}",
                ]
            ),
            report_section="\n".join(
                [
                    "## Post-Earnings Review Focus",
                    "",
                    f"- Reported period: {fiscal_period}",
                    f"- Reported revenue: {reported_revenue}",
                    f"- Reported EPS: {reported_eps}",
                    f"- Guidance change: {guidance_change}",
                ]
            ),
        )

    return EarningsWorkflowContext(
        mode="general",
        prompt_instruction="\n".join(
            [
                "Earnings mode: general",
                "No earnings-specific event data is available.",
                "Keep the analysis earnings-aware, but do not invent a preview or post-earnings narrative.",
            ]
        ),
        report_section="\n".join(
            [
                "## Earnings Context",
                "",
                f"- No explicit earnings event payload was supplied for {ticker}.",
                "- Treat earnings as a background catalyst rather than the primary frame.",
            ]
        ),
    )


def inject_earnings_section(report: str, earnings_section: str) -> str:
    base_report = (report or "").strip()
    additions = (earnings_section or "").strip()
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


def _parse_date(value: object) -> date | None:
    text = _string_or_none(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
