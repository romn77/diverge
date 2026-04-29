# Asset Module Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CLI-first asset tracking module with local persistence, symbol resolution, 15-minute valuation refresh support, and grouped summary views without introducing a separate web app.

**Architecture:** Add a new `diverge.assets` package for ledger models, SQLite persistence, symbol resolution, valuation refresh, and summary aggregation. Extend the existing Typer CLI with an `asset` command group that writes to `~/.diverge/assets.db`, reuses `diverge.dataflows` for price fetches, and keeps unresolved/manual-only assets explicit instead of silently valuing them at zero.

**Tech Stack:** Python 3.10+, Typer, Rich, Questionary, sqlite3, pytest/unittest, yfinance-backed search, existing `diverge.dataflows` routing.

---

### Task 1: Asset Persistence Foundation

**Files:**
- Create: `diverge/assets/__init__.py`
- Create: `diverge/assets/models.py`
- Create: `diverge/assets/paths.py`
- Create: `diverge/assets/storage.py`
- Test: `tests/test_asset_storage.py`

- [ ] **Step 1: Write the failing storage tests**

```python
def test_asset_repository_round_trip(tmp_path):
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
    )

    ledger = repo.list_assets_with_state()

    assert ledger[0].asset.id == asset.id
    assert ledger[0].mapping.ticker == "AAPL"
    assert ledger[0].latest_snapshot.market_value == 1750
```

- [ ] **Step 2: Run the storage test to verify it fails**

Run: `python -m pytest tests/test_asset_storage.py -q`
Expected: `ImportError` or `AttributeError` because the asset storage module does not exist yet.

- [ ] **Step 3: Write the minimal persistence implementation**

```python
class AssetRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = resolve_assets_db_path(db_path)
        self._ensure_schema()

    def create_platform_group(self, name: str) -> PlatformGroup: ...
    def create_account(self, platform_group_id: int, name: str) -> AssetAccount: ...
    def create_asset(self, *, account_id: int, name: str, category: str, quantity: float, cost_basis: float) -> AssetRecord: ...
    def update_asset(self, asset_id: int, **changes) -> AssetRecord: ...
    def delete_asset(self, asset_id: int) -> None: ...
    def upsert_mapping(self, asset_id: int, **mapping_fields) -> AssetMappingState: ...
    def add_valuation_snapshot(self, asset_id: int, **snapshot_fields) -> ValuationSnapshot: ...
    def list_assets_with_state(self) -> list[AssetLedgerEntry]: ...
```

- [ ] **Step 4: Run the storage test to verify it passes**

Run: `python -m pytest tests/test_asset_storage.py -q`
Expected: `1 passed` or more once CRUD coverage is expanded.

- [ ] **Step 5: Refactor to keep schema and row mapping readable**

