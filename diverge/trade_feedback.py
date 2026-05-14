from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from diverge.common.dates import (
    iso_date_part,
    offset_iso_date,
    require_iso_date,
    today_iso,
)
from diverge.common.fields import (
    normalize_optional_number as normalize_field_optional_number,
    normalize_optional_text as normalize_field_optional_text,
    require_text as require_field_text,
)
from diverge.common.json_io import read_json_file, write_json_atomic
from diverge.common.symbols import normalize_ticker_symbol
from diverge.data_layout import resolve_history_dir, resolve_reports_dir
from diverge.dataflows.interface import route_to_vendor
from diverge.llm_clients import create_llm_client
from diverge.llm_clients.model_config import get_provider_base_url
from diverge.markets import resolve_symbol
from diverge.market_data.price_history import load_local_price_window

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADE_FEEDBACK_DIRNAME = ".trade_feedback"
REVIEW_TYPES = {"entry_review", "exit_review"}
TRADE_RECORD_FILENAME = "trade_record.json"
TRADE_RECORD_SCHEMA_VERSION = 2
PLANNED_HORIZONS = {
    "intraday",
    "multi_day",
    "swing_1_4w",
    "position_1_6m",
    "long_term_6m_plus",
    "event_driven",
    "unknown",
}
PLAN_EXECUTIONS = {
    "followed_plan",
    "partially_followed",
    "deviated_with_reason",
    "deviated_emotionally",
    "not_applicable",
    "unknown",
}
DEFAULT_STRATEGY_TAGS = {
    "breakout",
    "pullback",
    "trend_following",
    "mean_reversion",
    "earnings_catalyst",
    "news_catalyst",
    "valuation_reversion",
    "technical_reversal",
    "momentum",
    "defensive",
    "event_driven",
    "other",
}


def get_trade_feedback_root(reports_dir: Path | None = None) -> Path:
    base_dir = (
        Path(reports_dir).resolve()
        if reports_dir is not None
        else resolve_reports_dir(PROJECT_ROOT)
    )
    return base_dir / TRADE_FEEDBACK_DIRNAME


