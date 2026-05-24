from __future__ import annotations

from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel


def normalize_structured_payload(
    output_schema: Any,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    portfolio_payload = _normalize_portfolio_payload(output_schema, payload)
    if portfolio_payload is not None:
        return portfolio_payload

    normalized = dict(payload)
    highlights = normalized.get("highlights")
    if isinstance(highlights, dict):
        normalized["highlights"] = _normalize_highlights_payload(
            output_schema,
            highlights,
        )
    return _prune_model_payload(output_schema, normalized)


def _normalize_portfolio_payload(
    output_schema: Any,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        from diverge.agents.managers.portfolio_output import (
            PortfolioManagerStructuredOutput,
            normalize_invalid_portfolio_manager_payload,
        )
    except Exception:
        return None
    if output_schema is not PortfolioManagerStructuredOutput:
        return None
    return normalize_invalid_portfolio_manager_payload(payload)


def _normalize_highlights_payload(
    output_schema: Any,
    highlights: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(highlights)
    normalized["signal"] = _normalize_signal(normalized.get("signal"))
    if "signal_confidence" in normalized:
        normalized["signal_confidence"] = _normalize_confidence(
            normalized.get("signal_confidence")
        )
    if "stance" in normalized:
        normalized["stance"] = _normalize_research_stance(normalized.get("stance"))
    if "trend_direction" in normalized:
        normalized["trend_direction"] = _normalize_research_stance(
            normalized.get("trend_direction")
        )
    if "overall_sentiment" in normalized:
        normalized["overall_sentiment"] = _normalize_impact_value(
            normalized.get("overall_sentiment")
        )
    if "market_impact" in normalized:
        normalized["market_impact"] = _normalize_impact_value(
            normalized.get("market_impact")
        )
    if "risk_assessment" in normalized:
        normalized["risk_assessment"] = _normalize_risk_assessment(
            normalized.get("risk_assessment")
        )
    if "decision" in normalized:
        normalized["decision"] = _normalize_signal(normalized.get("decision"))
    elif normalized.get("category") == "trader":
        normalized["decision"] = normalized["signal"]
    if "aligned_with" in normalized:
        normalized["aligned_with"] = _normalize_aligned_with(
            normalized.get("aligned_with")
        )

    normalized["evidence_blocks"] = _normalize_evidence_blocks(
        normalized.get("evidence_blocks")
    )
    if "unknowns" in normalized:
        normalized["unknowns"] = _coerce_string_list(normalized.get("unknowns"))
    if "contrary_evidence" in normalized:
        normalized["contrary_evidence"] = _coerce_string_list(
            normalized.get("contrary_evidence")
        )
    if "counterpoints" in normalized:
        normalized["counterpoints"] = _coerce_string_list(
            normalized.get("counterpoints")
        )
    if "key_arguments" in normalized:
        normalized["key_arguments"] = _normalize_research_arguments(
            normalized.get("key_arguments")
        )
    if "key_events" in normalized:
        normalized["key_events"] = _normalize_news_events(
            normalized.get("key_events")
        )
    if "risk_budget" in normalized and isinstance(normalized["risk_budget"], dict):
        risk_budget = dict(normalized["risk_budget"])
        if "liquidity_risk" in risk_budget:
            risk_budget["liquidity_risk"] = _normalize_liquidity_risk(
                risk_budget.get("liquidity_risk")
            )
        normalized["risk_budget"] = risk_budget

    highlights_model = _highlights_model_for_schema(output_schema)
    if highlights_model is not None:
        return _prune_model_payload(highlights_model, normalized)
    return normalized


def _normalize_signal(value: Any) -> str:
    candidate = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "WATCH": "HOLD",
        "MAINTAIN": "HOLD",
        "NO_ACTION": "HOLD",
        "NEUTRAL": "HOLD",
        "AVOID": "UNDERWEIGHT",
        "TRIM": "UNDERWEIGHT",
        "EXIT": "SELL",
        "ACCUMULATE": "BUY",
    }
    candidate = aliases.get(candidate, candidate)
    if candidate in {"BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"}:
        return candidate
    return "HOLD"


def _normalize_confidence(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"high", "medium", "low"}:
        return candidate
    if candidate in {"strong", "elevated"}:
        return "high"
    if candidate in {"moderate", "mid", "mixed"}:
        return "medium"
    return "low"


def _normalize_research_stance(value: Any) -> str:
    candidate = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if candidate in {"bullish", "neutral", "bearish", "mixed"}:
        return candidate
    has_bullish = any(
        token in candidate
        for token in ("bull", "positive", "constructive", "upside", "favorable")
    )
    has_bearish = any(
        token in candidate
        for token in ("bear", "negative", "downside", "unfavorable", "risk")
    )
    if has_bullish and has_bearish:
        return "mixed"
    if "mixed" in candidate or "balanced" in candidate:
        return "mixed"
    if has_bullish:
        return "bullish"
    if has_bearish:
        return "bearish"
    return "neutral"


def _normalize_impact_value(value: Any) -> str:
    stance = _normalize_research_stance(value)
    if stance == "bullish":
        return "positive"
    if stance == "bearish":
        return "negative"
    return stance


def _normalize_risk_assessment(value: Any) -> str:
    candidate = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if candidate in {"high", "low", "moderate"}:
        return candidate
    if candidate in {"medium", "balanced", "mixed", "neutral"}:
        return "moderate"
    if candidate in {"elevated", "aggressive"}:
        return "high"
    return "moderate"


def _normalize_liquidity_risk(value: Any) -> str:
    candidate = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if candidate in {"low", "medium", "high", "unknown"}:
        return candidate
    if candidate in {"moderate", "balanced", "mixed"}:
        return "medium"
    return "unknown"


def _normalize_aligned_with(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if "bear" in candidate:
        return "bear"
    return "bull"


def _normalize_evidence_blocks(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    blocks: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                blocks.append(
                    {
                        "claim": _compact_summary(cleaned),
                        "evidence": cleaned,
                        "confidence": "low",
                    }
                )
        elif isinstance(item, dict):
            claim = _clean_string(item.get("claim") or item.get("point"))
            evidence = _clean_string(item.get("evidence") or item.get("detail"))
            if claim or evidence:
                blocks.append(
                    {
                        "claim": claim or _compact_summary(evidence or ""),
                        "evidence": evidence or claim or "",
                        "source": item.get("source")
                        if isinstance(item.get("source"), str)
                        else None,
                        "data_date": item.get("data_date")
                        if isinstance(item.get("data_date"), str)
                        else None,
                        "confidence": _normalize_confidence(item.get("confidence"))
                        if item.get("confidence") is not None
                        else None,
                        "limitation": item.get("limitation")
                        if isinstance(item.get("limitation"), str)
                        else None,
                    }
                )
    return blocks


def _normalize_research_arguments(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    arguments: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                arguments.append(
                    {"point": _compact_summary(cleaned), "evidence": cleaned}
                )
        elif isinstance(item, dict):
            point = _clean_string(item.get("point") or item.get("claim"))
            evidence = _clean_string(
                item.get("evidence") or item.get("detail") or item.get("rationale")
            )
            if point or evidence:
                arguments.append(
                    {
                        "point": point or _compact_summary(evidence or ""),
                        "evidence": evidence or point or "",
                    }
                )
    return arguments


def _normalize_news_events(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    events: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                events.append({"event": _compact_summary(cleaned), "impact": cleaned})
        elif isinstance(item, dict):
            event = _clean_string(item.get("event") or item.get("title"))
            impact = _clean_string(item.get("impact") or item.get("summary"))
            if event or impact:
                events.append(
                    {
                        "event": event or _compact_summary(impact or ""),
                        "impact": impact or event or "",
                    }
                )
    return events


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _compact_summary(value: str, *, max_chars: int = 72) -> str:
    compacted = " ".join(str(value or "").split())
    if len(compacted) <= max_chars:
        return compacted
    return f"{compacted[:max_chars].rstrip()}..."


def _highlights_model_for_schema(output_schema: Any) -> type[BaseModel] | None:
    field = getattr(output_schema, "model_fields", {}).get("highlights")
    if field is None:
        return None
    return _model_type_from_annotation(field.annotation)


def _model_type_from_annotation(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in {Union, UnionType}:
        for arg in get_args(annotation):
            model = _model_type_from_annotation(arg)
            if model is not None:
                return model
    return None


def _prune_model_payload(model: Any, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not hasattr(model, "model_fields"):
        return payload
    pruned: dict[str, Any] = {}
    for field_name, field in model.model_fields.items():
        if field_name in payload:
            pruned[field_name] = _prune_value_for_annotation(
                field.annotation,
                payload[field_name],
            )
    return pruned


def _prune_value_for_annotation(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        item_annotation = args[0] if args else Any
        if not isinstance(value, list):
            return value
        return [
            _prune_value_for_annotation(item_annotation, item)
            for item in value
        ]
    model = _model_type_from_annotation(annotation)
    if model is not None and isinstance(value, dict):
        return _prune_model_payload(model, value)
    return value
