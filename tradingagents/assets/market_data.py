from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from tradingagents.dataflows.interface import route_to_vendor


_CATEGORY_TO_QUOTE_TYPES = {
    "stock": {"EQUITY"},
    "equity": {"EQUITY"},
    "etf": {"ETF"},
    "fund": {"MUTUALFUND"},
    "mutual_fund": {"MUTUALFUND"},
    "crypto": {"CRYPTOCURRENCY", "CRYPTO"},
    "index": {"INDEX"},
    "currency": {"CURRENCY"},
    "forex": {"CURRENCY"},
}
_MANUAL_ONLY_CATEGORIES = {"cash", "manual", "manual_only"}


@dataclass(slots=True)
class SymbolCandidate:
    ticker: str
    name: str
    market: str | None
    exchange: str | None
    quote_type: str | None
    vendor: str


@dataclass(slots=True)
class PriceQuote:
    ticker: str
    price: float
    currency: str | None
    as_of: datetime
    source: str


class MarketDataClient:
    vendor = "yfinance"

    def search_symbols(self, query: str, asset_category: str, limit: int = 5) -> list[SymbolCandidate]:
        normalized_category = asset_category.strip().lower()
        if normalized_category in _MANUAL_ONLY_CATEGORIES:
            return []

        search = yf.Search(
            query,
            max_results=max(limit, 8),
            news_count=0,
            lists_count=0,
            include_cb=False,
            include_nav_links=False,
            include_research=False,
            raise_errors=False,
        )
        quotes = getattr(search, "quotes", []) or []
        allowed_quote_types = _CATEGORY_TO_QUOTE_TYPES.get(normalized_category)
        candidates: list[SymbolCandidate] = []
        for item in quotes:
            quote_type = (item.get("quoteType") or item.get("typeDisp") or "").upper() or None
            if allowed_quote_types and quote_type not in allowed_quote_types:
                continue
            ticker = item.get("symbol")
            if not ticker:
                continue
            candidates.append(
                SymbolCandidate(
                    ticker=ticker,
                    name=item.get("longname") or item.get("shortname") or ticker,
                    market=item.get("exchDisp") or item.get("exchange"),
                    exchange=item.get("exchange"),
                    quote_type=quote_type,
                    vendor=self.vendor,
                )
            )
        return candidates[:limit]

    def get_latest_quote(self, ticker: str) -> PriceQuote:
        payload = route_to_vendor("get_latest_price", ticker)
        return self._quote_from_payload(payload)

    def get_fx_quote(self, from_currency: str, to_currency: str) -> PriceQuote:
        if from_currency.upper() == to_currency.upper():
            now = datetime.now(timezone.utc)
            return PriceQuote(
                ticker=f"{from_currency.upper()}{to_currency.upper()}=X",
                price=1.0,
                currency=to_currency.upper(),
                as_of=now,
                source="identity",
            )
        return self.get_latest_quote(f"{from_currency.upper()}{to_currency.upper()}=X")

    def _quote_from_payload(self, payload: dict[str, Any]) -> PriceQuote:
        as_of = payload.get("as_of")
        if isinstance(as_of, str):
            parsed = datetime.fromisoformat(as_of)
        elif isinstance(as_of, datetime):
            parsed = as_of
        else:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return PriceQuote(
            ticker=payload["ticker"],
            price=float(payload["price"]),
            currency=payload.get("currency"),
            as_of=parsed,
            source=payload.get("source", "unknown"),
        )