def create_trade_record(
    payload: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    market_resolution = _resolve_trade_market(payload)
    ticker = _normalize_ticker(market_resolution["canonical_symbol"])
    exit_timestamp = _normalize_optional_timestamp(
        payload.get("exit_timestamp"), "exit_timestamp"
    )
    exit_price = _normalize_optional_number(payload.get("exit_price"), "exit_price")
    status = _derive_trade_status(exit_timestamp, exit_price)
    trade_id = uuid.uuid4().hex
    record = {
        "type": "trade_record",
        "schema_version": TRADE_RECORD_SCHEMA_VERSION,
        "trade_id": trade_id,
        "raw_symbol": market_resolution["raw_symbol"],
        "ticker": ticker,
        "canonical_symbol": ticker,
        "display_symbol": market_resolution["display_symbol"],
        "market": market_resolution["market"],
        "exchange": market_resolution.get("exchange"),
        "asset_type": market_resolution["asset_type"],
        "exchange_or_market": _exchange_or_market(market_resolution),
        "market_resolution": market_resolution,
        "side": _normalize_side(payload.get("side", "long")),
        "status": status,
        "entry_timestamp": _normalize_optional_timestamp(
            payload.get("entry_timestamp"), "entry_timestamp"
        ),
        "entry_price": _normalize_required_number(
            payload.get("entry_price"), "entry_price"
        ),
        "exit_timestamp": exit_timestamp,
        "exit_price": exit_price,
        "size": _normalize_optional_number(payload.get("size"), "size"),
        "strategy_tags": _normalize_strategy_tags(payload.get("strategy_tags")),
        "entry_reason": _require_text(payload.get("entry_reason"), "entry_reason"),
        "initial_thesis": _normalize_initial_thesis(payload),
        "invalidation_condition": _require_text(
            payload.get("invalidation_condition"), "invalidation_condition"
        ),
        "planned_horizon": _normalize_planned_horizon(payload.get("planned_horizon")),
        "stop_loss": _normalize_optional_number(payload.get("stop_loss"), "stop_loss"),
        "take_profit": _normalize_optional_number(
            payload.get("take_profit"), "take_profit"
        ),
        "exit_reason": _normalize_optional_text(payload.get("exit_reason")),
        "plan_execution": _normalize_plan_execution(payload.get("plan_execution")),
        "notes": _normalize_optional_text(payload.get("notes")),
        "analysis_references": _normalize_analysis_references(
            payload.get("analysis_references") or []
        ),
        "derived_metrics": {},
        "created_at": now,
        "updated_at": now,
    }
    _validate_trade_record(record)
    record["derived_metrics"] = calculate_derived_metrics(record)
    _write_trade_record(record, reports_dir=reports_dir)
    return record


def update_trade_record(
    trade_id: str,
    updates: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    existing = get_trade_record(trade_id, reports_dir=reports_dir)
    updated = dict(existing)
    previous_ticker = existing["ticker"]

    if "raw_symbol" in updates or "market_resolution" in updates:
        market_resolution = _resolve_trade_market(
            {
                **updated,
                **updates,
                "raw_symbol": updates.get("raw_symbol") or updated.get("raw_symbol"),
            }
        )
        updated["raw_symbol"] = market_resolution["raw_symbol"]
        updated["ticker"] = _normalize_ticker(market_resolution["canonical_symbol"])
        updated["canonical_symbol"] = updated["ticker"]
        updated["display_symbol"] = market_resolution["display_symbol"]
        updated["market"] = market_resolution["market"]
        updated["exchange"] = market_resolution.get("exchange")
        updated["asset_type"] = market_resolution["asset_type"]
        updated["exchange_or_market"] = _exchange_or_market(market_resolution)
        updated["market_resolution"] = market_resolution
    if "side" in updates and updates["side"] is not None:
        updated["side"] = _normalize_side(updates["side"])
    if "entry_timestamp" in updates:
        updated["entry_timestamp"] = _normalize_optional_timestamp(
            updates.get("entry_timestamp"), "entry_timestamp"
        )
    if "entry_price" in updates:
        updated["entry_price"] = _normalize_required_number(
            updates.get("entry_price"), "entry_price"
        )
    if "exit_timestamp" in updates:
        updated["exit_timestamp"] = _normalize_optional_timestamp(
            updates.get("exit_timestamp"), "exit_timestamp"
        )
    if "exit_price" in updates:
        updated["exit_price"] = _normalize_optional_number(
            updates.get("exit_price"), "exit_price"
        )
    if "size" in updates:
        updated["size"] = _normalize_optional_number(updates.get("size"), "size")
    if "strategy_tags" in updates and updates["strategy_tags"] is not None:
        updated["strategy_tags"] = _normalize_strategy_tags(
            updates.get("strategy_tags")
        )
    if "entry_reason" in updates and updates["entry_reason"] is not None:
        updated["entry_reason"] = _require_text(updates["entry_reason"], "entry_reason")
    if (
        "invalidation_condition" in updates
        and updates["invalidation_condition"] is not None
    ):
        updated["invalidation_condition"] = _require_text(
            updates["invalidation_condition"], "invalidation_condition"
        )
    if "initial_thesis" in updates and updates["initial_thesis"] is not None:
        updated["initial_thesis"] = _normalize_optional_text(updates["initial_thesis"])
    if "planned_horizon" in updates and updates["planned_horizon"] is not None:
        updated["planned_horizon"] = _normalize_planned_horizon(
            updates["planned_horizon"]
        )
    if "stop_loss" in updates:
        updated["stop_loss"] = _normalize_optional_number(
            updates.get("stop_loss"), "stop_loss"
        )
    if "take_profit" in updates:
        updated["take_profit"] = _normalize_optional_number(
            updates.get("take_profit"), "take_profit"
        )
    if "exit_reason" in updates:
        updated["exit_reason"] = _normalize_optional_text(updates.get("exit_reason"))
    if "plan_execution" in updates and updates["plan_execution"] is not None:
        updated["plan_execution"] = _normalize_plan_execution(updates["plan_execution"])
    if "notes" in updates:
        updated["notes"] = _normalize_optional_text(updates.get("notes"))
    if "analysis_references" in updates:
        updated["analysis_references"] = _normalize_analysis_references(
            updates.get("analysis_references") or []
        )

    updated["schema_version"] = TRADE_RECORD_SCHEMA_VERSION
    updated["status"] = _derive_trade_status(
        updated.get("exit_timestamp"), updated.get("exit_price")
    )
    if not updated.get("initial_thesis"):
        updated["initial_thesis"] = updated.get("entry_reason", "")
    _validate_trade_record(updated)
    updated["derived_metrics"] = calculate_derived_metrics(updated)
    updated["updated_at"] = _now_iso()
    _write_trade_record(
        updated,
        reports_dir=reports_dir,
        previous_ticker=previous_ticker,
    )
    return updated


def list_trade_records(
    *,
    ticker: str | None = None,
    reports_dir: Path | None = None,
) -> list[dict[str, Any]]:
    root = get_trade_feedback_root(reports_dir)
    if not root.is_dir():
        return []

    if ticker:
        search_roots = [root / _normalize_ticker(ticker)]
    else:
        search_roots = [path for path in root.iterdir() if path.is_dir()]

    results: list[dict[str, Any]] = []
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for record_path in sorted(search_root.glob(f"*/{TRADE_RECORD_FILENAME}")):
            results.append(read_json_file(record_path))

    results.sort(key=lambda record: record.get("updated_at", ""), reverse=True)
    return results


def get_trade_record(
    trade_id: str,
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    record_path = _find_trade_record_path(trade_id, reports_dir=reports_dir)
    if record_path is None:
        raise ValueError(f"Trade '{trade_id}' not found")
    return read_json_file(record_path)


def list_trade_reviews(
    trade_id: str,
    *,
    reports_dir: Path | None = None,
) -> list[dict[str, Any]]:
    record = get_trade_record(trade_id, reports_dir=reports_dir)
    trade_dir = _trade_dir(record["ticker"], trade_id, reports_dir=reports_dir)
    reviews_dir = trade_dir / "reviews"
    if not reviews_dir.is_dir():
        return []

    reviews = []
    for review_type in sorted(REVIEW_TYPES):
        review_path = reviews_dir / f"{review_type}.json"
        if review_path.is_file():
            reviews.append(read_json_file(review_path))
    reviews.sort(key=lambda review: review.get("updated_at", ""), reverse=True)
    return reviews


def get_trade_feedback_payload(
    ticker: str,
    *,
    reports_dir: Path | None = None,
    limit: int = 3,
    analysis_date: str | None = None,
    visible_trade_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    normalized_ticker = _resolve_feedback_ticker(ticker)
    entries = list_trade_feedback_entries(
        normalized_ticker,
        reports_dir=reports_dir,
        visible_trade_ids=visible_trade_ids,
    )
    if analysis_date is not None:
        normalized_analysis_date = _normalize_analysis_date(analysis_date)
        entries = [
            entry
            for entry in entries
            if _review_visibility_date(entry) <= normalized_analysis_date
        ]
    selected_entries = entries[:limit] if limit > 0 else entries
    selected_entries = [
        {
            **entry,
            "feedback_selection_reason": _feedback_selection_reason(
                normalized_ticker,
                entry,
            ),
        }
        for entry in selected_entries
    ]
    return {
        "ticker": normalized_ticker,
        "reviews": selected_entries,
        "prompt": _build_feedback_prompt(normalized_ticker, selected_entries),
        "selection_strategy": "same_ticker_recent_visible_reviews",
    }


def list_trade_feedback_entries(
    ticker: str,
    *,
    reports_dir: Path | None = None,
    visible_trade_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    normalized_ticker = _resolve_feedback_ticker(ticker)
    allowed_trade_ids = (
        {str(trade_id) for trade_id in visible_trade_ids}
        if visible_trade_ids is not None
        else None
    )
    results: list[dict[str, Any]] = []
    for record in list_trade_records(ticker=normalized_ticker, reports_dir=reports_dir):
        if (
            allowed_trade_ids is not None
            and record["trade_id"] not in allowed_trade_ids
        ):
            continue
        for review in list_trade_reviews(record["trade_id"], reports_dir=reports_dir):
            results.append(
                {
                    "trade_id": record["trade_id"],
                    "ticker": record["ticker"],
                    "exchange_or_market": record["exchange_or_market"],
                    "raw_symbol": record.get("raw_symbol"),
                    "canonical_symbol": record.get("canonical_symbol"),
                    "display_symbol": record.get("display_symbol"),
                    "market": record.get("market"),
                    "exchange": record.get("exchange"),
                    "asset_type": record.get("asset_type"),
                    "market_resolution": record.get("market_resolution"),
                    "side": record["side"],
                    "status": record["status"],
                    "entry_timestamp": record.get("entry_timestamp"),
                    "entry_price": record.get("entry_price"),
                    "exit_timestamp": record.get("exit_timestamp"),
                    "exit_price": record.get("exit_price"),
                    "size": record.get("size"),
                    "strategy_tags": record.get("strategy_tags", []),
                    "entry_reason": record.get("entry_reason"),
                    "invalidation_condition": record.get("invalidation_condition"),
                    "exit_reason": record.get("exit_reason"),
                    "plan_execution": record.get("plan_execution"),
                    "initial_thesis": record.get("initial_thesis"),
                    "planned_horizon": record.get("planned_horizon"),
                    "stop_loss": record.get("stop_loss"),
                    "take_profit": record.get("take_profit"),
                    "derived_metrics": calculate_derived_metrics(record),
                    "review_id": review["review_id"],
                    "review_type": review["review_type"],
                    "analysis_date": review.get("analysis_date"),
                    "analysis_references": review.get("analysis_references", []),
                    "thesis_assessment": review.get("thesis_assessment", ""),
                    "timing_assessment": review.get("timing_assessment", ""),
                    "sizing_assessment": review.get("sizing_assessment", ""),
                    "discipline_assessment": review.get("discipline_assessment", ""),
                    "outcome_summary": review.get("outcome_summary", ""),
                    "improvement_actions": review.get("improvement_actions", []),
                    "ticker_specific_lessons": review.get(
                        "ticker_specific_lessons", []
                    ),
                    "cross_ticker_tags": review.get("cross_ticker_tags", []),
                    "created_at": review.get("created_at"),
                    "updated_at": review.get("updated_at"),
                }
            )
    results.sort(key=lambda entry: entry.get("updated_at", ""), reverse=True)
    return results


def generate_trade_review(
    trade_id: str,
    *,
    review_type: str,
    llm_provider: str,
    model: str,
    output_language: str = "en",
    google_thinking_level: str | None = None,
    openai_reasoning_effort: str | None = None,
    analysis_date: str | None = None,
    analysis_references: Optional[list[dict[str, Any]]] = None,
    reports_dir: Path | None = None,
    history_dir: Path | None = None,
    include_external_news: bool = False,
    llm: Any = None,
) -> dict[str, Any]:
    normalized_review_type = _normalize_review_type(review_type)
    trade_record = get_trade_record(trade_id, reports_dir=reports_dir)
    snapshot_references = _normalize_analysis_references(
        analysis_references
        if analysis_references is not None
        else trade_record.get("analysis_references") or []
    )

    prompt = _build_review_prompt(
        trade_record,
        normalized_review_type,
        snapshot_references,
        output_language=output_language,
        analysis_date=analysis_date,
        history_dir=history_dir,
        include_external_news=include_external_news,
    )

    active_llm = llm
    if active_llm is None:
        llm_kwargs: dict[str, Any] = {}
        if llm_provider == "openai" and openai_reasoning_effort:
            llm_kwargs["reasoning_effort"] = openai_reasoning_effort
        if llm_provider == "google" and google_thinking_level:
            llm_kwargs["thinking_level"] = google_thinking_level
        try:
            base_url = get_provider_base_url(llm_provider)
        except KeyError:
            base_url = None
        active_llm = create_llm_client(
            provider=llm_provider,
            model=model,
            base_url=base_url,
            **llm_kwargs,
        ).get_llm()

    response = active_llm.invoke(prompt)
    response_text = getattr(response, "content", response)
    if not isinstance(response_text, str):
        response_text = str(response_text)
    parsed_review = _normalize_review_payload(_extract_json_object(response_text))

    return _save_trade_review(
        trade_id,
        review_type=normalized_review_type,
        review_payload=parsed_review,
        analysis_date=analysis_date,
        analysis_references=snapshot_references,
        reports_dir=reports_dir,
    )


def save_trade_review(
    trade_id: str,
    *,
    review_type: str,
    payload: dict[str, Any],
    analysis_date: str | None = None,
    analysis_references: Optional[list[dict[str, Any]]] = None,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    normalized_review_type = _normalize_review_type(review_type)
    parsed_review = _normalize_review_payload(payload)
    return _save_trade_review(
        trade_id,
        review_type=normalized_review_type,
        review_payload=parsed_review,
        analysis_date=analysis_date,
        analysis_references=analysis_references,
        reports_dir=reports_dir,
    )


def _save_trade_review(
    trade_id: str,
    *,
    review_type: str,
    review_payload: dict[str, Any],
    analysis_date: str | None,
    analysis_references: Optional[list[dict[str, Any]]],
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    trade_record = get_trade_record(trade_id, reports_dir=reports_dir)
    existing_review = _find_existing_review(
        trade_id,
        review_type,
        reports_dir=reports_dir,
    )
    snapshot_references = _resolve_review_analysis_references(
        trade_record,
        existing_review=existing_review,
        analysis_references=analysis_references,
    )

    now = _now_iso()
    review = {
        "type": "trade_review",
        "schema_version": 1,
        "review_id": f"{trade_id}:{review_type}",
        "trade_id": trade_id,
        "ticker": trade_record["ticker"],
        "review_type": review_type,
        "analysis_date": _resolve_review_date(
            analysis_date,
            snapshot_references,
            existing_review=existing_review,
        ),
        "analysis_references": snapshot_references,
        "created_at": (
            existing_review.get("created_at")
            if isinstance(existing_review, dict)
            else now
        ),
        "updated_at": now,
        **review_payload,
    }
    _write_trade_review(review, reports_dir=reports_dir)
    return review


def _build_review_prompt(
    trade_record: dict[str, Any],
    review_type: str,
    analysis_references: list[dict[str, Any]],
    *,
    output_language: str,
    analysis_date: str | None = None,
    history_dir: Path | None = None,
    include_external_news: bool = False,
) -> str:
    trade_context = {
        "trade_id": trade_record["trade_id"],
        "ticker": trade_record["ticker"],
        "raw_symbol": trade_record.get("raw_symbol"),
        "canonical_symbol": trade_record.get("canonical_symbol"),
        "display_symbol": trade_record.get("display_symbol"),
        "market": trade_record.get("market"),
        "exchange": trade_record.get("exchange"),
        "asset_type": trade_record.get("asset_type"),
        "exchange_or_market": trade_record["exchange_or_market"],
        "market_resolution": trade_record.get("market_resolution"),
        "side": trade_record["side"],
        "status": trade_record["status"],
        "entry_timestamp": trade_record.get("entry_timestamp"),
        "entry_price": trade_record.get("entry_price"),
        "exit_timestamp": trade_record.get("exit_timestamp"),
        "exit_price": trade_record.get("exit_price"),
        "size": trade_record.get("size"),
        "strategy_tags": trade_record.get("strategy_tags", []),
        "entry_reason": trade_record.get("entry_reason"),
        "invalidation_condition": trade_record.get("invalidation_condition"),
        "initial_thesis": trade_record.get("initial_thesis"),
        "planned_horizon": trade_record.get("planned_horizon"),
        "stop_loss": trade_record.get("stop_loss"),
        "take_profit": trade_record.get("take_profit"),
        "exit_reason": trade_record.get("exit_reason"),
        "plan_execution": trade_record.get("plan_execution"),
        "notes": trade_record.get("notes"),
        "derived_metrics": calculate_derived_metrics(trade_record),
    }

    snapshot_context = [
        _load_snapshot_context(reference) for reference in analysis_references
    ]
    evidence_pack = _build_review_evidence_pack(
        trade_record,
        review_type,
        analysis_date=analysis_date,
        history_dir=history_dir,
        include_external_news=include_external_news,
    )
    review_diagnostics = _build_review_diagnostics(
        trade_record,
        review_type,
        evidence_pack=evidence_pack,
    )
    snapshot_note = (
        "Attached analysis snapshots are available. Use them as supplementary evidence, but keep the saved trade record as the primary source of truth."
        if analysis_references
        else "No analysis snapshots are attached. Review from the saved trade record, thesis, notes, prices, timestamps, risk plan, and any realized outcome fields. Do not invent report evidence."
    )
    review_focus = _build_review_focus(review_type)
    target_language_label = (
        "Simplified Chinese" if output_language.lower() == "cn" else "English"
    )
    language_instruction = f"Write free-form string values in {target_language_label}."

    return f"""You are writing a structured trade review for a manual trading journal.
Your role is a high-quality trading coach: candid, evidence-based, process-focused, and practical.
Your goal is not to criticize missing fields mechanically. Your goal is to evaluate the quality of the trading decision, identify the highest-leverage process error, and turn it into concrete next-time rules.

{review_focus}

==========================================
CRITICAL OUTPUT FORMAT (read first)
==========================================
- Return ONLY a single JSON object. No markdown fences, no headers, no prose outside the JSON.
- JSON keys MUST be in English exactly as specified in the schema below, regardless of any other language instruction.
- {language_instruction} applies ONLY to the string VALUES inside the JSON, never to the keys.
- Mini example of the expected key/value language split (illustrative only, not real content):
  {{"thesis_assessment": "Verdict: breakout idea is directionally plausible but not yet tradable. Score: 2/5 because the record gives a breakout theme but not the level or validation rule. Evidence: entry reason says intraday breakout chase; no catalyst support was available. Impact: the trade cannot be repeated or audited as a planned breakout.", "timing_assessment": "Verdict: entry looks extended rather than confirmed. Score: 2/5 because price was above the recent range but lacked retest/close/volume confirmation. Evidence: entry price was already above the 20-day high while latest close fell back below entry. Impact: chase and reversal risk were elevated.", "sizing_assessment": "Verdict: risk was not bounded before entry. Score: risk/reward 1/5; sizing 2/5 because stop, target, and planned horizon were not defined. Evidence: no stop or target was recorded for a volatile breakout. Impact: size could not be tied to 1R or account risk.", "discipline_assessment": "Verdict: this was a process failure, not just an incomplete note. Score: 2/5 because the order was entered before trigger, invalidation, and exit rules were executable. Evidence: the record says intraday chase but has no confirmation gate. Impact: future entries can drift into discretion under market noise.", "outcome_summary": "Evidence: local_price_history=unavailable, external_news=unavailable. Record quality: low. Setup: breakout. Process: weak. Confidence: low. Main root cause: risk plan undefined. Confidence is low because price evidence is missing and the entry rule was not recorded. Coaching verdict: the setup direction may be reasonable, but the process was not tradeable because the trigger and risk boundary were not specified. Next time, block the order until breakout level, confirmation gate, stop, target, and horizon are filled.", "improvement_actions": ["BLOCKING: Before entering a breakout trade, require breakout_level, confirmation_method, stop_loss, take_profit_or_reward_target, and planned_horizon; reject the order if any is blank.", "CONDITIONAL: If entry is more than 3% above the breakout level without retest or close confirmation, restrict the order to probe size and forbid adding until the close confirms.", "CONDITIONAL: Before submitting the order, calculate R:R from planned stop to nearest target; if R:R is below 2:1, skip or reduce risk by at least 50%."], "ticker_specific_lessons": ["For this ticker/setup, do not treat a high intraday print as confirmation; record the breakout level and the close/retest rule first."], "cross_ticker_tags": ["risk_plan_undefined", "breakout_without_confirmation"]}}
- If evidence is incomplete, still make a bounded process evaluation and name the missing evidence briefly; never omit the key.

==========================================
Core principles:
==========================================
- Do not reduce the review to PnL alone.
- Separate process quality from realized outcome.
- Separate record quality from trade quality.
- Diagnose trading behavior, not form completeness. The review should read like a trading coach identifying process errors, not a compliance audit of missing fields.
- The output should feel like a coach speaking to the trader: direct, specific, and useful. Avoid bureaucratic phrases, raw diagnostic keys, and vague motivational language.
- Make a judgment even when evidence is incomplete. The uncertainty should limit confidence, not replace the evaluation.
- Avoid obvious hindsight bias. If a point depends on information that was unavailable at the time, say so explicitly.
- Anchor every conclusion in the trade record first; use attached analysis snapshots only when they exist.
- Treat the four assessment fields as display modules, not literal old categories:
  - `thesis_assessment` = Logic assessment. For entry reviews, evaluate the entry logic/setup rationale. For exit reviews, evaluate the exit logic relative to thesis change, invalidation, plan, or updated evidence.
  - `timing_assessment` = Technical assessment. For entry reviews, verify whether the buy actually satisfied the setup trigger, confirmation, extension/chase, volume/market context, and whether available fundamental/catalyst context supports or conflicts with the technical signal. For exit reviews, verify whether the sell satisfied the exit trigger, technical exit timing, support/resistance/trend context, and whether fundamentals or updated evidence supported the exit.
  - `sizing_assessment` = Risk-control assessment. Evaluate stop, target, R:R, position sizing, and computable risk only. If risk control was not defined or was not computable, explicitly give the required risk-control rule or remediation. Do not repeat the technical trigger critique here.
  - `discipline_assessment` = Execution assessment. Evaluate plan-vs-action, checklist completeness, emotional/chasing/deviation evidence, and follow-through. If execution quality was poor, state that plainly and critique the operational failure. Do not soften poor execution into generic improvement language, and do not repeat the full risk-plan critique here.
- Use Review diagnostics as the source of truth when it provides setup_type, record_quality, missing_critical_fields, validation_warnings, or priority_process_errors. Only infer these fields from the trade record when Review diagnostics is missing or explicitly uncertain.
- Use the evidence pack for market context before making technical, news, or catalyst claims.
- If an evidence source is marked unavailable, explicitly state that limitation instead of filling the gap with generic language, but mention each unavailable evidence source at most once.
- Distinguish pre-decision evidence from latest/post-decision evidence. Latest news or post-entry price action can inform current risk or hindsight calibration, but must not be treated as information available at the original entry/exit time.
- Do not mechanically punish a trade for missing fundamentals if the setup is clearly technical or short-term. For technical breakout, momentum, pullback, or other short-term trades, fundamental thesis means basic catalyst, news, event, liquidity, and fundamental risk awareness rather than a full valuation case.
- For technical breakout, momentum, pullback, or short-term trades, thesis_assessment should focus on whether the trade had enough risk-awareness context, not whether it had a full investment thesis. Keep fundamental discussion to 1-2 sentences unless the trade explicitly claims a fundamental or value thesis.
- Missing data lowers record quality and review confidence. It lowers trade quality only when the missing field is essential to the inferred setup, such as stop loss, invalidation, confirmation, or reward/risk for a breakout trade.
- When the trade record is too incomplete for a confident judgment, make a bounded process evaluation and name the missing decision rule briefly instead of filling the gap with generic criticism.
- Prioritize the top 1-3 process errors. Avoid listing every possible missing field unless it directly affected decision quality.
- If multiple fields are missing, group them into one root cause instead of repeating them separately, such as "risk plan undefined" for missing invalidation, stop, target, and reward/risk.
- Do not explain general trading theory unless it directly changes the next action for this trade. Prefer diagnosis and rules over education.
- Reports and full-state logs are optional supplements, not prerequisites. {snapshot_note}
- Use trade record fields in this priority order: entry_reason; invalidation_condition; strategy_tags and planned_horizon; stop_loss, take_profit, and size; exit_reason and plan_execution; market_resolution, prices, and timestamps; notes; analysis snapshots.
- Treat notes and snapshots as supplemental evidence. Do not let them override structured entry, invalidation, exit, or plan execution fields.

==========================================
Coaching voice and evidence translation
==========================================
- Translate raw record and diagnostic keys into trader-facing language in the review values.
  - Write "stop was not recorded", not `stop_loss=null`.
  - Write "R:R could not be calculated", not `risk_reward_available=false`.
  - Write "breakout level and confirmation method were missing", not `missing_critical_fields`.
  - Write "open trade with no exit-management rule", not `status=open and exit data missing`.
- Do not output internal diagnostic keys such as `missing_critical_fields`, `priority_process_errors`, `computable_metrics`, `risk_reward_available`, `position_risk_available`, or `technical_decision_checks` in any review value.
- It is acceptable to name trader-facing fields such as entry reason, breakout level, confirmation method, stop, target, planned horizon, size, entry price, latest close, RSI, ATR, and volume.
- For each score, include a short "because..." explanation so the reader understands why it is not one point higher or lower.
- Prefer one sharp coaching sentence over a list of raw evidence. Evidence should support the verdict, not become the verdict.
- Outcome summary after the anchor sentence should be 2-3 coaching sentences only:
  1. why confidence is high/medium/low, naming what raised and lowered it,
  2. overall coaching verdict and primary root cause,
  3. the next rule that would have prevented the problem.

==========================================
Root-cause grouping (strict)
==========================================
- Group related missing fields into ONE root cause and mention it ONCE, in the single most relevant section. Do not repeat the same gap across multiple fields.
- Assign each root cause to one primary module:
  - entry/exit logic problems -> `thesis_assessment`
  - price/trigger/confirmation problems -> `timing_assessment`
  - stop/target/R:R/size problems -> `sizing_assessment`
  - plan/execution/emotion/process problems -> `discipline_assessment`
- Common groupings:
  - "risk plan undefined" covers missing stop_loss, take_profit, invalidation_condition, planned_horizon, R:R.
  - "entry trigger unspecified" covers missing breakout level, confirmation method, volume criteria, retest rules.
  - "thesis context missing" covers missing catalyst, news awareness, sector/market context for non-fundamental setups.
- BAD example (do NOT do this):
  sizing_assessment: "no stop_loss, no take_profit..."
  discipline_assessment: "no stop_loss, no planned_horizon..."
  improvement_actions: ["set stop_loss", "set take_profit", "set planned_horizon", "set invalidation"]
- GOOD example:
  sizing_assessment mentions "risk plan undefined -> cannot bind size to risk".
  discipline_assessment focuses on plan-vs-execution, not re-listing the same gap.
  improvement_actions has ONE rule that enforces the whole risk plan together.

==========================================
Evaluation process:
==========================================
1. Read Review diagnostics first:
   - Use review_type, setup_type, record_quality, missing_critical_fields, validation_warnings, and priority_process_errors from Review diagnostics when present.
   - Only infer these values from the trade record when diagnostics is missing or explicitly uncertain.

2. If diagnostics is missing or uncertain, Determine setup_type from strategy_tags, entry_reason, notes, and planned_horizon:
   - breakout
   - pullback
   - trend_following
   - mean_reversion
   - earnings_or_event
   - value_or_fundamental
   - momentum_chase
   - unclear

3. If diagnostics is missing or uncertain, determine record/data quality:
   - high: entry reason, invalidation, stop, target or exit plan, size, timeframe, and relevant price/market context are available.
   - medium: core trade idea exists, but some risk or context fields are missing.
   - low: trade idea is vague or risk plan is missing.
   Low data_quality means limited review confidence, not automatic poor trade quality. However, missing stop, invalidation, or reward/risk is a process risk and should affect risk/reward and discipline scores when those fields are essential to the setup.

4. Use setup-specific evaluation:
   - For breakout trades, focus on breakout level, confirmation method, distance from breakout level at entry, volume or volatility expansion, market/sector confirmation, invalidation level, reward/risk, and whether the entry was a planned breakout or late chase.
   - For pullback trades, focus on trend context, support area, reversal confirmation, stop placement, reward/risk, and whether the pullback is orderly or a breakdown.
   - For trend_following trades, focus on trend strength, entry alignment with trend structure, trailing invalidation, risk/reward, and whether the entry chased an extended move.
   - For mean_reversion trades, focus on overextension evidence, support/resistance, reversion trigger, stop placement, and whether the trade fights a dominant trend.
   - For value_or_fundamental trades, focus on thesis quality, valuation, catalyst, downside risk, expected holding period, and thesis invalidation.
   - For earnings_or_event trades, focus on event date, expected surprise, positioning, gap risk if available, and predefined exit plan.
   - If setup_type is unclear, say so and evaluate mainly record quality, risk definition, and process discipline.

5. Apply module-specific judgment:
   - Technical assessment must answer the direct question: did the buy/sell conform to the declared setup and available evidence? For entry reviews, say whether the buy was valid, weak, late/chasing, or unverified. For exit reviews, say whether the sell was plan-based, technically justified, premature, late, or unverified.
   - Technical assessment must cross-check fundamentals/catalysts when available. If fundamentals/news are unavailable, say the technical signal cannot be confirmed or rejected by catalyst context; do not invent support or conflict.
   - Risk-control assessment must not stop at "risk missing". If stop_loss, take_profit, invalidation, R:R, or size logic is missing, provide the concrete risk-control requirement needed before the next order.
   - Execution assessment must be candid. If the record shows chasing, plan deviation, missing checklist, or poor execution, name it as a process failure and explain the operational consequence.

6. Use this score meaning:
   - 1 = absent or materially flawed
   - 2 = weak, incomplete, or high uncertainty
   - 3 = acceptable but not strong
   - 4 = good and evidence-backed
   - 5 = excellent, specific, and repeatable

   Score floors by setup_type:
   - For non-fundamental setups (breakout / pullback / trend_following / mean_reversion / momentum_chase), the fundamental thesis score has a FLOOR of 2 unless the trade actively ignored a known fundamental risk, such as entering the day before earnings without acknowledging it. Missing catalyst notes alone is not enough to score 1.
   - For value_or_fundamental setups, no floor; score 1 is appropriate when the fundamental case is absent.
   - For earnings_or_event setups, missing event date or surprise expectation is a 1.

==========================================
Inputs
==========================================
Trade record:
```json
{json.dumps(trade_context, ensure_ascii=False, indent=2)}
```

Analysis snapshot references:
```json
{json.dumps(analysis_references, ensure_ascii=False, indent=2)}
```

Analysis snapshot content:
```json
{json.dumps(snapshot_context, ensure_ascii=False, indent=2)}
```

Evidence pack:
```json
{json.dumps(evidence_pack, ensure_ascii=False, indent=2)}
```

Review diagnostics:
```json
{json.dumps(review_diagnostics, ensure_ascii=False, indent=2)}
```

==========================================
Output schema (return EXACTLY this object)
==========================================
{{
  "thesis_assessment": "string",
  "timing_assessment": "string",
  "sizing_assessment": "string",
  "discipline_assessment": "string",
  "outcome_summary": "string",
  "improvement_actions": ["string"],
  "ticker_specific_lessons": ["string"],
  "cross_ticker_tags": ["string"]
}}

==========================================
Field requirements
==========================================
General:
- Each assessment field uses this compact structure:
    "Verdict: <one phrase> | Score: <1-5 or named sub-scores> | Evidence: <specific record/evidence items> | Impact: <how it affected this trade>"
  Keep it tight. Skip a sub-part with "n/a" if truly not applicable, but do not omit the structure.
- Each assessment must reference at least one concrete trader-facing record item or evidence item. Generic phrasing like "risk control insufficient" without naming the missing stop, target, entry trigger, or confirmation rule is not acceptable.
- Do not write long sub-sections inside a field. Each assessment should be one compact paragraph.
- Do not label content as "fundamental/timing/sizing/discipline" inside the values. Use the module meanings above: Logic, Technical, Risk-control, Execution.
- `timing_assessment` must explicitly answer whether the buy/sell conformed to the declared setup and must mention available fundamental/catalyst support, conflict, or unavailability.
- `sizing_assessment` must include at least one concrete risk-control remediation when risk controls are missing or uncomputable.
- `discipline_assessment` must be critical when execution is poor. Use direct wording such as "execution failure", "process failure", "chase", or "plan violation" when supported by the record.
- The first sentence of `outcome_summary` MUST follow this exact format:
    "Evidence: local_price_history=<status>, external_news=<status>. Record quality: <high|medium|low>. Setup: <setup_type>. Process: <excellent|good|acceptable|weak|poor>. Confidence: <high|medium|low>."
  After this anchor sentence, write the rest of the summary in {target_language_label}.
- Mention at least one concrete item from `Evidence pack.local_price_history` when its status is `available`.
- When `Review diagnostics.technical_decision_checks.status` is `available`, `timing_assessment` MUST cite at least three concrete OHLC-derived metrics from `technical_decision_checks.key_metrics` or `Evidence pack.local_price_history.technical_summary`, such as latest_close, previous_20d_high, entry_vs_previous_20d_high_pct, volume_vs_20d_avg, rsi_14, atr_14, close_vs_sma_20_pct, or recent_bars.
- When local OHLC is available, do NOT say there is no chart, volume, price structure, or technical context. Instead, use the OHLC metrics to evaluate what can be verified, and separately state only what remains unavailable, such as intraday tape or exact user-defined breakout level.
- If `Evidence pack.local_price_history.status` is not `available`, say which local cache/source was unavailable before discussing technical timing, but mention this limitation at most once.
- Mention `Evidence pack.external_news.status` when discussing news, catalysts, or fundamentals. Do not invent news if it is unavailable, and mention this limitation at most once.

Score scope per review type:
- Entry reviews score: fundamental thesis, technical timing, risk/reward, sizing, discipline.
- Exit reviews score: fundamental change assessment, technical exit timing, risk/reward, sizing/risk control, discipline.
- Adapt fundamental scoring by setup_type per the floors above.
- `sizing_assessment` may include named sub-scores, for example "Score: risk/reward 1/5; sizing 2/5", when one string must cover both risk/reward and sizing.

outcome_summary is the SINGLE place for:
- record_quality, setup_type, process_quality, confidence (in the anchor sentence)
- top 1-3 root causes
- key strengths
- key weaknesses
- hindsight calibration (only when exit or post-entry evidence exists)
- review confidence and any material evidence limitation, expressed as a bounded coaching judgment
Do NOT duplicate these in the four assessment fields. Assessment fields hold only their own dimension's verdict/score/evidence/impact.

improvement_actions:
- Return 3 to 5 items only, ranked by impact. The first must address the highest-impact process error.
- Each action must be enforceable by software or a pre-order checklist. Test: can I write a boolean check that fires before order placement? If no, rewrite.
- Mix severity levels so the ruleset is usable rather than uniformly punitive:
  - 1-2 `BLOCKING:` gates for non-negotiable risk fundamentals, such as missing stop, target, position-risk cap, or required setup trigger.
  - 1-2 `CONDITIONAL:` constraints for setup-quality issues, such as extended entry, missing retest, weak volume, or high volatility; these may allow probe size, reduced risk, or delayed add rules.
  - 0-1 `FLAG:` logging rules for softer context issues that should tag the trade or force post-trade review without blocking the order.
- Prefix each action with exactly one severity label: `BLOCKING:`, `CONDITIONAL:`, or `FLAG:`.
- Prefer "Before entering ..., check ..." or "If ..., then ..." phrasing. Use numeric thresholds when the record, setup defaults, or provided rule examples support them; otherwise use explicit boolean gates instead of inventing numbers.
- GOOD examples:
  - "BLOCKING: Every breakout order must have stop_loss, take_profit, and planned_horizon filled before submission; reject the order otherwise."
  - "CONDITIONAL: If entry occurs more than 3% above the breakout level intraday without a retest, reduce size to a probe (<=25% of normal) and require a daily close above the level to add."
  - "FLAG: If catalyst/news context is unavailable for a high-volatility breakout, tag the order as catalyst_unverified and force next-day review."
- BAD examples (do NOT produce these):
  - "Control risk better." (not checkable)
  - "Write a testable hypothesis before entering." (verb too soft, no threshold or gate)
  - "Be more disciplined about breakouts." (no rule)

ticker_specific_lessons:
- Lessons that apply directly to this ticker or this exact setup. 1-3 items.

cross_ticker_tags:
- Short reusable tags, all English lowercase snake_case, like `late_breakout_entry`, `risk_plan_undefined`, `earnings_gap_risk`. 2-5 tags.
- Do not mix Chinese and English in tags. Tags are system keys for aggregation, filtering, URLs, and database indexes.

==========================================
Final reminders before output
==========================================
- Output is ONE JSON object. Nothing before it, nothing after it.
- English keys, {target_language_label} values.
- Do not repeat the same missing-field gap across multiple sections; group it.
- Mention each unavailable evidence source at most once across the whole output.
- If you find yourself writing trading theory, delete it and replace with a checkable rule.
- For exit reviews, state whether the exit was plan-based, evidence-based, or emotion-based in `discipline_assessment`.
"""


def _build_review_evidence_pack(
    trade_record: dict[str, Any],
    review_type: str,
    *,
    analysis_date: str | None,
    history_dir: Path | None,
    include_external_news: bool,
) -> dict[str, Any]:
    action_date = _resolve_review_action_date(trade_record, review_type, analysis_date)
    return {
        "action_date": action_date,
        "local_price_history": _build_local_price_history_evidence(
            trade_record,
            action_date=action_date,
            history_dir=history_dir,
        ),
        "external_news": _build_external_news_evidence(
            trade_record,
            action_date=action_date,
            include_external_news=include_external_news,
        ),
    }


def _build_review_diagnostics(
    trade_record: dict[str, Any],
    review_type: str,
    *,
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    setup_type = _infer_setup_type(trade_record)
    missing_critical_fields = _review_missing_critical_fields(
        trade_record, setup_type, review_type
    )
    validation_warnings = _review_validation_warnings(
        trade_record,
        setup_type,
        missing_critical_fields,
    )
    computable_metrics = {
        "risk_reward_available": _has_number(trade_record.get("entry_price"))
        and _has_number(trade_record.get("stop_loss"))
        and _has_number(trade_record.get("take_profit")),
        "position_risk_available": _has_number(trade_record.get("entry_price"))
        and _has_number(trade_record.get("stop_loss"))
        and _has_number(trade_record.get("size")),
        "holding_period_available": bool(
            trade_record.get("entry_timestamp") and trade_record.get("exit_timestamp")
        ),
    }
    source_statuses = {
        "local_price_history": _nested_status(evidence_pack, "local_price_history"),
        "external_news": _nested_status(evidence_pack, "external_news"),
    }
    technical_decision_checks = _build_technical_decision_checks(
        trade_record,
        setup_type,
        evidence_pack,
    )
    return {
        "review_type": review_type,
        "setup_type": setup_type,
        "record_quality": _classify_review_record_quality(
            trade_record,
            setup_type,
            missing_critical_fields,
            validation_warnings,
        ),
        "missing_critical_fields": missing_critical_fields,
        "validation_warnings": validation_warnings,
        "priority_process_errors": _priority_process_errors(
            setup_type,
            missing_critical_fields,
            validation_warnings,
            computable_metrics,
        ),
        "computable_metrics": computable_metrics,
        "evidence_statuses": source_statuses,
        "technical_decision_checks": technical_decision_checks,
    }


def _build_technical_decision_checks(
    trade_record: dict[str, Any],
    setup_type: str,
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    local_history = evidence_pack.get("local_price_history")
    if (
        not isinstance(local_history, dict)
        or local_history.get("status") != "available"
    ):
        return {
            "status": "unavailable",
            "reason": (
                local_history.get("reason")
                if isinstance(local_history, dict)
                else "local price history is unavailable"
            ),
        }
    summary = local_history.get("technical_summary")
    if not isinstance(summary, dict):
        return {
            "status": "unavailable",
            "reason": "local price history has no technical_summary",
        }

    entry_price = _json_number(trade_record.get("entry_price"))
    latest_close = _json_number(summary.get("latest_close"))
    previous_high = _json_number(summary.get("previous_20d_high"))
    entry_vs_previous_high = _pct_diff(entry_price, previous_high)
    entry_vs_latest_close = _pct_diff(entry_price, latest_close)
    checks = {
        "status": "available",
        "setup_type": setup_type,
        "must_use_in_timing_assessment": True,
        "required_ohlc_metrics": [
            "latest_close",
            "previous_20d_high",
            "entry_vs_previous_20d_high_pct",
            "volume_vs_20d_avg",
            "rsi_14",
            "atr_14",
        ],
        "key_metrics": {
            "entry_price": entry_price,
            "latest_close": latest_close,
            "previous_20d_high": previous_high,
            "entry_vs_previous_20d_high_pct": entry_vs_previous_high,
            "entry_vs_latest_close_pct": entry_vs_latest_close,
            "return_20d_pct": summary.get("return_20d_pct"),
            "close_vs_sma_20_pct": summary.get("close_vs_sma_20_pct"),
            "close_vs_sma_50_pct": summary.get("close_vs_sma_50_pct"),
            "volume_vs_20d_avg": summary.get("volume_vs_20d_avg"),
            "rsi_14": summary.get("rsi_14"),
            "atr_14": summary.get("atr_14"),
        },
        "interpretation_hints": _technical_interpretation_hints(
            setup_type,
            entry_price=entry_price,
            latest_close=latest_close,
            previous_high=previous_high,
            summary=summary,
        ),
    }
    return checks


def _technical_interpretation_hints(
    setup_type: str,
    *,
    entry_price: float | None,
    latest_close: float | None,
    previous_high: float | None,
    summary: dict[str, Any],
) -> list[str]:
    hints: list[str] = []
    entry_vs_previous_high = _pct_diff(entry_price, previous_high)
    entry_vs_latest_close = _pct_diff(entry_price, latest_close)
    volume_ratio = _json_number(summary.get("volume_vs_20d_avg"))
    rsi = _json_number(summary.get("rsi_14"))
    close_vs_sma20 = _json_number(summary.get("close_vs_sma_20_pct"))
    if setup_type == "breakout" and entry_vs_previous_high is not None:
        if entry_vs_previous_high > 3:
            hints.append(
                "entry is more than 3% above the previous 20d high; treat as extended breakout/chase unless retest or close confirmation exists"
            )
        elif entry_vs_previous_high >= 0:
            hints.append(
                "entry is above the previous 20d high; breakout trigger may be present if confirmation and risk are defined"
            )
        else:
            hints.append(
                "entry is below the previous 20d high; breakout trigger is not confirmed by local OHLC"
            )
    if entry_vs_latest_close is not None and entry_vs_latest_close > 0:
        hints.append(
            "entry price is above the latest close in the evidence window; check intraday chase/slippage risk"
        )
    if volume_ratio is not None:
        if volume_ratio >= 1.5:
            hints.append(
                "volume is materially above 20d average, supporting participation but not replacing risk control"
            )
        elif volume_ratio >= 1.1:
            hints.append(
                "volume is only moderately above 20d average; confirmation is not strong by volume alone"
            )
        else:
            hints.append("volume does not confirm strong participation")
    if rsi is not None and rsi >= 70:
        hints.append(
            "RSI14 is above 70; momentum is strong but overextension risk is elevated"
        )
    if close_vs_sma20 is not None and close_vs_sma20 > 10:
        hints.append(
            "close is more than 10% above SMA20; short-term extension risk is elevated"
        )
    return hints


def _infer_setup_type(trade_record: dict[str, Any]) -> str:
    text = _review_signal_text(trade_record)
    if _contains_any(
        text, ("value", "valuation", "fundamental", "基本面", "估值", "价值")
    ):
        return "value_or_fundamental"
    if _contains_any(
        text, ("earnings", "event", "catalyst", "财报", "公告", "事件", "业绩", "催化")
    ):
        return "earnings_or_event"
    if _contains_any(text, ("breakout", "break out", "突破", "破位向上")):
        return "breakout"
    if _contains_any(text, ("pullback", "retest", "回踩", "回调", "支撑")):
        return "pullback"
    if _contains_any(text, ("trend", "趋势", "均线", "moving average")):
        return "trend_following"
    if _contains_any(
        text, ("mean reversion", "reversion", "超跌", "低吸", "反弹", "回归")
    ):
        return "mean_reversion"
    if _contains_any(text, ("momentum", "chase", "追高", "动量", "急拉", "冲高")):
        return "momentum_chase"
    return "unclear"


def _review_missing_critical_fields(
    trade_record: dict[str, Any],
    setup_type: str,
    review_type: str,
) -> list[str]:
    missing: list[str] = []
    if setup_type == "breakout":
        if not _mentions_breakout_level(trade_record):
            missing.append("breakout_level")
        if not _mentions_confirmation_method(trade_record):
            missing.append("confirmation_method")
    if setup_type in {
        "pullback",
        "mean_reversion",
    } and not _mentions_support_or_reversal(trade_record):
        missing.append("support_or_reversal_reference")
    if not _has_testable_invalidation(trade_record.get("invalidation_condition")):
        missing.append("testable_invalidation")
    if not _has_number(trade_record.get("stop_loss")):
        missing.append("stop_loss")
    if not _has_number(trade_record.get("take_profit")):
        missing.append("take_profit_or_reward_target")
    if (
        not trade_record.get("planned_horizon")
        or trade_record.get("planned_horizon") == "unknown"
    ):
        missing.append("planned_horizon")
    if not _has_number(trade_record.get("size")):
        missing.append("size")
    if review_type == "exit_review":
        if not _normalize_optional_text(trade_record.get("exit_reason")):
            missing.append("exit_reason")
        if trade_record.get("plan_execution") in (None, "", "unknown"):
            missing.append("plan_execution")
    return _dedupe_preserve(missing)


def _review_validation_warnings(
    trade_record: dict[str, Any],
    setup_type: str,
    missing_critical_fields: list[str],
) -> list[str]:
    warnings: list[str] = []
    text = _review_signal_text(trade_record)
    if _contains_any(text, ("追高", "chase", "急拉", "冲高")):
        warnings.append("entry_reason suggests intraday chase or extended entry")
    if (
        trade_record.get("invalidation_condition")
        and "testable_invalidation" in missing_critical_fields
    ):
        warnings.append("invalidation_condition is vague")
    if (
        "stop_loss" in missing_critical_fields
        or "take_profit_or_reward_target" in missing_critical_fields
        or "testable_invalidation" in missing_critical_fields
    ):
        warnings.append("risk_reward cannot be calculated from the record")
    if setup_type == "breakout" and (
        "breakout_level" in missing_critical_fields
        or "confirmation_method" in missing_critical_fields
    ):
        warnings.append(
            "breakout setup is not executable without level and confirmation"
        )
    return _dedupe_preserve(warnings)


def _classify_review_record_quality(
    trade_record: dict[str, Any],
    setup_type: str,
    missing_critical_fields: list[str],
    validation_warnings: list[str],
) -> str:
    if not _normalize_optional_text(trade_record.get("entry_reason")):
        return "low"
    risk_fields = {"testable_invalidation", "stop_loss"}
    if risk_fields.intersection(missing_critical_fields):
        return "low"
    if setup_type == "breakout" and {
        "breakout_level",
        "confirmation_method",
    }.intersection(missing_critical_fields):
        return "medium"
    if len(missing_critical_fields) >= 3 or validation_warnings:
        return "medium"
    return "high"


def _priority_process_errors(
    setup_type: str,
    missing_critical_fields: list[str],
    validation_warnings: list[str],
    computable_metrics: dict[str, bool],
) -> list[str]:
    errors: list[str] = []
    if setup_type == "breakout" and (
        {"breakout_level", "confirmation_method"}.intersection(missing_critical_fields)
        or any("chase" in warning for warning in validation_warnings)
    ):
        errors.append(
            "breakout execution undefined: level, confirmation, or chase control is missing"
        )
    if {
        "testable_invalidation",
        "stop_loss",
        "take_profit_or_reward_target",
    }.intersection(missing_critical_fields) or not computable_metrics.get(
        "risk_reward_available"
    ):
        errors.append(
            "risk plan undefined: invalidation, stop, target, or reward/risk cannot be checked"
        )
    if {"planned_horizon", "exit_reason", "plan_execution"}.intersection(
        missing_critical_fields
    ):
        errors.append(
            "exit management undefined: holding period or exit rules are not executable"
        )
    if not errors and missing_critical_fields:
        errors.append("record lacks setup-critical evidence for a confident review")
    return errors[:3]


def _review_signal_text(trade_record: dict[str, Any]) -> str:
    values: list[str] = []
    values.extend(str(tag) for tag in trade_record.get("strategy_tags") or [])
    for key in (
        "entry_reason",
        "initial_thesis",
        "invalidation_condition",
        "planned_horizon",
        "exit_reason",
        "notes",
    ):
        value = trade_record.get(key)
        if value:
            values.append(str(value))
    return " ".join(values).lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _mentions_breakout_level(trade_record: dict[str, Any]) -> bool:
    text = _review_signal_text(trade_record)
    level_terms = (
        "breakout_level",
        "breakout level",
        "突破位",
        "关键位",
        "前高",
        "阻力",
        "箱体",
        "平台",
        "颈线",
        "高点",
        "resistance",
        "previous high",
    )
    return bool(re.search(r"\d+(?:\.\d+)?", text)) or _contains_any(text, level_terms)


def _mentions_confirmation_method(trade_record: dict[str, Any]) -> bool:
    text = _review_signal_text(trade_record)
    return _contains_any(
        text,
        (
            "confirmation",
            "confirmed",
            "确认",
            "收盘",
            "close above",
            "close confirmation",
            "站稳",
            "放量",
            "volume",
            "回踩",
            "retest",
        ),
    )


def _mentions_support_or_reversal(trade_record: dict[str, Any]) -> bool:
    text = _review_signal_text(trade_record)
    return _contains_any(
        text,
        (
            "support",
            "resistance",
            "reversal",
            "支撑",
            "阻力",
            "反转",
            "止跌",
            "回踩",
            "低点",
        ),
    )


def _has_testable_invalidation(value: Any) -> bool:
    text = _normalize_optional_text(value).lower()
    if not text:
        return False
    if bool(re.search(r"\d+(?:\.\d+)?", text)):
        return True
    return _contains_any(
        text,
        (
            "close below",
            "below support",
            "break below",
            "跌破",
            "收盘",
            "支撑",
            "低点",
            "突破位下方",
            "pullback low",
        ),
    )


def _has_number(value: Any) -> bool:
    if value is None or value == "":
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _nested_status(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, dict):
        return str(value.get("status") or "unknown")
    return "unknown"


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _resolve_review_action_date(
    trade_record: dict[str, Any],
    review_type: str,
    analysis_date: str | None,
) -> str:
    fallback_date = (
        _normalize_analysis_date(analysis_date) if analysis_date else today_iso()
    )
    if review_type == "exit_review":
        return _date_part(trade_record.get("exit_timestamp")) or fallback_date
    return _date_part(trade_record.get("entry_timestamp")) or fallback_date


def _build_local_price_history_evidence(
    trade_record: dict[str, Any],
    *,
    action_date: str,
    history_dir: Path | None,
) -> dict[str, Any]:
    market = str(trade_record.get("market") or "").strip().lower() or None
    symbol = str(
        trade_record.get("canonical_symbol")
        or trade_record.get("ticker")
        or trade_record.get("raw_symbol")
        or ""
    ).strip()
    resolved_history_dir = (
        Path(history_dir)
        if history_dir is not None
        else resolve_history_dir(PROJECT_ROOT)
    )
    if not market or not symbol:
        return {
            "status": "unavailable",
            "reason": "trade record does not include a resolved market and symbol",
            "history_dir": str(resolved_history_dir),
        }

    cache_path = None
    effective_action_date = action_date
    lookback_start = _date_offset(action_date, -180)
    try:
        price_window = load_local_price_window(
            history_dir=resolved_history_dir,
            market=market,
            symbol=symbol,
            as_of_date=action_date,
            lookback_days=180,
            normalize_to_trading_day=True,
        )
        cache_path = price_window["cache_path"]
        coverage = price_window["coverage"]
        action_window = price_window["window"]
        lookback_start = price_window["start_date"]
        effective_action_date = price_window["as_of_date"]
        if action_window.empty:
            return {
                "status": "unavailable",
                "reason": coverage["status"],
                "cache_path": str(cache_path),
                "cache_span": coverage.get("cache_span"),
                "required_window": f"{lookback_start}..{effective_action_date}",
            }

        evidence = {
            "status": "available",
            "source": "local_history_cache",
            "cache_path": str(cache_path),
            "cache_span": coverage.get("cache_span"),
            "required_window": f"{lookback_start}..{effective_action_date}",
            "used_window": _frame_date_span(action_window),
            "bar_count": int(len(action_window)),
            "technical_summary": _summarize_price_window(
                action_window,
                trade_record=trade_record,
                action_date=effective_action_date,
            ),
            "recent_bars": _recent_bars(action_window, limit=8),
        }
        if effective_action_date != action_date:
            evidence["requested_action_date"] = action_date
            evidence["action_date"] = effective_action_date
        return evidence
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "cache_path": str(cache_path or resolved_history_dir),
            "required_window": f"{lookback_start}..{action_date}",
        }


def _build_external_news_evidence(
    trade_record: dict[str, Any],
    *,
    action_date: str,
    include_external_news: bool,
) -> dict[str, Any]:
    symbol = str(
        trade_record.get("display_symbol")
        or trade_record.get("canonical_symbol")
        or trade_record.get("ticker")
        or ""
    ).strip()
    if not include_external_news:
        return {
            "status": "unavailable",
            "reason": "external news lookup is disabled for this review generation",
        }
    if not symbol:
        return {
            "status": "unavailable",
            "reason": "trade record does not include a symbol for news lookup",
        }

    today = today_iso()
    latest_start = _date_offset(today, -14)
    action_start = _date_offset(action_date, -14)
    try:
        latest_news = route_to_vendor("get_news", symbol, latest_start, today)
        action_news = (
            latest_news
            if action_date == today
            else route_to_vendor("get_news", symbol, action_start, action_date)
        )
        return {
            "status": "available",
            "source": "configured_news_data_vendor",
            "pre_action_window": f"{action_start}..{action_date}",
            "pre_action_news": _truncate_text(str(action_news), 4000),
            "latest_window": f"{latest_start}..{today}",
            "latest_news": _truncate_text(str(latest_news), 4000),
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "pre_action_window": f"{action_start}..{action_date}",
            "latest_window": f"{latest_start}..{today}",
        }


def _summarize_price_window(
    frame,
    *,
    trade_record: dict[str, Any],
    action_date: str,
) -> dict[str, Any]:
    close_values = _numeric_series(frame, "Close")
    volume_values = _numeric_series(frame, "Volume")
    high_values = _numeric_series(frame, "High")
    low_values = _numeric_series(frame, "Low")
    if close_values.empty:
        return {
            "status": "unavailable",
            "reason": "Close column has no usable numeric values",
        }

    last = frame.iloc[-1]
    latest_close = _json_number(last.get("Close"))
    latest_volume = _json_number(last.get("Volume"))
    ma20 = _series_tail_mean(close_values, 20)
    ma50 = _series_tail_mean(close_values, 50)
    previous_20_high = _series_tail_max(high_values.iloc[:-1], 20)
    previous_20_low = _series_tail_min(low_values.iloc[:-1], 20)
    volume_avg20 = _series_tail_mean(volume_values.iloc[:-1], 20)
    return {
        "as_of_date": action_date,
        "latest_bar_date": str(last.get("Date")),
        "latest_close": latest_close,
        "latest_volume": latest_volume,
        "return_20d_pct": _pct_change(close_values, 20),
        "return_60d_pct": _pct_change(close_values, 60),
        "sma_20": ma20,
        "sma_50": ma50,
        "close_vs_sma_20_pct": _pct_diff(latest_close, ma20),
        "close_vs_sma_50_pct": _pct_diff(latest_close, ma50),
        "previous_20d_high": previous_20_high,
        "previous_20d_low": previous_20_low,
        "close_vs_previous_20d_high_pct": _pct_diff(latest_close, previous_20_high),
        "close_vs_previous_20d_low_pct": _pct_diff(latest_close, previous_20_low),
        "volume_vs_20d_avg": _ratio(latest_volume, volume_avg20),
        "rsi_14": _rsi(close_values, 14),
        "atr_14": _atr(high_values, low_values, close_values, 14),
        "trade_price_context": {
            "entry_price": trade_record.get("entry_price"),
            "exit_price": trade_record.get("exit_price"),
            "stop_loss": trade_record.get("stop_loss"),
            "take_profit": trade_record.get("take_profit"),
            "entry_vs_latest_close_pct": _pct_diff(
                trade_record.get("entry_price"),
                latest_close,
            ),
        },
    }


def _recent_bars(frame, *, limit: int) -> list[dict[str, Any]]:
    rows = []
    for row in frame.tail(limit).itertuples(index=False):
        rows.append(
            {
                "date": getattr(row, "Date", None),
                "open": _json_number(getattr(row, "Open", None)),
                "high": _json_number(getattr(row, "High", None)),
                "low": _json_number(getattr(row, "Low", None)),
                "close": _json_number(getattr(row, "Close", None)),
                "volume": _json_number(getattr(row, "Volume", None)),
            }
        )
    return rows


def _date_part(value: Any) -> str | None:
    return iso_date_part(value)


def _date_offset(value: str, days: int) -> str:
    return offset_iso_date(value, days)


def _frame_date_span(frame) -> str | None:
    if frame is None or frame.empty:
        return None
    return f"{frame.iloc[0]['Date']}..{frame.iloc[-1]['Date']}"


def _numeric_series(frame, column: str):
    import pandas as pd

    if column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _series_tail_mean(series, window: int) -> float | None:
    if len(series) < window:
        return None
    return _round_float(series.tail(window).mean())


def _series_tail_max(series, window: int) -> float | None:
    if len(series) < window:
        return None
    return _round_float(series.tail(window).max())


def _series_tail_min(series, window: int) -> float | None:
    if len(series) < window:
        return None
    return _round_float(series.tail(window).min())


def _pct_change(series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    previous = float(series.iloc[-periods - 1])
    current = float(series.iloc[-1])
    if previous == 0:
        return None
    return _round_float((current / previous - 1) * 100)


def _pct_diff(numerator: Any, denominator: Any) -> float | None:
    try:
        left = float(numerator)
        right = float(denominator)
    except (TypeError, ValueError):
        return None
    if right == 0:
        return None
    return _round_float((left / right - 1) * 100)


def _ratio(numerator: Any, denominator: Any) -> float | None:
    try:
        left = float(numerator)
        right = float(denominator)
    except (TypeError, ValueError):
        return None
    if right == 0:
        return None
    return _round_float(left / right)


def _rsi(close_values, window: int) -> float | None:
    if len(close_values) <= window:
        return None
    delta = close_values.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.tail(window).mean()
    avg_loss = losses.tail(window).mean()
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else None
    rs = avg_gain / avg_loss
    return _round_float(100 - (100 / (1 + rs)))


def _atr(high_values, low_values, close_values, window: int) -> float | None:
    if (
        len(high_values) <= window
        or len(low_values) <= window
        or len(close_values) <= window
    ):
        return None
    ranges = []
    for index in range(1, len(close_values)):
        high = float(high_values.iloc[index])
        low = float(low_values.iloc[index])
        previous_close = float(close_values.iloc[index - 1])
        ranges.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
    if len(ranges) < window:
        return None
    return _round_float(sum(ranges[-window:]) / window)


def _round_float(value: Any) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _json_number(value: Any) -> float | None:
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass
    return _round_float(value)


def _truncate_text(value: str, max_chars: int) -> str:
    return value if len(value) <= max_chars else value[:max_chars] + "\n...[truncated]"


def _build_review_focus(review_type: str) -> str:
    if review_type == "entry_review":
        return """
This is an ENTRY review.

Evaluate the quality of the entry decision primarily using information that was available at or before the entry time.
Do not judge the entry mainly by the later outcome. If post-entry price action, news, or PnL is available, place it in a separate hindsight calibration section only.

Review the entry from both fundamental and technical perspectives:

1. Fundamental thesis:
   - Was there a clear fundamental reason to enter?
   - Were valuation, growth, earnings, macro, sector trend, catalyst, liquidity, or narrative conditions supportive?
   - Were key risks, counterarguments, or missing information acknowledged?
   - Was the thesis specific enough to be tested later?

2. Technical setup:
   - Was the entry aligned with trend, market structure, support/resistance, volume, volatility, momentum, or breakout/pullback conditions?
   - Was the timing early, reasonable, late, or chasing?
   - Was there confirmation, or was the entry premature?

3. Risk/reward and sizing:
   - Was the expected upside/downside attractive?
   - Was there a clear invalidation level or stop-loss logic?
   - Was position size appropriate relative to conviction, volatility, portfolio risk, and account drawdown limits?

4. Discipline and process:
   - Did the trader follow the plan?
   - Was the entry driven by evidence or by FOMO, revenge trading, overconfidence, or impulse?
   - Were there better alternatives, such as waiting, scaling in, or using a smaller size?

Output the review content with:
- Overall entry verdict: Excellent / Good / Mixed / Poor
- Scores from 1 to 5 for: fundamental thesis, technical timing, risk/reward, sizing, discipline
- Key strengths
- Key weaknesses
- What should be improved before taking a similar trade again
- Hindsight calibration, if later outcome data exists
"""

    return """
This is an EXIT review.

Evaluate the quality of the exit decision relative to the original thesis, intended holding period, risk limits, and information available at or before the exit time.
Realized PnL matters, but it must not be the sole basis of the review. If later price action after the exit is available, use it only as hindsight calibration.

Review the exit from both fundamental and technical perspectives:

1. Change in fundamental thesis:
   - Did the original fundamental thesis improve, weaken, break, or remain intact?
   - Were there new earnings results, guidance changes, macro shifts, sector changes, regulatory/news events, liquidity changes, or catalyst failures?
   - Was the exit based on a real thesis change or merely emotional discomfort?

2. Technical exit quality:
   - Did the technical structure justify exiting?
   - Consider trend, support/resistance, moving averages, volume, momentum, volatility, breakdowns, failed breakouts, exhaustion, or reversal signals.
   - Was the exit early, timely, late, or panic-driven?

3. Risk/reward after holding:
   - At the exit point, was the remaining upside still worth the downside risk?
   - Had the trade reached target, stop, trailing stop, time stop, or invalidation level?
   - Would partial exit, full exit, holding, hedging, or adding have been more rational?

4. Sizing and portfolio risk:
   - Did the exit reduce risk appropriately?
   - Was the decision consistent with account-level risk, drawdown control, concentration, and volatility?

5. Discipline and process:
   - Did the trader follow the pre-defined plan?
   - Was the exit based on evidence, or on fear, greed, impatience, regret, or PnL anchoring?
   - Was the exit consistent with the stated time horizon?

Output the review content with:
- Overall exit verdict: Excellent / Good / Mixed / Poor
- Scores from 1 to 5 for: fundamental change assessment, technical exit timing, risk/reward, sizing/risk control, discipline
- Key strengths
- Key weaknesses
- Whether the exit was plan-based, evidence-based, or emotion-based
- What should be improved in future exits
- Hindsight calibration, if later outcome data exists
"""


def _build_feedback_prompt(ticker: str, reviews: list[dict[str, Any]]) -> str:
    if not reviews:
        return ""

    lines = [
        f"Historical trade feedback for ticker {ticker}:",
        "Use these prior reviews as process feedback only. Do not anchor blindly on past outcomes or treat them as a substitute for the current evidence.",
    ]
    for index, review in enumerate(reviews, start=1):
        actions = "; ".join(review.get("improvement_actions") or []) or "None"
        lessons = "; ".join(review.get("ticker_specific_lessons") or []) or "None"
        tags = ", ".join(review.get("cross_ticker_tags") or []) or "None"
        lines.extend(
            [
                f"{index}. Trade {review['trade_id']} ({review['review_type']}, updated {review.get('updated_at')})",
                f"Initial thesis: {review.get('initial_thesis') or 'N/A'}",
                f"Outcome summary: {review.get('outcome_summary') or 'N/A'}",
                f"Thesis assessment: {review.get('thesis_assessment') or 'N/A'}",
                f"Timing assessment: {review.get('timing_assessment') or 'N/A'}",
                f"Sizing assessment: {review.get('sizing_assessment') or 'N/A'}",
                f"Discipline assessment: {review.get('discipline_assessment') or 'N/A'}",
                f"Improvement actions: {actions}",
                f"Ticker-specific lessons: {lessons}",
                f"Cross-ticker tags: {tags}",
            ]
        )
    return "\n".join(lines)


def _feedback_selection_reason(ticker: str, review: dict[str, Any]) -> str:
    if review.get("ticker") == ticker:
        return "same_ticker_recent_review"
    return "recent_related_review"


def _normalize_review_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "thesis_assessment": _require_text(
            payload.get("thesis_assessment"), "thesis_assessment"
        ),
        "timing_assessment": _require_text(
            payload.get("timing_assessment"), "timing_assessment"
        ),
        "sizing_assessment": _require_text(
            payload.get("sizing_assessment"), "sizing_assessment"
        ),
        "discipline_assessment": _require_text(
            payload.get("discipline_assessment"), "discipline_assessment"
        ),
        "outcome_summary": _require_text(
            payload.get("outcome_summary"), "outcome_summary"
        ),
        "improvement_actions": _normalize_string_list(
            payload.get("improvement_actions"), "improvement_actions"
        ),
        "ticker_specific_lessons": _normalize_string_list(
            payload.get("ticker_specific_lessons"), "ticker_specific_lessons"
        ),
        "cross_ticker_tags": _normalize_string_list(
            payload.get("cross_ticker_tags"), "cross_ticker_tags"
        ),
    }


def _find_existing_review(
    trade_id: str,
    review_type: str,
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any] | None:
    for saved_review in list_trade_reviews(trade_id, reports_dir=reports_dir):
        if saved_review["review_type"] == review_type:
            return saved_review
    return None


def _resolve_review_analysis_references(
    trade_record: dict[str, Any],
    *,
    existing_review: dict[str, Any] | None,
    analysis_references: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if analysis_references is not None:
        source = analysis_references
    elif isinstance(existing_review, dict) and existing_review.get(
        "analysis_references"
    ):
        source = existing_review["analysis_references"]
    else:
        source = trade_record.get("analysis_references") or []
    return _normalize_analysis_references(source)


def _resolve_review_date(
    analysis_date: str | None,
    analysis_references: list[dict[str, Any]],
    *,
    existing_review: dict[str, Any] | None,
) -> str:
    if analysis_date is not None:
        return _normalize_analysis_date(analysis_date)
    if isinstance(existing_review, dict) and existing_review.get("analysis_date"):
        return _normalize_analysis_date(existing_review["analysis_date"])
    if analysis_references:
        return max(reference["analysis_date"] for reference in analysis_references)
    return _now_iso()[:10]


def _review_analysis_date(review: dict[str, Any]) -> str:
    if review.get("analysis_date"):
        return _normalize_analysis_date(review["analysis_date"])
    references = review.get("analysis_references") or []
    dates = [
        _normalize_analysis_date(reference.get("analysis_date"))
        for reference in references
        if isinstance(reference, dict) and reference.get("analysis_date")
    ]
    if dates:
        return max(dates)
    return "0001-01-01"


def _review_visibility_date(review: dict[str, Any]) -> str:
    # Gate historical replay on when this saved review payload actually existed.
    for field_name in ("updated_at", "created_at"):
        timestamp = review.get(field_name)
        if timestamp:
            return _timestamp_to_date(timestamp, field_name)
    return _review_analysis_date(review)


def _timestamp_to_date(value: Any, field_name: str) -> str:
    text = _require_text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from exc
    return parsed.date().isoformat()


def _load_snapshot_context(reference: dict[str, Any]) -> dict[str, Any]:
    complete_report_path = _resolve_project_path(reference["report_path"])

    complete_report = complete_report_path.read_text(encoding="utf-8")
    state_excerpt = {}
    full_state_log_path = reference.get("full_state_log_path") or ""
    snapshot_warning = None
    if full_state_log_path:
        resolved_full_state_log_path = _resolve_project_path(full_state_log_path)
        if resolved_full_state_log_path.is_file():
            full_state_payload = json.loads(
                resolved_full_state_log_path.read_text(encoding="utf-8")
            )
            if (
                isinstance(full_state_payload, dict)
                and reference["analysis_date"] in full_state_payload
                and isinstance(full_state_payload[reference["analysis_date"]], dict)
            ):
                selected_state = full_state_payload[reference["analysis_date"]]
            elif (
                isinstance(full_state_payload, dict)
                and len(full_state_payload) == 1
                and isinstance(next(iter(full_state_payload.values())), dict)
            ):
                selected_state = next(iter(full_state_payload.values()))
            else:
                selected_state = full_state_payload

            if isinstance(selected_state, dict):
                for key in (
                    "trade_date",
                    "market_report",
                    "sentiment_report",
                    "news_report",
                    "fundamentals_report",
                    "investment_plan",
                    "final_trade_decision",
                ):
                    value = selected_state.get(key)
                    if value:
                        state_excerpt[key] = value
                trader_plan = selected_state.get(
                    "trader_investment_plan"
                ) or selected_state.get("trader_investment_decision")
                if trader_plan:
                    state_excerpt["trader_investment_plan"] = trader_plan
            else:
                state_excerpt["raw_value"] = selected_state
        else:
            snapshot_warning = (
                "full_state_log_path was provided but the file does not exist"
            )
    else:
        snapshot_warning = "full_state_log_path is not attached"

    context = {
        "analysis_date": reference["analysis_date"],
        "report_path": reference["report_path"],
        "full_state_log_path": full_state_log_path,
        "complete_report": complete_report,
        "full_state_excerpt": state_excerpt,
    }
    if snapshot_warning:
        context["snapshot_warning"] = snapshot_warning
    return context


def _normalize_analysis_references(
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []
    for item in references:
        if not isinstance(item, dict):
            raise ValueError("analysis_references entries must be objects")
        analysis_date = _normalize_analysis_date(item.get("analysis_date"))
        report_path = _normalize_project_relative_path(
            item.get("report_path"), "report_path"
        )
        full_state_log_path = _normalize_optional_project_relative_path(
            item.get("full_state_log_path"), "full_state_log_path"
        )
        normalized.append(
            {
                "analysis_date": analysis_date,
                "report_path": report_path,
                "full_state_log_path": full_state_log_path,
            }
        )
    return normalized


def _normalize_analysis_date(value: Any) -> str:
    return require_iso_date(value, "analysis_date")


def _normalize_project_relative_path(value: Any, field_name: str) -> str:
    project_root = PROJECT_ROOT.resolve()
    resolved = _resolve_project_path(_require_text(value, field_name))
    if not resolved.is_file():
        raise ValueError(f"{field_name} does not point to an existing file")
    return resolved.relative_to(project_root).as_posix()


def _normalize_optional_project_relative_path(value: Any, field_name: str) -> str:
    text = _normalize_optional_text(value)
    if not text:
        return ""
    project_root = PROJECT_ROOT.resolve()
    raw_path = Path(text)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    resolved = candidate.resolve()
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise ValueError(
            "Analysis references must remain inside the project directory"
        ) from exc


def _resolve_project_path(value: str) -> Path:
    project_root = PROJECT_ROOT.resolve()
    raw_path = Path(value)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(
            "Analysis references must remain inside the project directory"
        ) from exc
    return resolved


def _normalize_review_type(value: str) -> str:
    review_type = _require_text(value, "review_type")
    if review_type not in REVIEW_TYPES:
        raise ValueError("review_type must be entry_review or exit_review")
    return review_type


def _find_trade_record_path(
    trade_id: str,
    *,
    reports_dir: Path | None = None,
) -> Path | None:
    root = get_trade_feedback_root(reports_dir)
    if not root.is_dir():
        return None
    for record_path in root.glob(f"*/*/{TRADE_RECORD_FILENAME}"):
        if record_path.parent.name == trade_id:
            return record_path
    return None


def _trade_dir(
    ticker: str,
    trade_id: str,
    *,
    reports_dir: Path | None = None,
) -> Path:
    root = get_trade_feedback_root(reports_dir)
    trade_dir = (root / _normalize_ticker(ticker) / trade_id).resolve()
    try:
        trade_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(
            "Trade feedback directory must remain inside the feedback root"
        ) from exc
    return trade_dir


def _write_trade_record(
    record: dict[str, Any],
    *,
    reports_dir: Path | None = None,
    previous_ticker: str | None = None,
) -> None:
    current_dir = _trade_dir(
        record["ticker"], record["trade_id"], reports_dir=reports_dir
    )
    if previous_ticker and previous_ticker != record["ticker"]:
        previous_dir = _trade_dir(
            previous_ticker, record["trade_id"], reports_dir=reports_dir
        )
        if previous_dir.is_dir():
            current_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(previous_dir), str(current_dir))
    current_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(current_dir / TRADE_RECORD_FILENAME, record)


def _write_trade_review(
    review: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> None:
    reviews_dir = (
        _trade_dir(review["ticker"], review["trade_id"], reports_dir=reports_dir)
        / "reviews"
    )
    reviews_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(reviews_dir / f"{review['review_type']}.json", review)


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    fenced_match = re.search(
        r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",
        raw_text,
        flags=re.IGNORECASE,
    )
    candidates = [fenced_match.group(1)] if fenced_match else []
    candidates.append(raw_text.strip())
    decoder = json.JSONDecoder()

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    raise ValueError("Model output did not contain a valid JSON object")


def _normalize_ticker(value: Any) -> str:
    return normalize_ticker_symbol(value)


def _normalize_optional_text(value: Any) -> str:
    return normalize_field_optional_text(value, empty_value="") or ""


def _normalize_optional_number(value: Any, field_name: str) -> float | None:
    return normalize_field_optional_number(value, field_name)


def _normalize_optional_timestamp(value: Any, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from exc
    return parsed.isoformat()


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        raise ValueError(f"{field_name} must be a list of strings")
    return [item for item in items if item]


def _calculate_realized_return_pct(record: dict[str, Any]) -> float | None:
    entry_price = record.get("entry_price")
    exit_price = record.get("exit_price")
    if entry_price in (None, 0) or exit_price is None:
        return None

    direction = -1.0 if str(record.get("side", "")).lower() == "short" else 1.0
    return round(
        ((float(exit_price) - float(entry_price)) / float(entry_price))
        * 100
        * direction,
        4,
    )


def calculate_derived_metrics(record: dict[str, Any]) -> dict[str, Any]:
    realized_return_pct = _calculate_realized_return_pct(record)
    entry_price = record.get("entry_price")
    exit_price = record.get("exit_price")
    size = record.get("size")
    stop_loss = record.get("stop_loss")
    direction = -1.0 if str(record.get("side", "")).lower() == "short" else 1.0
    pnl_amount = None
    r_multiple = None
    if entry_price is not None and exit_price is not None and size is not None:
        pnl_amount = round(
            (float(exit_price) - float(entry_price)) * float(size) * direction, 4
        )
    if entry_price is not None and exit_price is not None and stop_loss is not None:
        risk_per_unit = abs(float(entry_price) - float(stop_loss))
        if risk_per_unit > 0:
            reward_per_unit = (float(exit_price) - float(entry_price)) * direction
            r_multiple = round(reward_per_unit / risk_per_unit, 4)
    return {
        "realized_return_pct": realized_return_pct,
        "pnl_amount": pnl_amount,
        "r_multiple": r_multiple,
        "holding_period_hours": _holding_period_hours(record),
    }


def _holding_period_hours(record: dict[str, Any]) -> float | None:
    entry_timestamp = record.get("entry_timestamp")
    exit_timestamp = record.get("exit_timestamp")
    if not entry_timestamp or not exit_timestamp:
        return None
    try:
        entry_dt = datetime.fromisoformat(str(entry_timestamp).replace("Z", "+00:00"))
        exit_dt = datetime.fromisoformat(str(exit_timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((exit_dt - entry_dt).total_seconds() / 3600, 4)


def _resolve_trade_market(payload: dict[str, Any]) -> dict[str, Any]:
    market_resolution = payload.get("market_resolution")
    raw_symbol = payload.get("raw_symbol")
    if isinstance(market_resolution, dict):
        raw_symbol = raw_symbol or market_resolution.get("raw_symbol")
    raw_symbol = _require_text(raw_symbol, "raw_symbol")
    if (
        isinstance(market_resolution, dict)
        and market_resolution.get("source") == "manual"
    ):
        return resolve_symbol(
            raw_symbol,
            manual_market=market_resolution.get("market"),
            manual_exchange=market_resolution.get("exchange"),
            manual_asset_type=market_resolution.get("asset_type"),
        )
    return resolve_symbol(raw_symbol)


def _resolve_feedback_ticker(value: Any) -> str:
    try:
        return _normalize_ticker(resolve_symbol(value)["canonical_symbol"])
    except ValueError:
        return _normalize_ticker(value)


def _exchange_or_market(market_resolution: dict[str, Any]) -> str:
    exchange = market_resolution.get("exchange")
    if exchange:
        return str(exchange)
    return str(market_resolution.get("market") or "unknown").upper()


def _derive_trade_status(exit_timestamp: Any, exit_price: Any) -> str:
    return "closed" if exit_timestamp or exit_price is not None else "open"


def _normalize_required_number(value: Any, field_name: str) -> float:
    parsed = _normalize_optional_number(value, field_name)
    if parsed is None:
        raise ValueError(f"{field_name} is required")
    return parsed


def _normalize_side(value: Any) -> str:
    side = _require_text(value, "side").lower()
    if side not in {"long", "short"}:
        raise ValueError("side must be long or short")
    return side


def _normalize_planned_horizon(value: Any) -> str:
    horizon = _normalize_optional_text(value).lower() or "unknown"
    if horizon not in PLANNED_HORIZONS:
        raise ValueError(
            "planned_horizon must be one of " + ", ".join(sorted(PLANNED_HORIZONS))
        )
    return horizon


def _normalize_plan_execution(value: Any) -> str:
    plan_execution = _normalize_optional_text(value).lower() or "unknown"
    if plan_execution not in PLAN_EXECUTIONS:
        raise ValueError(
            "plan_execution must be one of " + ", ".join(sorted(PLAN_EXECUTIONS))
        )
    return plan_execution


def _normalize_strategy_tags(value: Any) -> list[str]:
    tags = _normalize_string_list(value, "strategy_tags")
    normalized: list[str] = []
    for tag in tags:
        parsed = re.sub(r"[^a-z0-9_]+", "_", tag.strip().lower()).strip("_")
        if parsed and parsed not in normalized:
            normalized.append(parsed)
    if not normalized:
        raise ValueError("strategy_tags must contain at least one tag")
    return normalized


def _normalize_initial_thesis(payload: dict[str, Any]) -> str:
    initial_thesis = _normalize_optional_text(payload.get("initial_thesis"))
    return initial_thesis or _require_text(payload.get("entry_reason"), "entry_reason")


def _validate_trade_record(record: dict[str, Any]) -> None:
    _require_text(record.get("raw_symbol"), "raw_symbol")
    _require_text(record.get("entry_timestamp"), "entry_timestamp")
    _normalize_required_number(record.get("entry_price"), "entry_price")
    _normalize_required_number(record.get("size"), "size")
    strategy_tags = _normalize_strategy_tags(record.get("strategy_tags"))
    record["strategy_tags"] = strategy_tags
    entry_reason = _require_text(record.get("entry_reason"), "entry_reason")
    _require_text(record.get("invalidation_condition"), "invalidation_condition")
    if strategy_tags == ["other"] and len(entry_reason) < 12:
        raise ValueError("other strategy_tags require a specific entry_reason")
    if record.get("exit_timestamp") or record.get("exit_price") is not None:
        _require_text(record.get("exit_reason"), "exit_reason")
        plan_execution = _normalize_plan_execution(record.get("plan_execution"))
        if plan_execution in {"unknown", "not_applicable"}:
            raise ValueError("plan_execution is required when exit fields are set")


def _require_text(value: Any, field_name: str) -> str:
    return require_field_text(value, field_name)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


__all__ = [
    "TRADE_FEEDBACK_DIRNAME",
    "calculate_derived_metrics",
    "create_trade_record",
    "generate_trade_review",
    "get_trade_feedback_payload",
    "get_trade_feedback_root",
    "get_trade_record",
    "list_trade_feedback_entries",
    "list_trade_records",
    "list_trade_reviews",
    "save_trade_review",
    "update_trade_record",
]
