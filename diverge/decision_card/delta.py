from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from diverge.decision_card.schema import DecisionCard


class FieldDelta(BaseModel):
    previous: str | int | None = None
    current: str | int | None = None
    changed: bool = False


class DecisionDelta(BaseModel):
    previous_report_id: str | None = None
    current_report_id: str
    symbol: str
    summary: str
    rating: FieldDelta
    action: FieldDelta
    conviction_score: FieldDelta
    confidence: FieldDelta
    trade_readiness: FieldDelta | None = None


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_decision_card(report_dir: Path) -> DecisionCard | None:
    path = report_dir / "artifacts" / "decision_card.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return DecisionCard(**payload)
    except Exception:
        return None


def find_previous_decision_card(
    *,
    current_card: DecisionCard,
    candidate_report_dirs: list[Path],
    current_report_id: str,
) -> DecisionCard | None:
    current_symbol = current_card.symbol.strip().upper()
    current_generated_at = _parse_dt(current_card.generated_at)
    previous_cards: list[DecisionCard] = []

    for report_dir in candidate_report_dirs:
        if report_dir.name == current_report_id:
            continue
        card = load_decision_card(report_dir)
        if card is None or card.symbol.strip().upper() != current_symbol:
            continue
        if current_generated_at is not None:
            card_generated_at = _parse_dt(card.generated_at)
            if card_generated_at is not None and card_generated_at >= current_generated_at:
                continue
        previous_cards.append(card)

    previous_cards.sort(
        key=lambda card: (
            _parse_dt(card.generated_at) or datetime.min,
            card.report_id or "",
        ),
        reverse=True,
    )
    return previous_cards[0] if previous_cards else None


def _field_delta(previous: str | int | None, current: str | int | None) -> FieldDelta:
    return FieldDelta(previous=previous, current=current, changed=previous != current)


def _summary(
    *,
    changed_count: int,
    output_language: str | None,
) -> str:
    if (output_language or "en").strip().lower() == "cn":
        if changed_count:
            return "相比上次可见分析，最终裁决已有变化。"
        return "相比上次可见分析，核心裁决没有明显变化。"
    if changed_count:
        return "The final ruling changed since the last visible analysis."
    return "No major verdict change since the last visible analysis."


def build_decision_delta(
    *,
    current_card: DecisionCard,
    previous_card: DecisionCard,
    current_report_id: str,
    output_language: str | None = None,
) -> DecisionDelta:
    rating = _field_delta(previous_card.rating, current_card.rating)
    action = _field_delta(previous_card.action, current_card.action)
    conviction_score = _field_delta(
        previous_card.conviction_score, current_card.conviction_score
    )
    confidence = _field_delta(previous_card.confidence, current_card.confidence)
    trade_readiness = None
    if previous_card.trade_readiness is not None or current_card.trade_readiness is not None:
        trade_readiness = _field_delta(
            previous_card.trade_readiness, current_card.trade_readiness
        )
    changed_count = sum(
        delta.changed
        for delta in (
            rating,
            action,
            conviction_score,
            confidence,
            trade_readiness or FieldDelta(),
        )
    )
    return DecisionDelta(
        previous_report_id=previous_card.report_id,
        current_report_id=current_report_id,
        symbol=current_card.symbol,
        summary=_summary(
            changed_count=changed_count,
            output_language=output_language,
        ),
        rating=rating,
        action=action,
        conviction_score=conviction_score,
        confidence=confidence,
        trade_readiness=trade_readiness,
    )


def save_decision_delta(delta: DecisionDelta, report_dir: Path) -> Path:
    artifacts_dir = report_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "decision_delta.json"
    path.write_text(delta.model_dump_json(indent=2), encoding="utf-8")
    return path
