from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, TypeAdapter

from diverge.agents.report_output import (
    AggressiveRiskStructuredOutput,
    BearCaseStructuredOutput,
    BullCaseStructuredOutput,
    ConservativeRiskStructuredOutput,
    FundamentalsReportStructuredOutput,
    MarketReportStructuredOutput,
    NeutralRiskStructuredOutput,
    NewsReportStructuredOutput,
    ResearchDecisionStructuredOutput,
    SentimentReportStructuredOutput,
    TraderStructuredOutput,
)
from diverge.runtime.messages import message_content
from diverge.runtime.structured_repair import normalize_structured_payload


def parse_structured_output(content: Any, schema: Any) -> Any:
    """Validate model JSON output against a Pydantic-compatible schema."""

    payload = _coerce_json_payload(content)
    return TypeAdapter(schema).validate_python(payload)


def repair_structured_output(output_schema: Any, raw_response: str):
    """Recover a schema-valid object from common malformed LLM outputs."""

    text = (raw_response or "").strip()
    if not text:
        return None

    candidates = [text]
    stripped = _strip_json_fence(text)
    if stripped != text:
        candidates.insert(0, stripped)

    for candidate in candidates:
        structured = _validate_first_json_object(output_schema, candidate)
        if structured is not None:
            return structured

    return _repair_markdown_json_highlights_output(output_schema, text)


def structured_output_warning(stage: str, error: BaseException) -> dict[str, str]:
    error_note = str(error).strip()[:500] or error.__class__.__name__
    return {
        "stage": stage,
        "kind": "structured_output_validation_failed",
        "message": (
            f"{stage} response did not match the ADK output schema; "
            "using a conservative schema-valid fallback. "
            f"Error type: {error.__class__.__name__}; detail: {error_note}"
        ),
    }


def fallback_structured_output(output_schema: Any, raw_response: str, stage: str):
    report = fallback_report_markdown(raw_response, stage)
    summary = (
        f"{stage} returned a response that could not be validated against the "
        "structured output schema."
    )
    common = {
        "signal": "HOLD",
        "signal_confidence": "low",
        "summary": summary,
        "evidence_blocks": [],
        "unknowns": ["Original model response failed structured validation."],
    }
    if output_schema is MarketReportStructuredOutput:
        highlights = {
            **common,
            "category": "market",
            "stance": "neutral",
            "trend_direction": "neutral",
            "key_levels": {"support": [], "resistance": []},
            "indicators": [],
            "volatility": None,
        }
    elif output_schema is FundamentalsReportStructuredOutput:
        highlights = {
            **common,
            "category": "fundamentals",
            "stance": "neutral",
            "metrics": [],
            "financial_health": None,
        }
    elif output_schema is SentimentReportStructuredOutput:
        highlights = {
            **common,
            "category": "sentiment",
            "stance": "neutral",
            "overall_sentiment": "neutral",
            "sentiment_score": None,
            "key_topics": [],
            "social_buzz": None,
        }
    elif output_schema is NewsReportStructuredOutput:
        highlights = {
            **common,
            "category": "news",
            "stance": "neutral",
            "market_impact": "neutral",
            "key_events": [],
            "macro_outlook": None,
        }
    elif output_schema is BullCaseStructuredOutput:
        highlights = {
            **common,
            "category": "bull_case",
            "stance": "bullish",
            "contrary_evidence": [],
            "key_arguments": [],
            "counterpoints": [],
        }
    elif output_schema is BearCaseStructuredOutput:
        highlights = {
            **common,
            "category": "bear_case",
            "stance": "bearish",
            "contrary_evidence": [],
            "key_arguments": [],
            "counterpoints": [],
        }
    elif output_schema is ResearchDecisionStructuredOutput:
        highlights = {
            **common,
            "category": "research_decision",
            "stance": "neutral",
            "decision": "HOLD",
            "aligned_with": "bull",
            "rationale": (
                "Structured validation failed, so no directional research edge "
                "is reliable."
            ),
            "action_items": ["Regenerate a schema-valid research decision."],
        }
    elif output_schema is TraderStructuredOutput:
        highlights = {
            **common,
            "category": "trader",
            "stance": "neutral",
            "decision": "HOLD",
            "entry_exit": {
                "action": "Wait for a schema-valid trading plan.",
                "entry_condition": None,
                "exit_target": None,
                "stop_loss": None,
                "invalidation": (
                    "A regenerated response validates against the trading schema."
                ),
                "re_entry": None,
            },
            "position_sizing": "No sizing until the trading plan validates.",
            "risk_budget": "No new risk budget from fallback output.",
            "risk_factors": ["Trading plan structured validation failed."],
        }
    elif output_schema is AggressiveRiskStructuredOutput:
        highlights = _fallback_risk_highlights(
            common,
            category="risk_aggressive",
            stance_label="Aggressive",
            risk_assessment="high",
        )
    elif output_schema is ConservativeRiskStructuredOutput:
        highlights = _fallback_risk_highlights(
            common,
            category="risk_conservative",
            stance_label="Conservative",
            risk_assessment="low",
        )
    elif output_schema is NeutralRiskStructuredOutput:
        highlights = _fallback_risk_highlights(
            common,
            category="risk_neutral",
            stance_label="Neutral",
            risk_assessment="moderate",
        )
    else:
        raise TypeError(f"Unsupported structured output schema: {output_schema!r}")

    return output_schema.model_validate(
        {
            "report_markdown": report,
            "highlights": highlights,
        }
    )


