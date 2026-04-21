from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class PlatformGroup:
    id: int
    name: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class AssetAccount:
    id: int
    platform_group_id: int
    name: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class AssetRecord:
    id: int
    account_id: int
    name: str
    category: str
    quantity: float
    cost_basis: float
    created_at: str
    updated_at: str


@dataclass(slots=True)
class AssetMappingState:
    asset_id: int
    status: str
    ticker: str | None
    market: str | None
    exchange: str | None
    quote_type: str | None
    resolved_name: str | None
    currency: str | None
    vendor: str | None
    error_message: str | None
    confirmed_at: str | None
    last_attempted_at: str | None
    updated_at: str


@dataclass(slots=True)
class ValuationSnapshot:
    id: int
    asset_id: int
    status: str
    price: float | None
    quote_currency: str | None
    base_currency: str | None
    fx_rate: float | None
    market_value: float | None
    unrealized_pnl: float | None
    source: str | None
    error_message: str | None
    captured_at: str


@dataclass(slots=True)
class AssetLedgerEntry:
    platform: PlatformGroup
    account: AssetAccount
    asset: AssetRecord
    mapping: AssetMappingState | None
    latest_snapshot: ValuationSnapshot | None
