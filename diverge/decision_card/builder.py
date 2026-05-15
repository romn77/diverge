from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from diverge.decision_card.parser import (
    extract_decision_card_block,
    extract_highlights_block,
    extract_rating_from_text,
    infer_action_from_rating,
    normalize_action,
    normalize_confidence,
    normalize_rating,
)
from diverge.decision_card.quality import apply_quality_gates
from diverge.decision_card.schema import (
    DecisionCard,
    EvidenceItem,
    PortfolioRating,
)


SOURCE_REPORT_PATHS = [
    "1_analysts/market.md",
    "1_analysts/news.md",
    "1_analysts/fundamentals.md",
    "1_analysts/sentiment.md",
    "2_research/manager.md",
    "3_trading/trader.md",
    "4_risk/debate.md",
    "5_portfolio/decision.md",
]


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _first_non_empty(*values: Any, fallback: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _coerce_string_list(value: Any, *, max_items: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        if len(result) >= max_items:
            break
    return result


def _clean_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _infer_market(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".HK"):
        return "hk"
    if normalized.endswith((".SS", ".SZ")) or (
        normalized.isdigit() and len(normalized) == 6
    ):
        return "cn"
    if normalized:
        return "us"
    return "unknown"


def _normalize_entry_zone(value: Any) -> list[float] | None:
    if not isinstance(value, list):
        return None
    numbers = []
    for item in value:
        if isinstance(item, (int, float)):
            numbers.append(float(item))
    return numbers or None


def _normalize_take_profit(value: Any) -> list[float] | None:
    return _normalize_entry_zone(value)


def _normalize_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_trade_readiness(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper().replace("-", "_").replace(" ", "_")
    if candidate in {
        "READY",
        "WAITING_FOR_TRIGGER",
        "BLOCKED_BY_RISK",
        "DATA_INSUFFICIENT",
        "NO_ACTION_REQUIRED",
    }:
        return candidate
    return None


def _normalize_data_quality_level(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower().replace("-", "_").replace(" ", "_")
    if candidate in {"complete", "partial", "weak", "insufficient"}:
        return candidate
    return None


def _build_why_not(value: Any) -> dict[str, str | None] | None:
    if not isinstance(value, dict):
        return None
    item = {
        "why_not_more_bullish": _clean_optional_string(
            value.get("why_not_more_bullish")
        ),
        "why_not_more_bearish": _clean_optional_string(
            value.get("why_not_more_bearish")
        ),
        "why_not_act_now": _clean_optional_string(value.get("why_not_act_now")),
    }
    return item if any(item.values()) else None


def _build_action_playbook(value: Any) -> dict[str, list[str]] | None:
    if not isinstance(value, dict):
        return None
    item = {
        "do_now": _coerce_string_list(value.get("do_now")),
        "trigger_to_act": _coerce_string_list(value.get("trigger_to_act")),
        "invalidation": _coerce_string_list(value.get("invalidation")),
        "execution_notes": _coerce_string_list(value.get("execution_notes")),
    }
    return item if any(item.values()) else None


def _build_position_guidance(value: Any) -> dict[str, str | None] | None:
    if not isinstance(value, dict):
        return None
    item = {
        "suggested_exposure": _clean_optional_string(value.get("suggested_exposure")),
        "max_exposure": _clean_optional_string(value.get("max_exposure")),
        "sizing_rationale": _clean_optional_string(value.get("sizing_rationale")),
        "risk_budget_note": _clean_optional_string(value.get("risk_budget_note")),
    }
    return item if any(item.values()) else None


def _build_evidence_items(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        point = raw.get("point")
        evidence = raw.get("evidence")
        if not isinstance(point, str) or not point.strip():
            continue
        pillar = raw.get("pillar")
        strength = raw.get("strength")
        confidence = raw.get("confidence")
        item = {
            "pillar": pillar if isinstance(pillar, str) else "portfolio",
            "point": point.strip(),
            "evidence": evidence.strip() if isinstance(evidence, str) else "",
            "strength": strength if isinstance(strength, str) else "medium",
            "source": raw.get("source") if isinstance(raw.get("source"), str) else None,
            "data_date": raw.get("data_date")
            if isinstance(raw.get("data_date"), str)
            else None,
            "confidence": normalize_confidence(confidence)
            if isinstance(confidence, str)
            else None,
            "limitation": raw.get("limitation")
            if isinstance(raw.get("limitation"), str)
            else None,
        }
        try:
            EvidenceItem(**item)
        except ValidationError:
            item["pillar"] = "portfolio"
            item["strength"] = "medium"
            item["confidence"] = None
        items.append(item)
        if len(items) >= 5:
            break
    return items


def _base_payload(
    *,
    symbol: str,
    report_id: str | None,
    analysis_date: str | None,
    rating: PortfolioRating,
    raw_signal: str | None,
) -> dict[str, Any]:
    return {
        "card_version": "1.1",
        "report_id": report_id,
        "symbol": symbol,
        "name": None,
        "market": _infer_market(symbol),
        "analysis_date": analysis_date,
        "generated_at": datetime.now(timezone.utc),
        "rating": rating,
        "action": infer_action_from_rating(rating),
        "confidence": "low",
        "conviction_score": 50,
        "time_horizon": "Not specified",
        "one_line_summary": "No structured decision summary was provided.",
        "thesis": "The final report did not provide a structured decision card.",
        "price_plan": {
            "current_price": None,
            "entry_zone": None,
            "add_condition": None,
            "stop_loss": None,
            "take_profit": None,
            "invalidation": [],
            "risk_reward_note": None,
        },
        "suggested_position": None,
        "key_reasons": [],
        "key_risks": [],
        "catalysts": [],
        "watch_items": [],
        "data_quality_notes": [],
        "source_report_paths": SOURCE_REPORT_PATHS,
        "raw_signal": raw_signal,
        "trade_readiness": None,
        "trade_readiness_reason": None,
        "blocking_items": [],
        "data_quality_level": None,
        "data_quality_summary": None,
        "why_not": None,
        "action_playbook": None,
        "position_guidance": None,
    }


def _payload_from_decision_card_block(
    block: dict[str, Any],
    *,
    symbol: str,
    report_id: str | None,
    analysis_date: str | None,
    raw_signal: str | None,
) -> dict[str, Any]:
    rating = normalize_rating(
        str(block.get("rating")) if block.get("rating") is not None else None
    )
    payload = _base_payload(
        symbol=symbol,
        report_id=report_id,
        analysis_date=analysis_date,
        rating=rating,
        raw_signal=raw_signal,
    )
    price_plan = (
        block.get("price_plan") if isinstance(block.get("price_plan"), dict) else {}
    )
    payload.update(
        {
            "card_version": block.get("card_version") or "1.1",
            "name": block.get("name") if isinstance(block.get("name"), str) else None,
            "market": block.get("market")
            if block.get("market") in {"cn", "us", "hk", "unknown"}
            else payload["market"],
            "action": normalize_action(
                str(block.get("action")) if block.get("action") is not None else None,
                rating,
            ),
            "confidence": normalize_confidence(
                str(block.get("confidence"))
                if block.get("confidence") is not None
                else None
            ),
            "conviction_score": block.get("conviction_score")
            if isinstance(block.get("conviction_score"), int)
            else 50,
            "time_horizon": _first_non_empty(
                block.get("time_horizon"), fallback="Not specified"
            ),
            "one_line_summary": _first_non_empty(
                block.get("one_line_summary"),
                block.get("summary"),
                fallback=payload["one_line_summary"],
            ),
            "thesis": _first_non_empty(block.get("thesis"), fallback=payload["thesis"]),
            "price_plan": {
                "current_price": _normalize_float(price_plan.get("current_price")),
                "entry_zone": _normalize_entry_zone(price_plan.get("entry_zone")),
                "add_condition": price_plan.get("add_condition")
                if isinstance(price_plan.get("add_condition"), str)
                else None,
                "stop_loss": _normalize_float(price_plan.get("stop_loss")),
                "take_profit": _normalize_take_profit(price_plan.get("take_profit")),
                "invalidation": _coerce_string_list(price_plan.get("invalidation")),
                "risk_reward_note": price_plan.get("risk_reward_note")
                if isinstance(price_plan.get("risk_reward_note"), str)
                else None,
            },
            "suggested_position": block.get("suggested_position")
            if isinstance(block.get("suggested_position"), str)
            else None,
            "key_reasons": _build_evidence_items(block.get("key_reasons")),
            "key_risks": _coerce_string_list(block.get("key_risks")),
            "catalysts": _coerce_string_list(block.get("catalysts")),
            "watch_items": _coerce_string_list(block.get("watch_items")),
            "data_quality_notes": _coerce_string_list(
                block.get("data_quality_notes"), max_items=20
            ),
            "trade_readiness": _normalize_trade_readiness(block.get("trade_readiness")),
            "trade_readiness_reason": _clean_optional_string(
                block.get("trade_readiness_reason")
            ),
            "blocking_items": _coerce_string_list(block.get("blocking_items")),
            "data_quality_level": _normalize_data_quality_level(
                block.get("data_quality_level")
            ),
            "data_quality_summary": _clean_optional_string(
                block.get("data_quality_summary")
            ),
            "why_not": _build_why_not(block.get("why_not")),
            "action_playbook": _build_action_playbook(block.get("action_playbook")),
            "position_guidance": _build_position_guidance(
                block.get("position_guidance")
            ),
        }
    )
    return payload


def _payload_from_highlights_block(
    block: dict[str, Any],
    *,
    symbol: str,
    report_id: str | None,
    analysis_date: str | None,
    raw_signal: str | None,
) -> dict[str, Any]:
    rating = normalize_rating(
        str(block.get("final_decision") or block.get("signal"))
        if (block.get("final_decision") or block.get("signal")) is not None
        else None
    )
    payload = _base_payload(
        symbol=symbol,
        report_id=report_id,
        analysis_date=analysis_date,
        rating=rating,
        raw_signal=raw_signal,
    )
    decision_basis = block.get("decision_basis")
    payload.update(
        {
            "confidence": normalize_confidence(
                str(block.get("signal_confidence"))
                if block.get("signal_confidence") is not None
                else None
            ),
            "one_line_summary": _first_non_empty(
                block.get("summary"), fallback=payload["one_line_summary"]
            ),
            "thesis": _first_non_empty(
                decision_basis, block.get("summary"), fallback=payload["thesis"]
            ),
            "key_reasons": _build_evidence_items(
                [
                    {
                        "pillar": "portfolio",
                        "point": "Portfolio manager final basis",
                        "evidence": decision_basis,
                        "strength": "medium",
                    }
                ]
                if isinstance(decision_basis, str) and decision_basis.strip()
                else []
            ),
            "key_risks": _coerce_string_list(block.get("risk_warnings")),
            "data_quality_notes": [
                "DecisionCard was derived from legacy json-highlights because json-decision-card was unavailable."
            ],
        }
    )
    strategic_actions = block.get("strategic_actions")
    if isinstance(strategic_actions, list) and strategic_actions:
        first_action = strategic_actions[0]
        if isinstance(first_action, dict) and isinstance(
            first_action.get("action"), str
        ):
            payload["price_plan"]["add_condition"] = first_action["action"]
    return payload


def build_fallback_decision_card(
    *,
    symbol: str,
    report_id: str | None = None,
    analysis_date: str | None = None,
    rating: PortfolioRating = "HOLD",
    raw_signal: str | None = None,
    error: str | None = None,
    output_language: str | None = None,
) -> DecisionCard:
    payload = _base_payload(
        symbol=symbol,
        report_id=report_id,
        analysis_date=analysis_date,
        rating=rating,
        raw_signal=raw_signal,
    )
    payload["action"] = "NO_ACTION"
    payload["confidence"] = "low"
    payload["one_line_summary"] = (
        "Structured decision card generation fell back to a low-confidence placeholder."
    )
    payload["thesis"] = (
        "The full markdown report was saved, but Diverge could not derive a complete structured decision card."
    )
    payload["data_quality_notes"] = [
        "Fallback card generated because structured decision data was unavailable."
    ]
    if error:
        payload["data_quality_notes"].append(f"Fallback reason: {error}")
    return apply_quality_gates(DecisionCard(**payload), output_language=output_language)


def _structured_card_from_state(final_state: dict) -> dict[str, Any] | None:
    value = final_state.get("portfolio_decision_card")
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else None
    return None


def build_decision_card(
    *,
    final_state: dict,
    symbol: str,
    report_id: str | None = None,
    analysis_date: str | None = None,
    output_language: str | None = None,
) -> DecisionCard:
    final_decision = _as_text(final_state.get("final_trade_decision"))
    raw_signal = final_decision or None

    structured_card = _structured_card_from_state(final_state)
    if structured_card:
        try:
            payload = _payload_from_decision_card_block(
                structured_card,
                symbol=symbol,
                report_id=report_id,
                analysis_date=analysis_date,
                raw_signal=raw_signal,
            )
            card = DecisionCard(**payload)
            card.data_quality_notes.append(
                "DecisionCard was sourced from ADK output_schema state."
            )
            return apply_quality_gates(card, output_language=output_language)
        except ValidationError:
            pass

    decision_card_block = extract_decision_card_block(final_decision)
    if decision_card_block:
        payload = _payload_from_decision_card_block(
            decision_card_block,
            symbol=symbol,
            report_id=report_id,
            analysis_date=analysis_date,
            raw_signal=raw_signal,
        )
        return apply_quality_gates(
            DecisionCard(**payload), output_language=output_language
        )

    highlights_block = extract_highlights_block(final_decision)
    if highlights_block:
        payload = _payload_from_highlights_block(
            highlights_block,
            symbol=symbol,
            report_id=report_id,
            analysis_date=analysis_date,
            raw_signal=raw_signal,
        )
        return apply_quality_gates(
            DecisionCard(**payload), output_language=output_language
        )

    rating = extract_rating_from_text(final_decision)
    if rating:
        fallback = build_fallback_decision_card(
            symbol=symbol,
            report_id=report_id,
            analysis_date=analysis_date,
            rating=rating,
            raw_signal=raw_signal,
            output_language=output_language,
        )
        fallback.action = infer_action_from_rating(rating)
        fallback.one_line_summary = f"Final report text indicates a {rating} rating, but no structured decision card was provided."
        fallback.thesis = _first_non_empty(
            final_decision[:600], fallback=fallback.thesis
        )
        fallback.data_quality_notes.append(
            "DecisionCard was derived from unstructured final decision text."
        )
        return apply_quality_gates(fallback, output_language=output_language)

    return build_fallback_decision_card(
        symbol=symbol,
        report_id=report_id,
        analysis_date=analysis_date,
        raw_signal=raw_signal,
        output_language=output_language,
    )
