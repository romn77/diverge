from pathlib import Path

from tradingagents.assets.storage import AssetRepository


def test_asset_repository_round_trip(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "assets.db")
    platform = repo.create_platform_group("Broker")
    account = repo.create_account(platform.id, "Taxable")
    asset = repo.create_asset(
        account_id=account.id,
        name="Apple Inc.",
        category="stock",
        quantity=10,
        cost_basis=150,
    )

    repo.upsert_mapping(
        asset.id,
        status="resolved",
        ticker="AAPL",
        market="NASDAQ",
        exchange="NMS",
        quote_type="EQUITY",
        resolved_name="Apple Inc.",
        currency="USD",
        vendor="yfinance",
    )
    repo.add_valuation_snapshot(
        asset.id,
        status="priced",
        price=175,
        quote_currency="USD",
        base_currency="USD",
        fx_rate=1,
        market_value=1750,
        unrealized_pnl=250,
        source="yfinance",
    )

    ledger = repo.list_assets_with_state()

    assert len(ledger) == 1
    assert ledger[0].platform.name == "Broker"
    assert ledger[0].account.name == "Taxable"
    assert ledger[0].asset.name == "Apple Inc."
    assert ledger[0].mapping.ticker == "AAPL"
    assert ledger[0].latest_snapshot.market_value == 1750


def test_repository_updates_asset_and_mapping_state(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "assets.db")
    platform = repo.create_platform_group("Broker")
    account = repo.create_account(platform.id, "Taxable")
    asset = repo.create_asset(
        account_id=account.id,
        name="Apple Inc.",
        category="stock",
        quantity=10,
        cost_basis=150,
    )

    repo.upsert_mapping(asset.id, status="unresolved", error_message="No exact match")

    updated_asset = repo.update_asset(
        asset.id,
        name="Apple",
        quantity=12,
        cost_basis=140,
    )
    updated_mapping = repo.upsert_mapping(
        asset.id,
        status="resolved",
        ticker="AAPL",
        market="NASDAQ",
        resolved_name="Apple Inc.",
        currency="USD",
    )

    fetched = repo.get_asset_entry(asset.id)

    assert updated_asset.name == "Apple"
    assert updated_asset.quantity == 12
    assert updated_mapping.status == "resolved"
    assert fetched.asset.cost_basis == 140
    assert fetched.mapping.error_message is None


def test_repository_supports_platform_and_account_crud(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "assets.db")

    platform = repo.create_platform_group("Old Platform")
    renamed_platform = repo.update_platform_group(platform.id, name="New Platform")
    account = repo.create_account(renamed_platform.id, "Old Account")
    renamed_account = repo.update_account(account.id, name="New Account")

    assert repo.list_platform_groups()[0].name == "New Platform"
    assert repo.list_accounts(renamed_platform.id)[0].name == "New Account"

    repo.delete_account(renamed_account.id)
    repo.delete_platform_group(renamed_platform.id)

    assert repo.list_accounts() == []
    assert repo.list_platform_groups() == []
