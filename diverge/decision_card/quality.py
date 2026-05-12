from __future__ import annotations

from diverge.decision_card.enrichment import (
    apply_decision_intelligence,
    ensure_position_guidance,
    validate_trade_readiness,
)
from diverge.decision_card.schema import DecisionCard


def validate_rating_action_consistency(card: DecisionCard) -> DecisionCard:
    if card.rating == "SELL" and card.action in {"OPEN", "ADD"}:
        card.action = "EXIT"
        card.data_quality_notes.append(
            "Inconsistent rating/action corrected: SELL cannot map to OPEN or ADD."
        )

    if card.rating == "UNDERWEIGHT" and card.action == "OPEN":
        card.action = "TRIM"
        card.data_quality_notes.append(
            "Inconsistent rating/action corrected: UNDERWEIGHT cannot map to OPEN."
        )

    if card.rating == "BUY" and card.action == "EXIT":
        card.action = "WATCH"
        card.data_quality_notes.append(
            "Inconsistent rating/action corrected: BUY cannot map to EXIT."
        )

    return card


def validate_price_plan(card: DecisionCard) -> DecisionCard:
    plan = card.price_plan

    if plan.current_price is None:
        if plan.stop_loss is not None or plan.take_profit is not None:
            plan.stop_loss = None
            plan.take_profit = None
            card.data_quality_notes.append(
                "Price levels were removed because current_price is unavailable."
            )

    if card.rating in {"BUY", "OVERWEIGHT"}:
        if not plan.add_condition and not plan.entry_zone:
            card.data_quality_notes.append(
                "BUY/OVERWEIGHT card lacks entry or add condition."
            )
        if not plan.invalidation:
            card.data_quality_notes.append(
                "BUY/OVERWEIGHT card lacks invalidation condition."
            )

    if card.action == "WATCH" and not card.watch_items and not plan.add_condition:
        card.data_quality_notes.append("WATCH card lacks watch_items or add_condition.")

    return card


def validate_evidence_and_risk(card: DecisionCard) -> DecisionCard:
    if not card.key_reasons:
        card.data_quality_notes.append("Decision card lacks key reasons.")
    else:
        for reason in card.key_reasons:
            if not reason.evidence.strip():
                card.data_quality_notes.append(
                    "A key reason is missing concrete evidence."
                )
                break

    if card.rating in {"BUY", "OVERWEIGHT"} and not card.key_risks:
        card.data_quality_notes.append("BUY/OVERWEIGHT card lacks key risks.")

    if not card.one_line_summary.strip():
        card.one_line_summary = "No structured decision summary was provided."
        card.data_quality_notes.append("Missing one_line_summary was replaced.")

    if not card.thesis.strip():
        card.thesis = card.one_line_summary
        card.data_quality_notes.append("Missing thesis was replaced with the summary.")

    return card


def downgrade_confidence_for_quality(card: DecisionCard) -> DecisionCard:
    issue_count = len(card.data_quality_notes)
    if issue_count >= 3:
        card.confidence = "low"
    elif issue_count >= 1 and card.confidence == "high":
        card.confidence = "medium"
    return card


def calibrate_conviction_score(card: DecisionCard) -> DecisionCard:
    card.conviction_score = max(0, min(100, int(card.conviction_score)))
    return card


def apply_quality_gates(
    card: DecisionCard, *, output_language: str | None = None
) -> DecisionCard:
    card = validate_rating_action_consistency(card)
    card = validate_price_plan(card)
    card = validate_evidence_and_risk(card)
    card = apply_decision_intelligence(card, output_language=output_language)
    card = downgrade_confidence_for_quality(card)
    card = calibrate_conviction_score(card)
    card = validate_trade_readiness(card, output_language=output_language)
    card = ensure_position_guidance(card, output_language=output_language)
    return card
