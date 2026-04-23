from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request

from tradingagents.assets.market_data import MarketDataClient, SymbolCandidate
from web.backend import access, asset_entries, auth
from web.backend.schemas.assets import AssetPositionCreatePayload, AssetPositionUpdatePayload

REFRESH_INTERVAL = timedelta(minutes=15)
MARKET_VALUATION_MODE = "market"
MANUAL_VALUATION_MODE = "manual"


def build_market_data_client() -> MarketDataClient:
    return MarketDataClient()


def _serialize_datetime(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _require_asset_runtime() -> None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise HTTPException(
            status_code=409,
            detail="Assets require AUTH_ENABLED and the database-backed web runtime.",
        )


def translate_asset_error(exc: Exception) -> HTTPException:
    if isinstance(exc, auth.AuthNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, auth.AuthPermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, (auth.AuthValidationError, auth.AuthConflictError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, auth.AuthDisabledError):
        return HTTPException(status_code=409, detail=str(exc))
    detail = str(exc).strip() or "Unexpected asset service error"
    return HTTPException(status_code=500, detail=detail)


def _require_text(value: str | None, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise auth.AuthValidationError(f"{field_name} is required")
    return str(value).strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _normalize_upper(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    return normalized.upper() if normalized else None


def _normalize_valuation_mode(value: str | None) -> str:
    normalized = _require_text(value, "valuation_mode").lower()
    if normalized not in {MARKET_VALUATION_MODE, MANUAL_VALUATION_MODE}:
        raise auth.AuthValidationError("valuation_mode must be either 'market' or 'manual'")
    return normalized


def _coerce_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_compare_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _auto_select_candidate(asset_name: str, candidates: list[SymbolCandidate]) -> SymbolCandidate | None:
    if len(candidates) == 1:
        return candidates[0]
    normalized_name = _normalize_compare_text(asset_name)
    exact_matches = [
        candidate
        for candidate in candidates
        if _normalize_compare_text(candidate.name) == normalized_name
        or _normalize_compare_text(candidate.ticker) == normalized_name
    ]
    return exact_matches[0] if len(exact_matches) == 1 else None


def _serialize_position(
    position: asset_entries.AssetPosition,
    account: asset_entries.AssetAccount,
    latest_snapshot: asset_entries.AssetValuationSnapshot | None,
    *,
    base_currency: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = _coerce_now(now)
    normalized_base_currency = _normalize_upper(base_currency)
    snapshot_payload = asset_entries.serialize_asset_snapshot(latest_snapshot)
    is_stale = False
    if latest_snapshot is not None:
        same_currency = (
            normalized_base_currency is None
            or latest_snapshot.base_currency == normalized_base_currency
        )
        is_stale = (
            not same_currency
            or current_time - latest_snapshot.captured_at.astimezone(timezone.utc)
            >= REFRESH_INTERVAL
        )

    state = latest_snapshot.status if latest_snapshot is not None else (position.mapping_status or "unresolved")
    return {
        "id": position.id,
        "owner_user_id": position.owner_user_id,
        "account": asset_entries.serialize_asset_account(account),
        "asset_name": position.asset_name,
        "asset_category": position.asset_category,
        "quantity": position.quantity,
        "cost_basis": position.cost_basis,
        "valuation_mode": position.valuation_mode,
        "manual_price": position.manual_price,
        "ticker": position.ticker,
        "market": position.market,
        "exchange": position.exchange,
        "quote_type": position.quote_type,
        "resolved_name": position.resolved_name,
        "currency": position.quote_currency,
        "vendor": position.vendor,
        "mapping_status": position.mapping_status,
        "error_message": position.error_message,
        "notes": position.notes,
        "state": state,
        "is_stale": is_stale,
        "latest_snapshot": snapshot_payload,
        "created_at": _serialize_datetime(position.created_at),
        "updated_at": _serialize_datetime(position.updated_at),
    }


def _resolve_request_scope(db, request: Request | None) -> tuple[auth.User, str | None]:
    user = access.require_trade_request_user(db, request)
    assert user is not None
    return user, access.owner_scope_for_user(user)


def _list_position_payloads(
    db,
    *,
    owner_scope: str | None,
    base_currency: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    positions = asset_entries.list_asset_position_records(db, owner_user_id=owner_scope)
    accounts = {
        account.id: account
        for account in asset_entries.list_asset_account_records(db, owner_user_id=owner_scope)
    }
    latest_snapshots = asset_entries.list_latest_snapshots_by_position(db, [position.id for position in positions])
    payloads = [
        _serialize_position(
            position,
            accounts[position.account_id],
            latest_snapshots.get(position.id),
            base_currency=base_currency,
            now=now,
        )
        for position in positions
        if position.account_id in accounts
    ]
    payloads.sort(
        key=lambda item: (
            item["account"]["platform_name"].lower(),
            item["account"]["account_name"].lower(),
            item["asset_name"].lower(),
            item["id"],
        )
    )
    return payloads


def _resolve_mapping(position: asset_entries.AssetPosition, *, market_data: MarketDataClient) -> None:
    if position.valuation_mode != MARKET_VALUATION_MODE:
        position.mapping_status = "manual_only"
        position.error_message = None
        return

    if position.ticker:
        position.ticker = _normalize_upper(position.ticker)
        position.mapping_status = "resolved"
        position.error_message = None
        return

    candidates = market_data.search_symbols(position.asset_name, position.asset_category, limit=5)
    if not candidates:
        position.mapping_status = "unresolved"
        position.error_message = "No market matches found"
        return

    selected = _auto_select_candidate(position.asset_name, candidates)
    if selected is None:
        position.mapping_status = "ambiguous"
        position.error_message = f"{len(candidates)} candidates matched. Set ticker explicitly."
        return

    position.ticker = selected.ticker
    position.market = selected.market
    position.exchange = selected.exchange
    position.quote_type = selected.quote_type
    position.resolved_name = selected.name
    position.vendor = selected.vendor
    position.mapping_status = "resolved"
    position.error_message = None


def _get_fx_rate(
    market_data: MarketDataClient,
    *,
    quote_currency: str | None,
    base_currency: str,
) -> float:
    source_currency = _normalize_upper(quote_currency) or base_currency
    target_currency = _normalize_upper(base_currency) or "USD"
    if source_currency == target_currency:
        return 1.0
    fx_quote = market_data.get_fx_quote(source_currency, target_currency)
    return float(fx_quote.price)


def _refresh_manual_position(
    db,
    position: asset_entries.AssetPosition,
    *,
    base_currency: str,
    market_data: MarketDataClient,
    now: datetime,
) -> dict[str, Any]:
    if position.manual_price is None:
        snapshot = asset_entries.add_asset_snapshot(
            db,
            position_id=position.id,
            status="manual_only",
            base_currency=base_currency,
            source="manual",
            error_message="Manual asset has no manual_price set",
            captured_at=now,
        )
        return asset_entries.serialize_asset_snapshot(snapshot) or {}

    fx_rate = _get_fx_rate(
        market_data,
        quote_currency=position.quote_currency,
        base_currency=base_currency,
    )
    market_value = round(position.quantity * position.manual_price * fx_rate, 4)
    unrealized_pnl = round((position.manual_price - position.cost_basis) * position.quantity * fx_rate, 4)
    snapshot = asset_entries.add_asset_snapshot(
        db,
        position_id=position.id,
        status="priced",
        price=position.manual_price,
        quote_currency=position.quote_currency or base_currency,
        base_currency=base_currency,
        fx_rate=fx_rate,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        source="manual",
        captured_at=now,
    )
    position.mapping_status = "manual_only"
    position.error_message = None
    db.flush()
    return asset_entries.serialize_asset_snapshot(snapshot) or {}


def _refresh_market_position(
    db,
    position: asset_entries.AssetPosition,
    *,
    base_currency: str,
    market_data: MarketDataClient,
    now: datetime,
) -> dict[str, Any]:
    _resolve_mapping(position, market_data=market_data)
    db.flush()

    if position.mapping_status != "resolved" or not position.ticker:
        snapshot = asset_entries.add_asset_snapshot(
            db,
            position_id=position.id,
            status=position.mapping_status or "unresolved",
            base_currency=base_currency,
            source=position.vendor or getattr(market_data, "vendor", None),
            error_message=position.error_message or "Asset is not mapped to a market symbol",
            captured_at=now,
        )
        return asset_entries.serialize_asset_snapshot(snapshot) or {}

    try:
        latest_quote = market_data.get_latest_quote(position.ticker)
        fx_rate = _get_fx_rate(
            market_data,
            quote_currency=latest_quote.currency,
            base_currency=base_currency,
        )
        market_value = round(position.quantity * latest_quote.price * fx_rate, 4)
        unrealized_pnl = round((latest_quote.price - position.cost_basis) * position.quantity * fx_rate, 4)
        snapshot = asset_entries.add_asset_snapshot(
            db,
            position_id=position.id,
            status="priced",
            price=latest_quote.price,
            quote_currency=latest_quote.currency,
            base_currency=base_currency,
            fx_rate=fx_rate,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            source=latest_quote.source,
            captured_at=now,
        )
        position.quote_currency = _normalize_upper(latest_quote.currency)
        position.vendor = latest_quote.source
        position.mapping_status = "resolved"
        position.error_message = None
        db.flush()
        return asset_entries.serialize_asset_snapshot(snapshot) or {}
    except Exception as exc:
        snapshot = asset_entries.add_asset_snapshot(
            db,
            position_id=position.id,
            status="error",
            base_currency=base_currency,
            source=position.vendor or getattr(market_data, "vendor", None),
            error_message=str(exc),
            captured_at=now,
        )
        position.error_message = str(exc)
        db.flush()
        return asset_entries.serialize_asset_snapshot(snapshot) or {}


def _refresh_position_record(
    db,
    position: asset_entries.AssetPosition,
    *,
    base_currency: str,
    market_data: MarketDataClient,
    now: datetime | None = None,
) -> dict[str, Any]:
    captured_at = _coerce_now(now)
    normalized_base_currency = _normalize_upper(base_currency) or "USD"
    if position.valuation_mode == MANUAL_VALUATION_MODE:
        return _refresh_manual_position(
            db,
            position,
            base_currency=normalized_base_currency,
            market_data=market_data,
            now=captured_at,
        )
    return _refresh_market_position(
        db,
        position,
        base_currency=normalized_base_currency,
        market_data=market_data,
        now=captured_at,
    )


def _is_snapshot_fresh(
    snapshot: asset_entries.AssetValuationSnapshot | None,
    *,
    base_currency: str,
    now: datetime,
) -> bool:
    if snapshot is None:
        return False
    if snapshot.base_currency != _normalize_upper(base_currency):
        return False
    return now - snapshot.captured_at.astimezone(timezone.utc) < REFRESH_INTERVAL


def list_asset_positions(request: Request | None) -> list[dict[str, Any]]:
    _require_asset_runtime()
    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        return _list_position_payloads(db, owner_scope=owner_scope)


def get_asset_position(position_id: str, request: Request | None) -> dict[str, Any]:
    _require_asset_runtime()
    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        position = asset_entries.get_asset_position_record(db, position_id, owner_user_id=owner_scope)
        account = asset_entries.get_asset_account_record(db, position.account_id, owner_user_id=position.owner_user_id)
        snapshot = asset_entries.list_latest_snapshots_by_position(db, [position.id]).get(position.id)
        return _serialize_position(position, account, snapshot)


def create_asset_position(
    payload: AssetPositionCreatePayload,
    request: Request | None,
) -> dict[str, Any]:
    _require_asset_runtime()
    market_data = build_market_data_client()
    with auth.db_session() as db:
        user, _owner_scope = _resolve_request_scope(db, request)
        valuation_mode = _normalize_valuation_mode(payload.valuation_mode)
        account = asset_entries.get_or_create_asset_account(
            db,
            owner_user_id=user.id,
            platform_name=payload.platform_name,
            account_name=payload.account_name,
        )
        position = asset_entries.AssetPosition(
            owner_user_id=user.id,
            account_id=account.id,
            asset_name=_require_text(payload.asset_name, "asset_name"),
            asset_category=_require_text(payload.asset_category, "asset_category").lower(),
            quantity=float(payload.quantity),
            cost_basis=float(payload.cost_basis),
            valuation_mode=valuation_mode,
            manual_price=payload.manual_price,
            ticker=_normalize_upper(payload.ticker),
            market=_normalize_optional_text(payload.market),
            exchange=_normalize_optional_text(payload.exchange),
            quote_type=_normalize_optional_text(payload.quote_type),
            resolved_name=_normalize_optional_text(payload.resolved_name),
            quote_currency=_normalize_upper(payload.currency),
            vendor=getattr(market_data, "vendor", None),
            mapping_status="manual_only" if valuation_mode == MANUAL_VALUATION_MODE else "unresolved",
            notes=_normalize_optional_text(payload.notes),
        )
        db.add(position)
        db.flush()

        if valuation_mode == MANUAL_VALUATION_MODE or not position.ticker:
            _resolve_mapping(position, market_data=market_data)
        _refresh_position_record(
            db,
            position,
            base_currency=position.quote_currency or "USD",
            market_data=market_data,
        )
        snapshot = asset_entries.list_latest_snapshots_by_position(db, [position.id]).get(position.id)
        return _serialize_position(position, account, snapshot)


def update_asset_position(
    position_id: str,
    payload: AssetPositionUpdatePayload,
    request: Request | None,
) -> dict[str, Any]:
    _require_asset_runtime()
    market_data = build_market_data_client()
    changes = payload.model_dump(exclude_unset=True)
    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        position = asset_entries.get_asset_position_record(db, position_id, owner_user_id=owner_scope)
        current_account = asset_entries.get_asset_account_record(
            db,
            position.account_id,
            owner_user_id=position.owner_user_id,
        )

        platform_name = changes.pop("platform_name", current_account.platform_name)
        account_name = changes.pop("account_name", current_account.account_name)
        target_account = asset_entries.get_or_create_asset_account(
            db,
            owner_user_id=position.owner_user_id,
            platform_name=platform_name,
            account_name=account_name,
        )
        position.account_id = target_account.id

        if "asset_name" in changes:
            position.asset_name = _require_text(changes.pop("asset_name"), "asset_name")
        if "asset_category" in changes:
            position.asset_category = _require_text(changes.pop("asset_category"), "asset_category").lower()
        if "quantity" in changes:
            position.quantity = float(changes.pop("quantity"))
        if "cost_basis" in changes:
            position.cost_basis = float(changes.pop("cost_basis"))
        if "valuation_mode" in changes:
            position.valuation_mode = _normalize_valuation_mode(changes.pop("valuation_mode"))
        if "manual_price" in changes:
            position.manual_price = changes.pop("manual_price")
        if "ticker" in changes:
            position.ticker = _normalize_upper(changes.pop("ticker"))
        if "market" in changes:
            position.market = _normalize_optional_text(changes.pop("market"))
        if "exchange" in changes:
            position.exchange = _normalize_optional_text(changes.pop("exchange"))
        if "quote_type" in changes:
            position.quote_type = _normalize_optional_text(changes.pop("quote_type"))
        if "resolved_name" in changes:
            position.resolved_name = _normalize_optional_text(changes.pop("resolved_name"))
        if "currency" in changes:
            position.quote_currency = _normalize_upper(changes.pop("currency"))
        if "notes" in changes:
            position.notes = _normalize_optional_text(changes.pop("notes"))
        if changes:
            raise auth.AuthValidationError(f"Unsupported asset fields: {sorted(changes.keys())}")

        if position.valuation_mode == MANUAL_VALUATION_MODE:
            position.mapping_status = "manual_only"
            position.ticker = None
            position.market = None
            position.exchange = None
            position.quote_type = None
            position.resolved_name = None
            position.error_message = None
        else:
            position.mapping_status = "unresolved"

        db.flush()
        _resolve_mapping(position, market_data=market_data)
        _refresh_position_record(
            db,
            position,
            base_currency=position.quote_currency or "USD",
            market_data=market_data,
        )
        snapshot = asset_entries.list_latest_snapshots_by_position(db, [position.id]).get(position.id)
        return _serialize_position(position, target_account, snapshot)


def delete_asset_position(position_id: str, request: Request | None) -> dict[str, Any]:
    _require_asset_runtime()
    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        position = asset_entries.get_asset_position_record(db, position_id, owner_user_id=owner_scope)
        db.delete(position)
        db.flush()
        return {"deleted": True, "position_id": position_id}


def refresh_asset_position(
    position_id: str,
    *,
    base_currency: str = "USD",
    request: Request | None,
) -> dict[str, Any]:
    _require_asset_runtime()
    market_data = build_market_data_client()
    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        position = asset_entries.get_asset_position_record(db, position_id, owner_user_id=owner_scope)
        account = asset_entries.get_asset_account_record(db, position.account_id, owner_user_id=position.owner_user_id)
        _refresh_position_record(db, position, base_currency=base_currency, market_data=market_data)
        snapshot = asset_entries.list_latest_snapshots_by_position(db, [position.id]).get(position.id)
        return _serialize_position(position, account, snapshot, base_currency=base_currency)


def refresh_due_asset_positions(
    *,
    base_currency: str = "USD",
    force: bool = False,
    request: Request | None,
) -> list[dict[str, Any]]:
    _require_asset_runtime()
    market_data = build_market_data_client()
    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        positions = asset_entries.list_asset_position_records(db, owner_user_id=owner_scope)
        accounts = {
            account.id: account
            for account in asset_entries.list_asset_account_records(db, owner_user_id=owner_scope)
        }
        latest_snapshots = asset_entries.list_latest_snapshots_by_position(db, [position.id for position in positions])
        now = _coerce_now()
        refreshed: list[dict[str, Any]] = []
        for position in positions:
            latest_snapshot = latest_snapshots.get(position.id)
            if not force and _is_snapshot_fresh(latest_snapshot, base_currency=base_currency, now=now):
                continue
            _refresh_position_record(
                db,
                position,
                base_currency=base_currency,
                market_data=market_data,
                now=now,
            )
            latest_snapshot = asset_entries.list_latest_snapshots_by_position(db, [position.id]).get(position.id)
            refreshed.append(
                _serialize_position(
                    position,
                    accounts[position.account_id],
                    latest_snapshot,
                    base_currency=base_currency,
                    now=now,
                )
            )
        return refreshed


def get_asset_summary(
    *,
    base_currency: str = "USD",
    refresh_if_stale: bool = True,
    request: Request | None,
) -> dict[str, Any]:
    _require_asset_runtime()
    normalized_base_currency = _normalize_upper(base_currency) or "USD"
    if refresh_if_stale:
        refresh_due_asset_positions(base_currency=normalized_base_currency, force=False, request=request)

    with auth.db_session() as db:
        _user, owner_scope = _resolve_request_scope(db, request)
        now = _coerce_now()
        positions = _list_position_payloads(
            db,
            owner_scope=owner_scope,
            base_currency=normalized_base_currency,
            now=now,
        )

    total_market_value = 0.0
    total_unrealized_pnl = 0.0
    priced_positions = 0
    unpriced_positions: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}

    for position in positions:
        account = position["account"]
        platform_name = account["platform_name"]
        account_name = account["account_name"]
        platform_group = groups.setdefault(
            platform_name,
            {
                "platform_name": platform_name,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "accounts": {},
            },
        )
        account_group = platform_group["accounts"].setdefault(
            account["id"],
            {
                "account_id": account["id"],
                "account_name": account_name,
                "market_value": 0.0,
                "unrealized_pnl": 0.0,
                "positions": [],
            },
        )
        account_group["positions"].append(position)

        snapshot = position.get("latest_snapshot")
        if (
            snapshot
            and snapshot.get("status") == "priced"
            and snapshot.get("base_currency") == normalized_base_currency
            and snapshot.get("market_value") is not None
        ):
            market_value = float(snapshot["market_value"])
            pnl = float(snapshot.get("unrealized_pnl") or 0.0)
            total_market_value += market_value
            total_unrealized_pnl += pnl
            priced_positions += 1
            platform_group["market_value"] += market_value
            platform_group["unrealized_pnl"] += pnl
            account_group["market_value"] += market_value
            account_group["unrealized_pnl"] += pnl
        else:
            unpriced_positions.append(position)

    ordered_groups = []
    for platform_name in sorted(groups):
        platform_group = groups[platform_name]
        ordered_accounts = []
        for account_id in sorted(
            platform_group["accounts"],
            key=lambda key: platform_group["accounts"][key]["account_name"].lower(),
        ):
            ordered_accounts.append(platform_group["accounts"][account_id])
        ordered_groups.append(
            {
                "platform_name": platform_group["platform_name"],
                "market_value": round(platform_group["market_value"], 4),
                "unrealized_pnl": round(platform_group["unrealized_pnl"], 4),
                "accounts": ordered_accounts,
            }
        )

    return {
        "base_currency": normalized_base_currency,
        "generated_at": _serialize_datetime(now),
        "totals": {
            "market_value": round(total_market_value, 4),
            "unrealized_pnl": round(total_unrealized_pnl, 4),
            "position_count": len(positions),
            "account_count": sum(len(group["accounts"]) for group in groups.values()),
            "priced_position_count": priced_positions,
            "unpriced_position_count": len(unpriced_positions),
        },
        "groups": ordered_groups,
        "unpriced_positions": unpriced_positions,
    }


def build_portfolio_context_for_owner(
    owner_user_id: str,
    *,
    ticker: str | None = None,
    base_currency: str = "USD",
) -> str:
    _require_asset_runtime()
    normalized_owner_user_id = _require_text(owner_user_id, "owner_user_id")
    normalized_base_currency = _normalize_upper(base_currency) or "USD"
    normalized_ticker = _normalize_upper(ticker)

    with auth.db_session() as db:
        positions = asset_entries.list_asset_position_records(db, owner_user_id=normalized_owner_user_id)
        if not positions:
            return ""

        accounts = {
            account.id: account
            for account in asset_entries.list_asset_account_records(db, owner_user_id=normalized_owner_user_id)
        }
        latest_snapshots = asset_entries.list_latest_snapshots_by_position(db, [position.id for position in positions])

    total_value = 0.0
    top_positions: list[dict[str, Any]] = []
    current_ticker_positions: list[str] = []
    unpriced_count = 0

    for position in positions:
        account = accounts.get(position.account_id)
        if account is None:
            continue
        snapshot = latest_snapshots.get(position.id)
        market_value = None
        unrealized_pnl = None
        if (
            snapshot is not None
            and snapshot.status == "priced"
            and snapshot.base_currency == normalized_base_currency
            and snapshot.market_value is not None
        ):
            market_value = float(snapshot.market_value)
            unrealized_pnl = float(snapshot.unrealized_pnl or 0.0)
            total_value += market_value
        else:
            unpriced_count += 1

        display_ticker = position.ticker or position.asset_name
        top_positions.append(
            {
                "label": display_ticker,
                "asset_name": position.asset_name,
                "quantity": position.quantity,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "platform_name": account.platform_name,
                "account_name": account.account_name,
            }
        )
        if normalized_ticker and (
            _normalize_upper(position.ticker) == normalized_ticker
            or _normalize_upper(position.asset_name) == normalized_ticker
            or _normalize_upper(position.resolved_name) == normalized_ticker
        ):
            value_label = (
                f"{market_value:.2f} {normalized_base_currency}"
                if market_value is not None
                else "unpriced"
            )
            current_ticker_positions.append(
                f"- {position.asset_name} | qty {position.quantity:g} | {value_label} | {account.platform_name}/{account.account_name}"
            )

    top_positions.sort(
        key=lambda item: (
            item["market_value"] is None,
            -(item["market_value"] or 0.0),
            item["asset_name"].lower(),
        )
    )

    lines = [
        "Current Portfolio Ledger Context:",
        f"- Tracked positions: {len(top_positions)} across {len(accounts)} account(s).",
        f"- Priced portfolio value: {total_value:.2f} {normalized_base_currency}.",
    ]
    if normalized_ticker:
        if current_ticker_positions:
            lines.append(f"- Existing exposure to {normalized_ticker}:")
            lines.extend(current_ticker_positions[:3])
        else:
            lines.append(f"- Existing exposure to {normalized_ticker}: none recorded.")

    lines.append("- Largest tracked positions:")
    for item in top_positions[:5]:
        if item["market_value"] is None:
            lines.append(
                f"- {item['label']} | qty {item['quantity']:g} | unpriced | {item['platform_name']}/{item['account_name']}"
            )
            continue
        weight = (item["market_value"] / total_value) * 100 if total_value > 0 else 0.0
        pnl_label = (
            f"{item['unrealized_pnl']:.2f} {normalized_base_currency}"
            if item["unrealized_pnl"] is not None
            else "N/A"
        )
        lines.append(
            f"- {item['label']} | qty {item['quantity']:g} | value {item['market_value']:.2f} {normalized_base_currency} | "
            f"weight {weight:.1f}% | P/L {pnl_label} | {item['platform_name']}/{item['account_name']}"
        )
    if unpriced_count:
        lines.append(f"- Additional unpriced positions: {unpriced_count}.")
    return "\n".join(lines)