def fallback_report_markdown(raw_response: str, stage: str) -> str:
    report = (raw_response or "").strip()
    if report:
        payload_text = _strip_json_fence(report)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return report
        if isinstance(payload, dict):
            report_markdown = payload.get("report_markdown")
            if isinstance(report_markdown, str) and report_markdown.strip():
                return report_markdown.strip()
        return report

    return (
        f"## {stage} Fallback\n\n"
        "The model response was empty or invalid, so Diverge generated a "
        "conservative schema-validation fallback."
    )


def _coerce_json_payload(content: Any) -> Any:
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json")
    if isinstance(content, dict | list):
        return content
    if isinstance(content, tuple):
        return _coerce_json_payload(message_content(content))
    if isinstance(content, list):
        text = "\n".join(_text_part(item) for item in content).strip()
    else:
        text = str(content or "").strip()
    if not text:
        raise ValueError("Structured model response was empty.")

    fenced = _strip_json_fence(text)
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        return _first_json_value(text)


def _text_part(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("text") or item.get("content") or "")
    return str(getattr(item, "text", getattr(item, "content", "")) or "")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _first_json_value(text: str) -> Any:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return payload
    raise ValueError("Structured model response did not contain valid JSON.")


def _validate_first_json_object(output_schema: Any, text: str):
    try:
        payload, _index = json.JSONDecoder().raw_decode(text.lstrip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return _validate_or_repair_payload(output_schema, payload)


def _validate_or_repair_payload(output_schema: Any, payload: dict[str, Any]):
    try:
        return output_schema.model_validate(payload)
    except Exception:
        normalized = normalize_structured_payload(output_schema, payload)
        if normalized is None:
            return None
        try:
            return output_schema.model_validate(normalized)
        except Exception:
            return None


def _repair_markdown_json_highlights_output(output_schema: Any, text: str):
    block = _extract_json_highlights_block(text)
    if block is None:
        return None

    report_markdown, highlights_text = block
    try:
        highlights, _index = json.JSONDecoder().raw_decode(highlights_text.lstrip())
    except json.JSONDecodeError:
        return None
    if not isinstance(highlights, dict):
        return None

    return _validate_or_repair_payload(
        output_schema,
        {
            "report_markdown": report_markdown,
            "highlights": highlights,
        },
    )


def _extract_json_highlights_block(text: str) -> tuple[str, str] | None:
    marker = "```json-highlights"
    start = text.lower().rfind(marker)
    if start < 0:
        return None

    body_start = text.find("\n", start)
    if body_start < 0:
        return None
    body_start += 1

    body_end = text.find("```", body_start)
    if body_end < 0:
        return None

    before = text[:start].strip()
    after = text[body_end + 3 :].strip()
    report_parts = [part for part in (before, after) if part]
    return "\n\n".join(report_parts).strip(), text[body_start:body_end].strip()


def _fallback_risk_highlights(
    common: dict[str, Any],
    *,
    category: str,
    stance_label: str,
    risk_assessment: str,
) -> dict[str, Any]:
    return {
        **common,
        "category": category,
        "stance": "neutral",
        "stance_label": stance_label,
        "core_argument": (
            "Structured validation failed, so risk posture should stay "
            "conservative until regenerated."
        ),
        "risk_assessment": risk_assessment,
        "key_recommendations": ["Regenerate a schema-valid risk debate response."],
        "risk_budget": None,
    }