```python
def _row_to_asset(self, row: sqlite3.Row) -> AssetRecord:
    return AssetRecord(
        id=row["id"],
        account_id=row["account_id"],
        name=row["name"],
        category=row["category"],
        quantity=row["quantity"],
        cost_basis=row["cost_basis"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

### Task 2: Symbol Resolution and Valuation Refresh

**Files:**
- Create: `diverge/assets/market_data.py`
- Create: `diverge/assets/service.py`
- Modify: `diverge/dataflows/interface.py`
- Modify: `diverge/dataflows/y_finance.py`
- Test: `tests/test_asset_market_data.py`

- [ ] **Step 1: Write the failing resolver and refresh tests**

```python
def test_refresh_marks_ambiguous_assets_without_silent_valuation(tmp_path):
    repo = AssetRepository(tmp_path / "assets.db")
    service = AssetService(
        repository=repo,
        market_data=FakeMarketData(
            search_results={"Apple": [candidate("AAPL"), candidate("APC.DE")]},
            prices={"AAPL": quote(price=175, currency="USD")},
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

    assert resolution.status == "ambiguous"
    assert len(resolution.candidates) == 2
```

```python
def test_refresh_converts_quote_currency_into_base_currency(tmp_path):
    repo = AssetRepository(tmp_path / "assets.db")
    service = AssetService(
        repository=repo,
        market_data=FakeMarketData(
            search_results={"Shopify": [candidate("SHOP.TO", market="TSX")]},
            prices={
                "SHOP.TO": quote(price=120, currency="CAD"),
                "CADUSD=X": quote(price=0.74, currency="USD"),
            },
        ),
    )

    asset = service.create_asset(...)
    service.confirm_mapping(asset.id, ticker="SHOP.TO", market="TSX")
    result = service.refresh_asset(asset.id, base_currency="USD")

    assert result.status == "priced"
    assert result.market_value == 888.0
```

- [ ] **Step 2: Run the resolver/refresh tests to verify they fail**

Run: `python -m pytest tests/test_asset_market_data.py -q`
Expected: failure because the service and market-data adapters do not exist yet.

- [ ] **Step 3: Add the market-data and valuation implementation**

```python
class MarketDataClient:
    def search_symbols(self, query: str, asset_category: str, limit: int = 5) -> list[SymbolCandidate]: ...
    def get_latest_quote(self, ticker: str) -> PriceQuote: ...
    def get_fx_quote(self, from_currency: str, to_currency: str) -> PriceQuote: ...

class AssetService:
    REFRESH_INTERVAL = timedelta(minutes=15)

    def resolve_asset(self, asset_id: int) -> ResolutionResult: ...
    def confirm_mapping(self, asset_id: int, ticker: str, market: str | None = None) -> AssetMappingState: ...
    def refresh_asset(self, asset_id: int, base_currency: str = "USD", now: datetime | None = None) -> RefreshResult: ...
    def refresh_due_assets(self, base_currency: str = "USD", now: datetime | None = None, force: bool = False) -> list[RefreshResult]: ...
```

- [ ] **Step 4: Run the resolver/refresh tests to verify they pass**

Run: `python -m pytest tests/test_asset_market_data.py -q`
Expected: all new cases pass, including ambiguous, unresolved, manual-only, and FX conversion branches.

- [ ] **Step 5: Add a simple local refresh loop**

```python
def run_refresh_loop(self, *, base_currency: str = "USD", interval_minutes: int = 15, cycles: int | None = None, sleep_fn=time.sleep) -> None:
    iteration = 0
    while cycles is None or iteration < cycles:
        self.refresh_due_assets(base_currency=base_currency, force=True)
        iteration += 1
        if cycles is None or iteration < cycles:
            sleep_fn(interval_minutes * 60)
```

### Task 3: CLI Asset Commands and Summary Views

**Files:**
- Create: `cli/assets.py`
- Modify: `cli/main.py`
- Test: `tests/test_asset_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
def test_asset_add_and_summary_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("DIVERGE_ASSETS_DB", str(tmp_path / "assets.db"))
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

    assert add.exit_code == 0
    assert summary.exit_code == 0
    assert "Auto-Valued Assets" in summary.stdout
    assert "Broker" in summary.stdout
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run: `python -m pytest tests/test_asset_cli.py -q`
Expected: failure because the `asset` command group is not registered yet.

- [ ] **Step 3: Add the CLI command group**

```python
asset_app = typer.Typer(help="Manage tracked assets and valuations.")

@asset_app.command("add")
def asset_add(...): ...

@asset_app.command("edit")
def asset_edit(...): ...

@asset_app.command("delete")
def asset_delete(...): ...

@asset_app.command("list")
def asset_list(...): ...

@asset_app.command("refresh")
def asset_refresh(...): ...

@asset_app.command("watch")
def asset_watch(...): ...

@asset_app.command("summary")
def asset_summary(...): ...
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run: `python -m pytest tests/test_asset_cli.py -q`
Expected: command registration, add/edit/delete/list/refresh/summary flows, and grouped summary output all pass.

- [ ] **Step 5: Run the targeted suite and manual smoke checks**

Run: `python -m pytest tests/test_asset_storage.py tests/test_asset_market_data.py tests/test_asset_cli.py -q`
Expected: all new tests pass.

Run: `python -m cli.main asset --help`
Expected: help output lists `add`, `edit`, `delete`, `list`, `refresh`, `watch`, and `summary`.
