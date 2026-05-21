from __future__ import annotations

import json
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
    OpportunityEvidence,
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


def _is_cn(output_language: str | None) -> bool:
    return (output_language or "en").strip().lower() == "cn"


def _fallback_summary(*, output_language: str | None) -> str:
    if _is_cn(output_language):
        return "结构化决策卡生成失败，当前为低置信度兜底卡片。"
    return (
        "Structured decision card generation fell back to a low-confidence placeholder."
    )


def _fallback_thesis(*, output_language: str | None) -> str:
    if _is_cn(output_language):
        return "完整报告已保存，但 Diverge 无法提取完整结构化决策卡。"
    return (
        "The full markdown report was saved, but Diverge could not derive a complete "
        "structured decision card."
    )


def _unstructured_rating_summary(
    *, rating: PortfolioRating, output_language: str | None
) -> str:
    if _is_cn(output_language):
        return f"最终报告文本给出了 {rating} 评级，但未提供结构化决策卡。"
    return (
        f"Final report text indicates a {rating} rating, "
        "but no structured decision card was provided."
    )


def _coerce_string_list(value: Any, *, max_items: int = 5) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
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


def _compact_summary(value: Any, *, max_chars: int = 180) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    for marker in ("。", ".", "！", "!", "？", "?"):
        marker_index = cleaned.find(marker)
        if 0 < marker_index < max_chars:
            return cleaned[: marker_index + 1]
    if len(cleaned) > max_chars:
        return f"{cleaned[:max_chars].rstrip()}..."
    return cleaned


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
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return {
                "suggested_exposure": cleaned,
                "max_exposure": None,
                "sizing_rationale": None,
                "risk_budget_note": None,
            }
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
        if isinstance(raw, str):
            evidence = raw.strip()
            if not evidence:
                continue
            item = {
                "pillar": "portfolio",
                "point": _compact_summary(evidence, max_chars=72)
                or "Portfolio evidence",
                "evidence": evidence,
                "strength": "medium",
                "source": None,
                "data_date": None,
                "confidence": None,
                "limitation": None,
            }
            items.append(item)
            if len(items) >= 5:
                break
            continue
        if not isinstance(raw, dict):
            continue
        point = raw.get("point") or raw.get("claim")
        evidence = raw.get("evidence") or raw.get("claim")
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
        "card_version": "1.2",
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
    thesis = _first_non_empty(
        block.get("thesis"),
        block.get("decision_basis"),
        block.get("decision_report"),
        fallback=payload["thesis"],
    )
    summary_fallback = (
        _compact_summary(thesis)
        if thesis != payload["thesis"]
        else payload["one_line_summary"]
    )
    key_risks = _coerce_string_list(block.get("key_risks"))
    risk_summary = _clean_optional_string(block.get("risk_summary"))
    if not key_risks and risk_summary:
        key_risks = [risk_summary]
    suggested_position = (
        block.get("suggested_position")
        if isinstance(block.get("suggested_position"), str)
        else _clean_optional_string(block.get("position_guidance"))
    )
    payload.update(
        {
            "card_version": block.get("card_version") or "1.2",
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
                fallback=summary_fallback,
            ),
            "thesis": thesis,
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
            "suggested_position": suggested_position,
            "key_reasons": _build_evidence_items(
                block.get("key_reasons") or block.get("evidence_blocks")
            ),
            "key_risks": key_risks,
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


def _extract_raw_json_decision_card(markdown: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(markdown or "")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    block = payload.get("decision_card")
    if isinstance(block, dict):
        decision_block = dict(block)
        decision_report = _clean_optional_string(payload.get("decision_report"))
        if decision_report:
            decision_block.setdefault("decision_report", decision_report)
        return decision_block
    if payload.get("rating") is not None:
        return payload
    return None


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
    payload["one_line_summary"] = _fallback_summary(output_language=output_language)
    payload["thesis"] = _fallback_thesis(output_language=output_language)
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


def _opportunity_evidence_from_state(final_state: dict) -> OpportunityEvidence | None:
    context = final_state.get("opportunity_context")
    if not isinstance(context, dict) or not context:
        return None
    return OpportunityEvidence(
        trigger=_clean_optional_string(context.get("trigger") or context.get("source")),
        theme_id=_clean_optional_string(context.get("theme_id")),
        theme_name=_clean_optional_string(context.get("theme_name")),
        candidate_type=_clean_optional_string(context.get("candidate_type")),
        source_run_id=_clean_optional_string(context.get("source_run_id")),
        backtest_summary=context.get("backtest_summary")
        if isinstance(context.get("backtest_summary"), dict)
        else None,
        risk_flags=_coerce_string_list(context.get("risk_flags")),
    )


def _attach_opportunity_evidence(card: DecisionCard, final_state: dict) -> DecisionCard:
    evidence = _opportunity_evidence_from_state(final_state)
    if evidence is None:
        return card
    card.opportunity_evidence = evidence
    sample_size = None
    if isinstance(evidence.backtest_summary, dict):
        sample_size = evidence.backtest_summary.get("sample_size")
    if sample_size:
        validation_note = f"Opportunity Radar validation sample size: {sample_size}."
    else:
        validation_note = "Opportunity Radar historical validation was unavailable or sample size was insufficient."
        if validation_note not in card.data_quality_notes:
            card.data_quality_notes.append(validation_note)
    point = evidence.trigger or "Opportunity Radar trigger"
    if len(card.key_reasons) < 5:
        card.key_reasons.append(
            EvidenceItem(
                pillar="opportunity",
                point=point,
                evidence=validation_note,
                strength="medium" if sample_size else "weak",
                source="Opportunity Radar",
                data_date=None,
                confidence="medium" if sample_size else "low",
                limitation=None if sample_size else "insufficient_sample",
            )
        )
    return card


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
            return _attach_opportunity_evidence(
                apply_quality_gates(card, output_language=output_language),
                final_state,
            )
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
        return _attach_opportunity_evidence(
            apply_quality_gates(
                DecisionCard(**payload), output_language=output_language
            ),
            final_state,
        )

    raw_json_decision_card = _extract_raw_json_decision_card(final_decision)
    if raw_json_decision_card:
        payload = _payload_from_decision_card_block(
            raw_json_decision_card,
            symbol=symbol,
            report_id=report_id,
            analysis_date=analysis_date,
            raw_signal=raw_signal,
        )
        card = DecisionCard(**payload)
        card.data_quality_notes.append(
            "DecisionCard was recovered from a raw JSON Portfolio Manager response."
        )
        return _attach_opportunity_evidence(
            apply_quality_gates(card, output_language=output_language), final_state
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
        return _attach_opportunity_evidence(
            apply_quality_gates(
                DecisionCard(**payload), output_language=output_language
            ),
            final_state,
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
        fallback.one_line_summary = _unstructured_rating_summary(
            rating=rating, output_language=output_language
        )
        fallback.thesis = _first_non_empty(
            final_decision[:600], fallback=fallback.thesis
        )
        fallback.data_quality_notes.append(
            "DecisionCard was derived from unstructured final decision text."
        )
        return _attach_opportunity_evidence(
            apply_quality_gates(fallback, output_language=output_language), final_state
        )

    return _attach_opportunity_evidence(
        build_fallback_decision_card(
            symbol=symbol,
            report_id=report_id,
            analysis_date=analysis_date,
            raw_signal=raw_signal,
            output_language=output_language,
        ),
        final_state,
    )
