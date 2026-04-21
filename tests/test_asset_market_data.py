from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tradingagents.assets.market_data import PriceQuote, SymbolCandidate
from tradingagents.assets.service import AssetService
from tradingagents.assets.storage import AssetRepository


class FakeMarketData:
    def __init__(self, *, search_results=None, prices=None, failures=None) -> None:
        self.search_results = search_results or {}
        self.prices = prices or {}
        self.failures = failures or {}
        self.search_calls: list[tuple[str, str, int]] = []
        self.quote_calls: list[str] = []
        self.fx_calls: list[tuple[str, str]] = []

    def search_symbols(self, query: str, asset_category: str, limit: int = 5) -> list[SymbolCandidate]:
        self.search_calls.append((query, asset_category, limit))
        return list(self.search_results.get(query, []))

    def get_latest_quote(self, ticker: str) -> PriceQuote:
        self.quote_calls.append(ticker)
        failure = self.failures.get(ticker)
        if failure is not None:
            raise failure
        return self.prices[ticker]

    def get_fx_quote(self, from_currency: str, to_currency: str) -> PriceQuote:
        self.fx_calls.append((from_currency, to_currency))
        ticker = f"{from_currency}{to_currency}=X"
        failure = self.failures.get(ticker)
        if failure is not None:
            raise failure
        return self.prices[ticker]


def candidate(ticker: str, *, market: str, exchange: str | None = None, quote_type: str = "EQUITY", name: str | None = None) -> SymbolCandidate:
    return SymbolCandidate(
        ticker=ticker,
        name=name or ticker,
        market=market,
        exchange=exchange,
        quote_type=quote_type,
        vendor="fake",
    )


def quote(price: float, currency: str, *, as_of: datetime) -> PriceQuote:
    return PriceQuote(
        ticker="ignored",
        price=price,
        currency=currency,
        as_of=as_of,
        source="fake",
    )


def test_resolve_asset_returns_ambiguous_candidates_without_silent_mapping(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "assets.db")
    service = AssetService(
        repository=repo,
        market_data=FakeMarketData(
            search_results={
                "Apple": [
                    candidate("AAPL", market="NASDAQ", name="Apple Inc."),
                    candidate("APC.DE", market="XETRA", name="Apple Hospitality"),
                ]
            }
        ),
    )

    asset = service.create_asset(
        platform_name="Broker",
        account_name="Taxable",
        asset_name="Apple",
        asset_category="stock",
        quantity=10,
        cost_basis=150,
    )

    resolution = service.resolve_asset(asset.id)
    mapping = repo.get_mapping(asset.id)

    assert resolution.status == "ambiguous"
    assert [item.ticker for item in resolution.candidates] == ["AAPL", "APC.DE"]
    assert mapping is not None
    assert mapping.status == "ambiguous"
    assert mapping.ticker is None


def test_refresh_converts_quote_currency_into_base_currency(tmp_path: Path) -> None:
    now = datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)
    repo = AssetRepository(tmp_path / "assets.db")
    service = AssetService(
        repository=repo,
        market_data=FakeMarketData(
            prices={
                "SHOP.TO": PriceQuote(
                    ticker="SHOP.TO",
                    price=120,
                    currency="CAD",
                    as_of=now,
                    source="fake",
                ),
                "CADUSD=X": PriceQuote(
                    ticker="CADUSD=X",
                    price=0.74,
                    currency="USD",
                    as_of=now,
                    source="fake",
                ),
            }
        ),
    )

    asset = service.create_asset(
        platform_name="Broker",
        account_name="Taxable",
        asset_name="Shopify",
        asset_category="stock",
        quantity=10,
        cost_basis=100,
    )
    service.confirm_mapping(
        asset.id,
        ticker="SHOP.TO",
        market="TSX",
        exchange="TOR",
        quote_type="EQUITY",
        resolved_name="Shopify Inc.",
        vendor="fake",
    )

    result = service.refresh_asset(asset.id, base_currency="USD", now=now)
    snapshot = repo.get_latest_snapshot(asset.id)

    assert result.status == "priced"
    assert result.market_value == 888.0
    assert result.unrealized_pnl == 148.0
    assert snapshot is not None
    assert snapshot.base_currency == "USD"
    assert snapshot.fx_rate == 0.74


def test_refresh_due_assets_skips_assets_with_fresh_snapshots(tmp_path: Path) -> None:
    now = datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)
    repo = AssetRepository(tmp_path / "assets.db")
    market_data = FakeMarketData(
        prices={
            "AAPL": PriceQuote(ticker="AAPL", price=175, currency="USD", as_of=now, source="fake"),
            "MSFT": PriceQuote(ticker="MSFT", price=300, currency="USD", as_of=now, source="fake"),
        }
    )
    service = AssetService(repository=repo, market_data=market_data)

    fresh_asset = service.create_asset(
        platform_name="Broker",
        account_name="Taxable",
        asset_name="Apple Inc.",
        asset_category="stock",
        quantity=10,
        cost_basis=150,
    )
    stale_asset = service.create_asset(
        platform_name="Broker",
        account_name="Retirement",
        asset_name="Microsoft",
        asset_category="stock",
        quantity=5,
        cost_basis=250,
    )

    service.confirm_mapping(fresh_asset.id, ticker="AAPL", market="NASDAQ")
    service.confirm_mapping(stale_asset.id, ticker="MSFT", market="NASDAQ")

    repo.add_valuation_snapshot(
        fresh_asset.id,
        status="priced",
        price=170,
        quote_currency="USD",
        base_currency="USD",
        fx_rate=1,
        market_value=1700,
        unrealized_pnl=200,
        source="fake",
        captured_at=(now - timedelta(minutes=5)).isoformat(),
    )
    repo.add_valuation_snapshot(
        stale_asset.id,
        status="priced",
        price=290,
        quote_currency="USD",
        base_currency="USD",
        fx_rate=1,
        market_value=1450,
        unrealized_pnl=200,
        source="fake",
        captured_at=(now - timedelta(minutes=20)).isoformat(),
    )

    results = service.refresh_due_assets(base_currency="USD", now=now)

    assert [result.asset_id for result in results] == [stale_asset.id]
    assert market_data.quote_calls == ["MSFT"]


def test_refresh_records_explicit_error_state_when_quote_fetch_fails(tmp_path: Path) -> None:
    now = datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)
    repo = AssetRepository(tmp_path / "assets.db")
    service = AssetService(
        repository=repo,
        market_data=FakeMarketData(
            failures={"BTC-USD": RuntimeError("quote unavailable")},
        ),
    )

    asset = service.create_asset(
        platform_name="Wallet",
        account_name="Cold",
        asset_name="Bitcoin",
        asset_category="crypto",
        quantity=1,
        cost_basis=50000,
    )
    service.confirm_mapping(
        asset.id,
        ticker="BTC-USD",
        market="CRYPTO",
        quote_type="CRYPTOCURRENCY",
        resolved_name="Bitcoin",
        vendor="fake",
    )

    result = service.refresh_asset(asset.id, base_currency="USD", now=now)
    snapshot = repo.get_latest_snapshot(asset.id)

    assert result.status == "error"
    assert "quote unavailable" in result.error_message
    assert snapshot is not None
    assert snapshot.status == "error"
    assert "quote unavailable" in snapshot.error_message
