from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from diverge.common.fields import (
    normalize_optional_number as normalize_field_optional_number,
    normalize_optional_text as normalize_field_optional_text,
    require_text as require_field_text,
)
from diverge.common.json_io import read_json_file, write_json_atomic
from diverge.common.symbols import normalize_ticker_symbol
from diverge.markets import resolve_symbol
from diverge.trade_feedback import (
    PLANNED_HORIZONS,
    _normalize_analysis_references as normalize_trade_analysis_references,
    get_trade_feedback_root,
)

TRADE_PLAN_DIRNAME = ".trade_plans"
TRADE_PLAN_FILENAME = "trade_plan.json"
TRADE_PLAN_SCHEMA_VERSION = 1
TRADE_PLAN_STATUSES = {"planned", "executed", "expired"}
TRADE_PLAN_SOURCES = {"manual", "analysis_prefill"}
STATUS_REASON_AWAITING_EXECUTION = "awaiting_execution"
STATUS_REASON_LINKED_TO_TRADE_RECORD = "linked_to_trade_record"
STATUS_REASON_NOT_EXECUTED_BEFORE_EXPIRY = "not_executed_before_expiry"


def get_trade_plan_root(reports_dir: Path | None = None) -> Path:
    return get_trade_feedback_root(reports_dir) / TRADE_PLAN_DIRNAME


