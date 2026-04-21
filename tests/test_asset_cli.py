from __future__ import annotations

from datetime import datetime, timezone

from typer.testing import CliRunner

from cli.main import app
from tradingagents.assets.market_data import PriceQuote, SymbolCandidate
from tradingagents.assets.service import AssetService
from tradingagents.assets.storage import AssetRepository


class FakeMarketData:
    vendor = "fake"

    def __init__(self, *, search_results=None, prices=None) -> None:
        self.search_results = search_results or {}
        self.prices = prices or {}

    def search_symbols(self, query: str, asset_category: str, limit: int = 5) -> list[SymbolCandidate]:
        return list(self.search_results.get(query, []))

    def get_latest_quote(self, ticker: str) -> PriceQuote:
        return self.prices[ticker]

    def get_fx_quote(self, from_currency: str, to_currency: str) -> PriceQuote:
        return self.prices[f"{from_currency}{to_currency}=X"]


def test_asset_add_and_summary_commands(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "assets.db"
    now = datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)
    service = AssetService(
        repository=AssetRepository(db_path),
        market_data=FakeMarketData(
            prices={
                "AAPL": PriceQuote(
                    ticker="AAPL",
                    price=175,
                    currency="USD",
                    as_of=now,
                    source="fake",
                ),
            }
        ),
    )
    monkeypatch.setattr("cli.assets.build_asset_service", lambda: service)

    runner = CliRunner()
    add = runner.invoke(
        app,
        [
            "asset",
            "add",
            "--platform",
            "Broker",
            "--account",
            "Taxable",
            "--name",
            "Apple Inc.",
            "--category",
            "stock",
            "--quantity",
            "10",
            "--cost-basis",
            "150",
            "--confirm-symbol",
            "AAPL",
        ],
    )
    summary = runner.invoke(app, ["asset", "summary", "--base-currency", "USD"])

    assert add.exit_code == 0, add.stdout
    assert summary.exit_code == 0, summary.stdout
    assert "Auto-Valued Assets" in summary.stdout
    assert "Broker" in summary.stdout
    assert "1750.00 USD" in summary.stdout


def test_asset_add_prompts_for_ambiguous_candidate_selection(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "assets.db"
    service = AssetService(
        repository=AssetRepository(db_path),
        market_data=FakeMarketData(
            search_results={
                "Apple": [
                    SymbolCandidate(
                        ticker="AAPL",
                        name="Apple Inc.",
                        market="NASDAQ",
                        exchange="NMS",
                        quote_type="EQUITY",
                        vendor="fake",
                    ),
                    SymbolCandidate(
                        ticker="APC.DE",
                        name="Apple Hospitality",
                        market="XETRA",
                        exchange="GER",
                        quote_type="EQUITY",
                        vendor="fake",
                    ),
                ]
            }
        ),
    )
    monkeypatch.setattr("cli.assets.build_asset_service", lambda: service)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "asset",
            "add",
            "--platform",
            "Broker",
            "--account",
            "Taxable",
            "--name",
            "Apple",
            "--category",
            "stock",
            "--quantity",
            "10",
            "--cost-basis",
            "150",
        ],
        input="1\n",
    )

    entries = service.repository.list_assets_with_state()

    assert result.exit_code == 0, result.stdout
    assert "Multiple matches found" in result.stdout
    assert entries[0].mapping is not None
    assert entries[0].mapping.ticker == "AAPL"


def test_summary_separates_manual_only_assets_from_auto_valued_total(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "assets.db"
    now = datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)
    service = AssetService(
        repository=AssetRepository(db_path),
        market_data=FakeMarketData(
            prices={
                "BTC-USD": PriceQuote(
                    ticker="BTC-USD",
                    price=60000,
                    currency="USD",
                    as_of=now,
                    source="fake",
                )
            }
        ),
    )
    monkeypatch.setattr("cli.assets.build_asset_service", lambda: service)

    runner = CliRunner()
    auto_result = runner.invoke(
        app,
        [
            "asset",
            "add",
            "--platform",
            "Wallet",
            "--account",
            "Hot",
            "--name",
            "Bitcoin",
            "--category",
            "crypto",
            "--quantity",
            "1",
            "--cost-basis",
            "50000",
            "--confirm-symbol",
            "BTC-USD",
        ],
    )
    manual_result = runner.invoke(
        app,
        [
            "asset",
            "add",
            "--platform",
            "Bank",
            "--account",
            "Savings",
            "--name",
            "Cash Reserve",
            "--category",
            "cash",
            "--quantity",
            "1",
            "--cost-basis",
            "10000",
            "--manual-only",
        ],
    )
    summary = runner.invoke(app, ["asset", "summary", "--base-currency", "USD"])

    assert auto_result.exit_code == 0, auto_result.stdout
    assert manual_result.exit_code == 0, manual_result.stdout
    assert summary.exit_code == 0, summary.stdout
    assert "Auto-Valued Assets" in summary.stdout
    assert "Manual/Unpriced Assets" in summary.stdout
    assert "60000.00 USD" in summary.stdout
    assert "Cash Reserve" in summary.stdout
