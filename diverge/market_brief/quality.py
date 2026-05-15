from __future__ import annotations

from diverge.market_brief.schema import PremarketBrief


def apply_quality_gate(brief: PremarketBrief) -> PremarketBrief:
    warnings = list(brief.quality_warnings)
    if not brief.information_cutoff_at:
        warnings.append("Missing information cutoff timestamp.")
    if not brief.markets:
        warnings.append("No markets were included.")
    if not brief.market_calendar:
        warnings.append("Missing market calendar context.")
    if not any(snapshot.status == "ok" for snapshot in brief.market_snapshots):
        warnings.append("No live index snapshots were available.")
    if not brief.sources:
        warnings.append("No source links were collected from Web Search.")
    if not brief.main_themes:
        warnings.append("No main market themes were generated.")
    if not brief.opening_validation_signals:
        warnings.append("No opening validation signals were generated.")

    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)

    if not deduped:
        quality_level = "high"
    elif len(deduped) <= 2 and brief.sources:
        quality_level = "medium"
    else:
        quality_level = "low"

    return brief.model_copy(
        update={
            "quality_warnings": deduped,
            "data_quality_level": quality_level,
        }
    )
