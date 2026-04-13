from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tradingagents.llm_clients import create_llm_client
from tradingagents.llm_clients.model_config import get_provider_base_url


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADE_FEEDBACK_DIRNAME = ".trade_feedback"
REVIEW_TYPES = {"entry_review", "exit_review"}
TRADE_RECORD_FILENAME = "trade_record.json"


def get_trade_feedback_root(reports_dir: Path | None = None) -> Path:
    base_dir = (
        Path(reports_dir).resolve()
        if reports_dir is not None
        else Path(os.environ.get("REPORTS_DIR", PROJECT_ROOT / "reports")).resolve()
    )
    return base_dir / TRADE_FEEDBACK_DIRNAME


def create_trade_record(
    payload: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    ticker = _normalize_ticker(payload.get("ticker"))
    trade_id = uuid.uuid4().hex
    record = {
        "type": "trade_record",
        "schema_version": 1,
        "trade_id": trade_id,
        "ticker": ticker,
        "exchange_or_market": _require_text(
            payload.get("exchange_or_market"), "exchange_or_market"
        ),
        "side": _require_text(payload.get("side"), "side").lower(),
        "status": _require_text(payload.get("status"), "status"),
        "entry_timestamp": _normalize_optional_timestamp(
            payload.get("entry_timestamp"), "entry_timestamp"
        ),
        "entry_price": _normalize_optional_number(
            payload.get("entry_price"), "entry_price"
        ),
        "exit_timestamp": _normalize_optional_timestamp(
            payload.get("exit_timestamp"), "exit_timestamp"
        ),
        "exit_price": _normalize_optional_number(
            payload.get("exit_price"), "exit_price"
        ),
        "size": _normalize_optional_number(payload.get("size"), "size"),
        "initial_thesis": _require_text(payload.get("initial_thesis"), "initial_thesis"),
        "planned_horizon": _require_text(
            payload.get("planned_horizon"), "planned_horizon"
        ),
        "stop_loss": _normalize_optional_number(payload.get("stop_loss"), "stop_loss"),
        "take_profit": _normalize_optional_number(
            payload.get("take_profit"), "take_profit"
        ),
        "notes": _normalize_optional_text(payload.get("notes")),
        "analysis_references": _normalize_analysis_references(
            payload.get("analysis_references") or []
        ),
        "created_at": now,
        "updated_at": now,
    }
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

    if "ticker" in updates and updates["ticker"] is not None:
        updated["ticker"] = _normalize_ticker(updates["ticker"])
    if "exchange_or_market" in updates and updates["exchange_or_market"] is not None:
        updated["exchange_or_market"] = _require_text(
            updates["exchange_or_market"], "exchange_or_market"
        )
    if "side" in updates and updates["side"] is not None:
        updated["side"] = _require_text(updates["side"], "side").lower()
    if "status" in updates and updates["status"] is not None:
        updated["status"] = _require_text(updates["status"], "status")
    if "entry_timestamp" in updates:
        updated["entry_timestamp"] = _normalize_optional_timestamp(
            updates.get("entry_timestamp"), "entry_timestamp"
        )
    if "entry_price" in updates:
        updated["entry_price"] = _normalize_optional_number(
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
    if "initial_thesis" in updates and updates["initial_thesis"] is not None:
        updated["initial_thesis"] = _require_text(
            updates["initial_thesis"], "initial_thesis"
        )
    if "planned_horizon" in updates and updates["planned_horizon"] is not None:
        updated["planned_horizon"] = _require_text(
            updates["planned_horizon"], "planned_horizon"
        )
    if "stop_loss" in updates:
        updated["stop_loss"] = _normalize_optional_number(
            updates.get("stop_loss"), "stop_loss"
        )
    if "take_profit" in updates:
        updated["take_profit"] = _normalize_optional_number(
            updates.get("take_profit"), "take_profit"
        )
    if "notes" in updates:
        updated["notes"] = _normalize_optional_text(updates.get("notes"))
    if "analysis_references" in updates:
        updated["analysis_references"] = _normalize_analysis_references(
            updates.get("analysis_references") or []
        )

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
            results.append(_read_json_file(record_path))

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
    return _read_json_file(record_path)


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
            reviews.append(_read_json_file(review_path))
    reviews.sort(key=lambda review: review.get("updated_at", ""), reverse=True)
    return reviews


def get_trade_feedback_payload(
    ticker: str,
    *,
    reports_dir: Path | None = None,
    limit: int = 3,
    analysis_date: str | None = None,
) -> dict[str, Any]:
    normalized_ticker = _normalize_ticker(ticker)
    entries = list_trade_feedback_entries(
        normalized_ticker,
        reports_dir=reports_dir,
    )
    if analysis_date is not None:
        normalized_analysis_date = _normalize_analysis_date(analysis_date)
        entries = [
            entry
            for entry in entries
            if _review_visibility_date(entry) <= normalized_analysis_date
        ]
    selected_entries = entries[:limit] if limit > 0 else entries
    return {
        "ticker": normalized_ticker,
        "reviews": selected_entries,
        "prompt": _build_feedback_prompt(normalized_ticker, selected_entries),
    }


def list_trade_feedback_entries(
    ticker: str,
    *,
    reports_dir: Path | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for record in list_trade_records(ticker=ticker, reports_dir=reports_dir):
        for review in list_trade_reviews(record["trade_id"], reports_dir=reports_dir):
            results.append(
                {
                    "trade_id": record["trade_id"],
                    "ticker": record["ticker"],
                    "exchange_or_market": record["exchange_or_market"],
                    "side": record["side"],
                    "status": record["status"],
                    "entry_timestamp": record.get("entry_timestamp"),
                    "entry_price": record.get("entry_price"),
                    "exit_timestamp": record.get("exit_timestamp"),
                    "exit_price": record.get("exit_price"),
                    "size": record.get("size"),
                    "initial_thesis": record.get("initial_thesis"),
                    "planned_horizon": record.get("planned_horizon"),
                    "stop_loss": record.get("stop_loss"),
                    "take_profit": record.get("take_profit"),
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
    llm: Any = None,
) -> dict[str, Any]:
    normalized_review_type = _normalize_review_type(review_type)
    trade_record = get_trade_record(trade_id, reports_dir=reports_dir)
    snapshot_references = _normalize_analysis_references(
        analysis_references
        if analysis_references is not None
        else trade_record.get("analysis_references") or []
    )
    if not snapshot_references:
        raise ValueError(
            "Review generation requires at least one analysis reference with complete_report and full state log paths"
        )

    prompt = _build_review_prompt(
        trade_record,
        normalized_review_type,
        snapshot_references,
        output_language=output_language,
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
    if not snapshot_references:
        raise ValueError(
            "Review saving requires at least one analysis reference with complete_report and full state log paths"
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
) -> str:
    trade_context = {
        "trade_id": trade_record["trade_id"],
        "ticker": trade_record["ticker"],
        "exchange_or_market": trade_record["exchange_or_market"],
        "side": trade_record["side"],
        "status": trade_record["status"],
        "entry_timestamp": trade_record.get("entry_timestamp"),
        "entry_price": trade_record.get("entry_price"),
        "exit_timestamp": trade_record.get("exit_timestamp"),
        "exit_price": trade_record.get("exit_price"),
        "size": trade_record.get("size"),
        "initial_thesis": trade_record.get("initial_thesis"),
        "planned_horizon": trade_record.get("planned_horizon"),
        "stop_loss": trade_record.get("stop_loss"),
        "take_profit": trade_record.get("take_profit"),
        "notes": trade_record.get("notes"),
        "realized_return_pct": _calculate_realized_return_pct(trade_record),
    }

    snapshot_context = [_load_snapshot_context(reference) for reference in analysis_references]
    review_focus = (
        "This is an entry review. Judge the quality of the thesis, timing, sizing, and discipline mostly from information available at or before entry. If later outcome information exists, use it carefully as calibration rather than the primary verdict."
        if review_type == "entry_review"
        else "This is an exit review. Judge the quality of the exit decision relative to the initial thesis, stated horizon, risk limits, and what changed. Realized PnL matters, but it cannot be the sole basis of the review."
    )
    language_instruction = (
        "Write free-form string values in Simplified Chinese."
        if output_language.lower() == "cn"
        else "Write free-form string values in English."
    )

    return f"""You are writing a structured trade review for a manual trading journal.

{review_focus}

Guardrails:
- Do not reduce the review to PnL alone.
- Separate process quality from realized outcome.
- Avoid obvious hindsight bias. If a point depends on information that was unavailable at the time, say so explicitly.
- Anchor every conclusion in the trade record or the attached analysis snapshots.

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

Return exactly one JSON object and nothing else. Use this schema exactly:
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

Requirements:
- Keep the JSON keys in English exactly as shown.
- Each assessment field must be specific and evidence-based.
- `improvement_actions` must contain concrete next-time actions.
- `ticker_specific_lessons` should be lessons that apply directly to this ticker or setup.
- `cross_ticker_tags` should be short reusable tags like `earnings_gap_risk` or `late_breakout_entry`.
- {language_instruction}
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
    elif isinstance(existing_review, dict) and existing_review.get("analysis_references"):
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
    return max(reference["analysis_date"] for reference in analysis_references)


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
    full_state_log_path = _resolve_project_path(reference["full_state_log_path"])

    complete_report = complete_report_path.read_text(encoding="utf-8")
    full_state_payload = json.loads(full_state_log_path.read_text(encoding="utf-8"))

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

    state_excerpt = {}
    if isinstance(selected_state, dict):
        for key in (
            "trade_date",
            "market_report",
            "sentiment_report",
            "news_report",
            "fundamentals_report",
            "investment_plan",
            "trader_investment_decision",
            "final_trade_decision",
        ):
            value = selected_state.get(key)
            if value:
                state_excerpt[key] = value
    else:
        state_excerpt["raw_value"] = selected_state

    return {
        "analysis_date": reference["analysis_date"],
        "report_path": reference["report_path"],
        "full_state_log_path": reference["full_state_log_path"],
        "complete_report": complete_report,
        "full_state_excerpt": state_excerpt,
    }


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
        full_state_log_path = _normalize_project_relative_path(
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
    text = _require_text(value, "analysis_date")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("analysis_date must use YYYY-MM-DD format") from exc
    return text


def _normalize_project_relative_path(value: Any, field_name: str) -> str:
    project_root = PROJECT_ROOT.resolve()
    resolved = _resolve_project_path(_require_text(value, field_name))
    if not resolved.is_file():
        raise ValueError(f"{field_name} does not point to an existing file")
    return resolved.relative_to(project_root).as_posix()


def _resolve_project_path(value: str) -> Path:
    project_root = PROJECT_ROOT.resolve()
    raw_path = Path(value)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Analysis references must remain inside the project directory") from exc
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
    return get_trade_feedback_root(reports_dir) / _normalize_ticker(ticker) / trade_id


def _write_trade_record(
    record: dict[str, Any],
    *,
    reports_dir: Path | None = None,
    previous_ticker: str | None = None,
) -> None:
    current_dir = _trade_dir(record["ticker"], record["trade_id"], reports_dir=reports_dir)
    if previous_ticker and previous_ticker != record["ticker"]:
        previous_dir = _trade_dir(previous_ticker, record["trade_id"], reports_dir=reports_dir)
        if previous_dir.is_dir():
            current_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(previous_dir), str(current_dir))
    current_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(current_dir / TRADE_RECORD_FILENAME, record)


def _write_trade_review(
    review: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> None:
    reviews_dir = _trade_dir(review["ticker"], review["trade_id"], reports_dir=reports_dir) / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(reviews_dir / f"{review['review_type']}.json", review)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    ticker = _require_text(value, "ticker").upper()
    return ticker


def _normalize_optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_optional_number(value: Any, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


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
    return round(((float(exit_price) - float(entry_price)) / float(entry_price)) * 100 * direction, 4)


def _require_text(value: Any, field_name: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


__all__ = [
    "TRADE_FEEDBACK_DIRNAME",
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
