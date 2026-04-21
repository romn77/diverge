from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .market_data import MarketDataClient, PriceQuote, SymbolCandidate
from .storage import AssetRepository


@dataclass(slots=True)
class ResolutionResult:
    asset_id: int
    status: str
    candidates: list[SymbolCandidate]


@dataclass(slots=True)
class RefreshResult:
    asset_id: int
    status: str
    ticker: str | None
    price: float | None
    quote_currency: str | None
    base_currency: str | None
    fx_rate: float | None
    market_value: float | None
    unrealized_pnl: float | None
    error_message: str | None
    refreshed_at: datetime


class AssetService:
    REFRESH_INTERVAL = timedelta(minutes=15)

    def __init__(
        self,
        *,
        repository: AssetRepository | None = None,
        market_data: MarketDataClient | None = None,
    ) -> None:
        self.repository = repository or AssetRepository()
        self.market_data = market_data or MarketDataClient()

    def create_asset(
        self,
        *,
        platform_name: str,
        account_name: str,
        asset_name: str,
        asset_category: str,
        quantity: float,
        cost_basis: float,
        manual_only: bool = False,
    ):
        platform = self.repository.get_or_create_platform_group(platform_name)
        account = self.repository.get_or_create_account(platform.id, account_name)
        asset = self.repository.create_asset(
            account_id=account.id,
            name=asset_name,
            category=asset_category,
            quantity=quantity,
            cost_basis=cost_basis,
        )
        if manual_only:
            self.repository.upsert_mapping(
                asset.id,
                status="manual_only",
                vendor=getattr(self.market_data, "vendor", None),
                error_message="Marked as manual-only by user",
            )
        return asset

    def resolve_asset(self, asset_id: int, *, limit: int = 5) -> ResolutionResult:
        asset = self.repository.get_asset(asset_id)
        candidates = self.market_data.search_symbols(asset.name, asset.category, limit=limit)
        if not candidates:
            self.repository.upsert_mapping(
                asset_id,
                status="unresolved",
                vendor=getattr(self.market_data, "vendor", None),
                error_message="No market matches found",
            )
            return ResolutionResult(asset_id=asset_id, status="unresolved", candidates=[])

        auto_candidate = self._auto_select_candidate(asset.name, candidates)
        if auto_candidate is not None:
            self.confirm_mapping(
                asset_id,
                ticker=auto_candidate.ticker,
                market=auto_candidate.market,
                exchange=auto_candidate.exchange,
                quote_type=auto_candidate.quote_type,
                resolved_name=auto_candidate.name,
                vendor=auto_candidate.vendor,
            )
            return ResolutionResult(asset_id=asset_id, status="resolved", candidates=[auto_candidate])

        self.repository.upsert_mapping(
            asset_id,
            status="ambiguous",
            vendor=getattr(self.market_data, "vendor", None),
            error_message=f"{len(candidates)} candidates require confirmation",
        )
        return ResolutionResult(asset_id=asset_id, status="ambiguous", candidates=candidates)

    def confirm_mapping(
        self,
        asset_id: int,
        *,
        ticker: str,
        market: str | None = None,
        exchange: str | None = None,
        quote_type: str | None = None,
        resolved_name: str | None = None,
        vendor: str | None = None,
        currency: str | None = None,
    ):
        return self.repository.upsert_mapping(
            asset_id,
            status="resolved",
            ticker=ticker,
            market=market,
            exchange=exchange,
            quote_type=quote_type,
            resolved_name=resolved_name,
            vendor=vendor or getattr(self.market_data, "vendor", None),
            currency=currency,
        )

    def refresh_asset(
        self,
        asset_id: int,
        *,
        base_currency: str = "USD",
        now: datetime | None = None,
    ) -> RefreshResult:
        refreshed_at = self._coerce_datetime(now)
        entry = self.repository.get_asset_entry(asset_id)
        mapping = entry.mapping
        if mapping is None or mapping.status != "resolved" or not mapping.ticker:
            status = mapping.status if mapping is not None else "unresolved"
            error_message = (
                mapping.error_message
                if mapping is not None and mapping.error_message
                else "Asset is not mapped to a priced market symbol"
            )
            self.repository.add_valuation_snapshot(
                asset_id,
                status=status,
                base_currency=base_currency.upper(),
                source=getattr(self.market_data, "vendor", None),
                error_message=error_message,
                captured_at=refreshed_at.isoformat(),
            )
            return RefreshResult(
                asset_id=asset_id,
                status=status,
                ticker=mapping.ticker if mapping is not None else None,
                price=None,
                quote_currency=mapping.currency if mapping is not None else None,
                base_currency=base_currency.upper(),
                fx_rate=None,
                market_value=None,
                unrealized_pnl=None,
                error_message=error_message,
                refreshed_at=refreshed_at,
            )

        try:
            latest_quote = self.market_data.get_latest_quote(mapping.ticker)
            fx_rate = self._get_fx_rate(latest_quote, base_currency)
            market_value = round(entry.asset.quantity * latest_quote.price * fx_rate, 4)
            unrealized_pnl = round(
                (latest_quote.price - entry.asset.cost_basis) * entry.asset.quantity * fx_rate,
                4,
            )
            self.repository.add_valuation_snapshot(
                asset_id,
                status="priced",
                price=latest_quote.price,
                quote_currency=latest_quote.currency,
                base_currency=base_currency.upper(),
                fx_rate=fx_rate,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                source=latest_quote.source,
                captured_at=refreshed_at.isoformat(),
            )
            self.confirm_mapping(
                asset_id,
                ticker=mapping.ticker,
                market=mapping.market,
                exchange=mapping.exchange,
                quote_type=mapping.quote_type,
                resolved_name=mapping.resolved_name,
                vendor=mapping.vendor,
                currency=latest_quote.currency,
            )
            return RefreshResult(
                asset_id=asset_id,
                status="priced",
                ticker=mapping.ticker,
                price=latest_quote.price,
                quote_currency=latest_quote.currency,
                base_currency=base_currency.upper(),
                fx_rate=fx_rate,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                error_message=None,
                refreshed_at=refreshed_at,
            )
        except Exception as exc:
            message = str(exc)
            self.repository.add_valuation_snapshot(
                asset_id,
                status="error",
                base_currency=base_currency.upper(),
                source=mapping.vendor,
                error_message=message,
                captured_at=refreshed_at.isoformat(),
            )
            return RefreshResult(
                asset_id=asset_id,
                status="error",
                ticker=mapping.ticker,
                price=None,
                quote_currency=mapping.currency,
                base_currency=base_currency.upper(),
                fx_rate=None,
                market_value=None,
                unrealized_pnl=None,
                error_message=message,
                refreshed_at=refreshed_at,
            )

    def refresh_due_assets(
        self,
        *,
        base_currency: str = "USD",
        now: datetime | None = None,
        force: bool = False,
    ) -> list[RefreshResult]:
        current_time = self._coerce_datetime(now)
        results: list[RefreshResult] = []
        for entry in self.repository.list_assets_with_state():
            if entry.mapping is None or entry.mapping.status != "resolved" or not entry.mapping.ticker:
                continue
            if not force and entry.latest_snapshot is not None and self._is_snapshot_fresh(entry.latest_snapshot.captured_at, current_time):
                continue
            results.append(
                self.refresh_asset(
                    entry.asset.id,
                    base_currency=base_currency,
                    now=current_time,
                )
            )
        return results

    def run_refresh_loop(
        self,
        *,
        base_currency: str = "USD",
        interval_minutes: int = 15,
        cycles: int | None = None,
        sleep_fn=time.sleep,
    ) -> None:
        iteration = 0
        while cycles is None or iteration < cycles:
            self.refresh_due_assets(base_currency=base_currency, force=True)
            iteration += 1
            if cycles is None or iteration < cycles:
                sleep_fn(interval_minutes * 60)

    def _get_fx_rate(self, latest_quote: PriceQuote, base_currency: str) -> float:
        quote_currency = (latest_quote.currency or base_currency).upper()
        target_currency = base_currency.upper()
        if quote_currency == target_currency:
            return 1.0
        fx_quote = self.market_data.get_fx_quote(quote_currency, target_currency)
        return float(fx_quote.price)

    def _auto_select_candidate(
        self,
        asset_name: str,
        candidates: list[SymbolCandidate],
    ) -> SymbolCandidate | None:
        if len(candidates) == 1:
            return candidates[0]
        normalized_name = self._normalize_text(asset_name)
        exact_matches = [
            candidate
            for candidate in candidates
            if self._normalize_text(candidate.name) == normalized_name
            or self._normalize_text(candidate.ticker) == normalized_name
        ]
        return exact_matches[0] if len(exact_matches) == 1 else None

    def _coerce_datetime(self, value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _is_snapshot_fresh(self, captured_at: str, now: datetime) -> bool:
        captured = datetime.fromisoformat(captured_at)
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        return now - captured < self.REFRESH_INTERVAL

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.lower().split())