def create_trade_plan(
    payload: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    market_resolution = _resolve_plan_market(payload)
    ticker = _normalize_ticker(market_resolution["canonical_symbol"])
    plan_id = uuid.uuid4().hex
    plan = {
        "type": "trade_plan",
        "schema_version": TRADE_PLAN_SCHEMA_VERSION,
        "plan_id": plan_id,
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
        "status": "planned",
        "status_reason": STATUS_REASON_AWAITING_EXECUTION,
        "source": _normalize_source(payload.get("source")),
        "strategy_tags": _normalize_strategy_tags(payload.get("strategy_tags")),
        "entry_condition": _require_text(
            payload.get("entry_condition"), "entry_condition"
        ),
        "thesis": _require_text(payload.get("thesis"), "thesis"),
        "invalidation_condition": _require_text(
            payload.get("invalidation_condition"), "invalidation_condition"
        ),
        "risk_rule": _require_text(payload.get("risk_rule"), "risk_rule"),
        "reward_target": _require_text(
            payload.get("reward_target"), "reward_target"
        ),
        "position_plan": _require_text(
            payload.get("position_plan"), "position_plan"
        ),
        "planned_horizon": _normalize_planned_horizon(
            payload.get("planned_horizon")
        ),
        "stop_loss": _normalize_optional_number(payload.get("stop_loss"), "stop_loss"),
        "take_profit": _normalize_optional_number(
            payload.get("take_profit"), "take_profit"
        ),
        "expires_at": _normalize_timestamp(payload.get("expires_at"), "expires_at"),
        "notes": _normalize_optional_text(payload.get("notes")),
        "analysis_references": _normalize_analysis_references(
            payload.get("analysis_references") or []
        ),
        "linked_trade_id": "",
        "created_at": now,
        "updated_at": now,
    }
    _validate_trade_plan(plan)
    _write_trade_plan(plan, reports_dir=reports_dir)
    return plan


def update_trade_plan(
    plan_id: str,
    updates: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    existing = get_trade_plan(plan_id, reports_dir=reports_dir)
    updated = dict(existing)
    previous_ticker = existing["ticker"]
    baseline_locked = updated.get("status") == "executed"

    if baseline_locked:
        _reject_executed_baseline_updates(updates)

    if "raw_symbol" in updates or "market_resolution" in updates:
        market_resolution = _resolve_plan_market(
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
    if "source" in updates and updates["source"] is not None:
        updated["source"] = _normalize_source(updates["source"])
    if "strategy_tags" in updates and updates["strategy_tags"] is not None:
        updated["strategy_tags"] = _normalize_strategy_tags(
            updates.get("strategy_tags")
        )
    for field_name in (
        "entry_condition",
        "thesis",
        "invalidation_condition",
        "risk_rule",
        "reward_target",
        "position_plan",
    ):
        if field_name in updates and updates[field_name] is not None:
            updated[field_name] = _require_text(updates[field_name], field_name)
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
    if "expires_at" in updates and updates["expires_at"] is not None:
        updated["expires_at"] = _normalize_timestamp(
            updates.get("expires_at"), "expires_at"
        )
    if "notes" in updates:
        updated["notes"] = _normalize_optional_text(updates.get("notes"))
    if "analysis_references" in updates:
        updated["analysis_references"] = _normalize_analysis_references(
            updates.get("analysis_references") or []
        )

    updated["schema_version"] = TRADE_PLAN_SCHEMA_VERSION
    _validate_trade_plan(updated)
    updated["updated_at"] = _now_iso()
    _write_trade_plan(updated, reports_dir=reports_dir, previous_ticker=previous_ticker)
    return updated


def list_trade_plans(
    *,
    ticker: str | None = None,
    status: str | None = None,
    reports_dir: Path | None = None,
) -> list[dict[str, Any]]:
    root = get_trade_plan_root(reports_dir)
    if not root.is_dir():
        return []

    if ticker:
        search_roots = [root / _normalize_ticker(ticker)]
    else:
        search_roots = [path for path in root.iterdir() if path.is_dir()]

    normalized_status = _normalize_optional_status(status)
    results: list[dict[str, Any]] = []
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for plan_path in sorted(search_root.glob(f"*/{TRADE_PLAN_FILENAME}")):
            plan = _materialize_status(read_json_file(plan_path), reports_dir=reports_dir)
            if normalized_status and plan.get("status") != normalized_status:
                continue
            results.append(plan)

    results.sort(
        key=lambda plan: (
            plan.get("expires_at", ""),
            plan.get("updated_at", ""),
            plan.get("plan_id", ""),
        )
    )
    return results


def get_trade_plan(
    plan_id: str,
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    plan_path = _find_trade_plan_path(plan_id, reports_dir=reports_dir)
    if plan_path is None:
        raise ValueError(f"Trade plan '{plan_id}' not found")
    return _materialize_status(read_json_file(plan_path), reports_dir=reports_dir)


def delete_trade_plan(
    plan_id: str,
    *,
    reports_dir: Path | None = None,
) -> None:
    plan = get_trade_plan(plan_id, reports_dir=reports_dir)
    if plan.get("status") == "executed":
        raise ValueError("executed trade plans cannot be deleted")
    plan_dir = _plan_dir(plan["ticker"], plan_id, reports_dir=reports_dir)
    if plan_dir.is_dir():
        shutil.rmtree(plan_dir)


def build_execution_trade_payload(
    plan: dict[str, Any],
    execution_payload: dict[str, Any],
) -> dict[str, Any]:
    notes = _normalize_optional_text(execution_payload.get("notes"))
    execution_note = _normalize_optional_text(execution_payload.get("execution_note"))
    return {
        "raw_symbol": plan["raw_symbol"],
        "side": plan["side"],
        "entry_timestamp": execution_payload.get("entry_timestamp"),
        "entry_price": execution_payload.get("entry_price"),
        "size": execution_payload.get("size"),
        "strategy_tags": list(plan.get("strategy_tags") or []),
        "entry_reason": plan.get("entry_condition") or plan.get("thesis"),
        "invalidation_condition": plan.get("invalidation_condition")
        or plan.get("risk_rule"),
        "planned_horizon": plan.get("planned_horizon"),
        "stop_loss": plan.get("stop_loss"),
        "take_profit": plan.get("take_profit"),
        "exit_timestamp": execution_payload.get("exit_timestamp"),
        "exit_price": execution_payload.get("exit_price"),
        "exit_reason": _normalize_optional_text(execution_payload.get("exit_reason")),
        "plan_execution": _normalize_optional_text(
            execution_payload.get("plan_execution")
        )
        or "unknown",
        "initial_thesis": plan.get("thesis"),
        "notes": notes,
        "execution_note": execution_note,
        "market_resolution": plan.get("market_resolution"),
        "analysis_references": list(plan.get("analysis_references") or []),
        "originating_plan_id": plan["plan_id"],
        "originating_plan_snapshot": build_trade_plan_snapshot(plan),
    }


def validate_plan_link(plan: dict[str, Any], record: dict[str, Any]) -> None:
    if plan.get("status") == "executed":
        if plan.get("linked_trade_id") != record.get("trade_id"):
            raise ValueError("trade plan has already been executed")
    if record.get("originating_plan_id") and record.get("originating_plan_id") != plan.get(
        "plan_id"
    ):
        raise ValueError("trade record is already linked to a trade plan")
    if _normalize_ticker(plan.get("ticker")) != _normalize_ticker(record.get("ticker")):
        raise ValueError("trade plan and trade record symbols must match")
    if str(plan.get("side", "")).lower() != str(record.get("side", "")).lower():
        raise ValueError("trade plan and trade record sides must match")

    entry_timestamp = _parse_datetime(record.get("entry_timestamp"), "entry_timestamp")
    expires_at = _parse_datetime(plan.get("expires_at"), "expires_at")
    if entry_timestamp > expires_at:
        raise ValueError("trade entry time is after the trade plan expiry")


def mark_trade_plan_executed(
    plan_id: str,
    trade_id: str,
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    plan = get_trade_plan(plan_id, reports_dir=reports_dir)
    if plan.get("status") == "executed" and plan.get("linked_trade_id") != trade_id:
        raise ValueError("trade plan has already been executed")
    plan["status"] = "executed"
    plan["status_reason"] = STATUS_REASON_LINKED_TO_TRADE_RECORD
    plan["linked_trade_id"] = trade_id
    plan["updated_at"] = _now_iso()
    _write_trade_plan(plan, reports_dir=reports_dir)
    return plan


def build_trade_plan_snapshot(plan: dict[str, Any]) -> dict[str, Any]:
    snapshot_fields = (
        "plan_id",
        "raw_symbol",
        "ticker",
        "canonical_symbol",
        "display_symbol",
        "market",
        "exchange",
        "asset_type",
        "exchange_or_market",
        "market_resolution",
        "side",
        "source",
        "strategy_tags",
        "entry_condition",
        "thesis",
        "invalidation_condition",
        "risk_rule",
        "reward_target",
        "position_plan",
        "planned_horizon",
        "stop_loss",
        "take_profit",
        "expires_at",
        "analysis_references",
        "created_at",
        "updated_at",
    )
    return {
        "type": "trade_plan_snapshot",
        "schema_version": TRADE_PLAN_SCHEMA_VERSION,
        **{field: plan.get(field) for field in snapshot_fields},
        "snapshotted_at": _now_iso(),
    }


def _materialize_status(
    plan: dict[str, Any],
    *,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    if plan.get("status") != "planned":
        return plan
    expires_at = _parse_datetime(plan.get("expires_at"), "expires_at")
    if expires_at >= _now_datetime():
        return plan
    updated = dict(plan)
    updated["status"] = "expired"
    updated["status_reason"] = STATUS_REASON_NOT_EXECUTED_BEFORE_EXPIRY
    updated["updated_at"] = _now_iso()
    _write_trade_plan(updated, reports_dir=reports_dir)
    return updated


def _reject_executed_baseline_updates(updates: dict[str, Any]) -> None:
    baseline_fields = {
        "raw_symbol",
        "market_resolution",
        "side",
        "strategy_tags",
        "entry_condition",
        "thesis",
        "invalidation_condition",
        "risk_rule",
        "reward_target",
        "position_plan",
        "planned_horizon",
        "stop_loss",
        "take_profit",
        "expires_at",
        "analysis_references",
    }
    touched = sorted(field for field in baseline_fields if field in updates)
    if touched:
        raise ValueError(
            "executed trade plan baseline fields are immutable: "
            + ", ".join(touched)
        )


def _find_trade_plan_path(
    plan_id: str,
    *,
    reports_dir: Path | None = None,
) -> Path | None:
    root = get_trade_plan_root(reports_dir)
    if not root.is_dir():
        return None
    for plan_path in root.glob(f"*/*/{TRADE_PLAN_FILENAME}"):
        if plan_path.parent.name == plan_id:
            return plan_path
    return None


def _plan_dir(
    ticker: str,
    plan_id: str,
    *,
    reports_dir: Path | None = None,
) -> Path:
    root = get_trade_plan_root(reports_dir)
    plan_dir = (root / _normalize_ticker(ticker) / plan_id).resolve()
    try:
        plan_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Trade plan directory must remain inside the plan root") from exc
    return plan_dir


def _write_trade_plan(
    plan: dict[str, Any],
    *,
    reports_dir: Path | None = None,
    previous_ticker: str | None = None,
) -> None:
    current_dir = _plan_dir(plan["ticker"], plan["plan_id"], reports_dir=reports_dir)
    if previous_ticker and previous_ticker != plan["ticker"]:
        previous_dir = _plan_dir(
            previous_ticker, plan["plan_id"], reports_dir=reports_dir
        )
        if previous_dir.is_dir():
            current_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(previous_dir), str(current_dir))
    current_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(current_dir / TRADE_PLAN_FILENAME, plan)


def _resolve_plan_market(payload: dict[str, Any]) -> dict[str, Any]:
    market_resolution = payload.get("market_resolution")
    raw_symbol = payload.get("raw_symbol")
    if isinstance(market_resolution, dict):
        raw_symbol = raw_symbol or market_resolution.get("raw_symbol")
    raw_symbol = _require_text(raw_symbol, "raw_symbol")
    if isinstance(market_resolution, dict) and market_resolution.get("source") == "manual":
        return resolve_symbol(
            raw_symbol,
            manual_market=market_resolution.get("market"),
            manual_exchange=market_resolution.get("exchange"),
            manual_asset_type=market_resolution.get("asset_type"),
        )
    return resolve_symbol(raw_symbol)


def _exchange_or_market(market_resolution: dict[str, Any]) -> str:
    exchange = market_resolution.get("exchange")
    if exchange:
        return str(exchange)
    return str(market_resolution.get("market") or "unknown").upper()


def _normalize_source(value: Any) -> str:
    source = _normalize_optional_text(value).lower() or "manual"
    if source not in TRADE_PLAN_SOURCES:
        raise ValueError(
            "source must be one of " + ", ".join(sorted(TRADE_PLAN_SOURCES))
        )
    return source


def _normalize_optional_status(value: Any) -> str | None:
    text = _normalize_optional_text(value).lower()
    if not text:
        return None
    if text not in TRADE_PLAN_STATUSES:
        raise ValueError(
            "status must be one of " + ", ".join(sorted(TRADE_PLAN_STATUSES))
        )
    return text


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


def _normalize_strategy_tags(value: Any) -> list[str]:
    tags = _normalize_string_list(value, "strategy_tags")
    normalized: list[str] = []
    for tag in tags:
        parsed = "_".join(str(tag).strip().lower().replace("-", "_").split())
        parsed = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in parsed)
        parsed = "_".join(part for part in parsed.split("_") if part)
        if parsed and parsed not in normalized:
            normalized.append(parsed)
    if not normalized:
        raise ValueError("strategy_tags must contain at least one tag")
    return normalized


def _normalize_analysis_references(
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return normalize_trade_analysis_references(references)


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


def _normalize_timestamp(value: Any, field_name: str) -> str:
    text = _require_text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _parse_datetime(value: Any, field_name: str) -> datetime:
    parsed = datetime.fromisoformat(_normalize_timestamp(value, field_name))
    return parsed.astimezone(timezone.utc)


def _validate_trade_plan(plan: dict[str, Any]) -> None:
    _require_text(plan.get("raw_symbol"), "raw_symbol")
    _normalize_side(plan.get("side"))
    _normalize_status(plan.get("status"))
    _normalize_source(plan.get("source"))
    _normalize_strategy_tags(plan.get("strategy_tags"))
    for field_name in (
        "entry_condition",
        "thesis",
        "invalidation_condition",
        "risk_rule",
        "reward_target",
        "position_plan",
    ):
        _require_text(plan.get(field_name), field_name)
    _normalize_planned_horizon(plan.get("planned_horizon"))
    _parse_datetime(plan.get("expires_at"), "expires_at")
    if plan.get("status") == "executed" and not _normalize_optional_text(
        plan.get("linked_trade_id")
    ):
        raise ValueError("executed trade plans require linked_trade_id")


def _normalize_status(value: Any) -> str:
    status = _require_text(value, "status").lower()
    if status not in TRADE_PLAN_STATUSES:
        raise ValueError(
            "status must be one of " + ", ".join(sorted(TRADE_PLAN_STATUSES))
        )
    return status


def _normalize_ticker(value: Any) -> str:
    return normalize_ticker_symbol(value)


def _normalize_optional_text(value: Any) -> str:
    return normalize_field_optional_text(value, empty_value="") or ""


def _normalize_optional_number(value: Any, field_name: str) -> float | None:
    return normalize_field_optional_number(value, field_name)


def _require_text(value: Any, field_name: str) -> str:
    return require_field_text(value, field_name)


def _now_datetime() -> datetime:
    return datetime.fromisoformat(_now_iso()).astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "TRADE_PLAN_FILENAME",
    "build_execution_trade_payload",
    "build_trade_plan_snapshot",
    "create_trade_plan",
    "delete_trade_plan",
    "get_trade_plan",
    "get_trade_plan_root",
    "list_trade_plans",
    "mark_trade_plan_executed",
    "update_trade_plan",
    "validate_plan_link",
]
