from __future__ import annotations

from collections import defaultdict
from typing import Optional

import typer

from tradingagents.assets.service import AssetService


asset_app = typer.Typer(
    help="Manage tracked assets and valuations.",
    no_args_is_help=True,
)


def build_asset_service() -> AssetService:
    return AssetService()


def _prompt_text(value: Optional[str], label: str) -> str:
    return value if value is not None else typer.prompt(label).strip()


def _prompt_float(value: Optional[float], label: str) -> float:
    return value if value is not None else float(typer.prompt(label))


def _format_money(value: float | None, currency: str | None) -> str:
    if value is None:
        return "N/A"
    suffix = f" {currency}" if currency else ""
    return f"{value:.2f}{suffix}"


def _select_candidate(candidates, confirm_symbol: str | None):
    if confirm_symbol:
        normalized = confirm_symbol.strip().upper()
        for candidate in candidates:
            if candidate.ticker.upper() == normalized:
                return candidate
        return None

    typer.echo("Multiple matches found:")
    for index, candidate in enumerate(candidates, start=1):
        typer.echo(
            f"{index}. {candidate.ticker} | {candidate.name} | {candidate.market or 'Unknown market'}"
        )

    raw_choice = typer.prompt("Choose candidate number").strip()
    try:
        choice = int(raw_choice)
    except ValueError as exc:
        raise typer.BadParameter("Candidate selection must be a number.") from exc
    if choice < 1 or choice > len(candidates):
        raise typer.BadParameter("Candidate selection is out of range.")
    return candidates[choice - 1]


def _state_for_entry(entry) -> str:
    if entry.latest_snapshot is not None:
        return entry.latest_snapshot.status
    if entry.mapping is not None:
        return entry.mapping.status
    return "unresolved"


@asset_app.command("add")
def asset_add(
    platform: Optional[str] = typer.Option(None, "--platform", help="Platform grouping label."),
    account: Optional[str] = typer.Option(None, "--account", help="Account name inside the platform group."),
    name: Optional[str] = typer.Option(None, "--name", help="Asset display name."),
    category: Optional[str] = typer.Option(None, "--category", help="Asset category, such as stock, crypto, etf, or cash."),
    quantity: Optional[float] = typer.Option(None, "--quantity", help="Held quantity."),
    cost_basis: Optional[float] = typer.Option(None, "--cost-basis", help="Per-unit cost basis."),
    manual_only: bool = typer.Option(False, "--manual-only", help="Skip market resolution and keep the asset manual-only."),
    confirm_symbol: Optional[str] = typer.Option(None, "--confirm-symbol", help="Explicit ticker to bind during asset creation."),
):
    service = build_asset_service()
    asset = service.create_asset(
        platform_name=_prompt_text(platform, "Platform group"),
        account_name=_prompt_text(account, "Account"),
        asset_name=_prompt_text(name, "Asset name"),
        asset_category=_prompt_text(category, "Asset category"),
        quantity=_prompt_float(quantity, "Quantity"),
        cost_basis=_prompt_float(cost_basis, "Cost basis"),
        manual_only=manual_only,
    )

    if manual_only:
        typer.echo(f"Added asset #{asset.id}: {asset.name} (manual-only)")
        return

    if confirm_symbol:
        service.confirm_mapping(
            asset.id,
            ticker=confirm_symbol.strip().upper(),
            resolved_name=asset.name,
            vendor=getattr(service.market_data, "vendor", None),
        )
        typer.echo(f"Added asset #{asset.id}: {asset.name} -> {confirm_symbol.strip().upper()}")
        return

    resolution = service.resolve_asset(asset.id)
    if resolution.status == "resolved":
        mapping = service.repository.get_mapping(asset.id)
        typer.echo(f"Added asset #{asset.id}: {asset.name} -> {mapping.ticker}")
        return

    if resolution.status == "unresolved":
        typer.echo(
            f"Added asset #{asset.id}: {asset.name} saved with unresolved pricing state"
        )
        return

    selected = _select_candidate(resolution.candidates, confirm_symbol=None)
    service.confirm_mapping(
        asset.id,
        ticker=selected.ticker,
        market=selected.market,
        exchange=selected.exchange,
        quote_type=selected.quote_type,
        resolved_name=selected.name,
        vendor=selected.vendor,
    )
    typer.echo(f"Added asset #{asset.id}: {asset.name} -> {selected.ticker}")


@asset_app.command("edit")
def asset_edit(
    asset_id: int = typer.Argument(..., help="Asset identifier."),
    platform: Optional[str] = typer.Option(None, "--platform", help="New platform grouping label."),
    account: Optional[str] = typer.Option(None, "--account", help="New account name."),
    name: Optional[str] = typer.Option(None, "--name", help="New asset name."),
    category: Optional[str] = typer.Option(None, "--category", help="New asset category."),
    quantity: Optional[float] = typer.Option(None, "--quantity", help="New quantity."),
    cost_basis: Optional[float] = typer.Option(None, "--cost-basis", help="New per-unit cost basis."),
    manual_only: bool = typer.Option(False, "--manual-only", help="Reset the asset into manual-only mode."),
    confirm_symbol: Optional[str] = typer.Option(None, "--confirm-symbol", help="Explicit ticker to bind after editing."),
):
    service = build_asset_service()
    entry = service.repository.get_asset_entry(asset_id)
    platform_name = platform or entry.platform.name
    account_name = account or entry.account.name
    platform_group = service.repository.get_or_create_platform_group(platform_name)
    account_record = service.repository.get_or_create_account(platform_group.id, account_name)

    changes = {"account_id": account_record.id}
    if name is not None:
        changes["name"] = name
    if category is not None:
        changes["category"] = category
    if quantity is not None:
        changes["quantity"] = quantity
    if cost_basis is not None:
        changes["cost_basis"] = cost_basis
    updated = service.repository.update_asset(asset_id, **changes)

    if manual_only:
        service.repository.upsert_mapping(
            asset_id,
            status="manual_only",
            vendor=getattr(service.market_data, "vendor", None),
            error_message="Marked as manual-only by user",
        )
    elif confirm_symbol:
        service.confirm_mapping(
            asset_id,
            ticker=confirm_symbol.strip().upper(),
            resolved_name=updated.name,
            vendor=getattr(service.market_data, "vendor", None),
        )
    elif name is not None or category is not None:
        service.resolve_asset(asset_id)

    typer.echo(f"Updated asset #{updated.id}: {updated.name}")


@asset_app.command("delete")
def asset_delete(
    asset_id: int = typer.Argument(..., help="Asset identifier."),
    yes: bool = typer.Option(False, "--yes", help="Delete without an interactive confirmation."),
):
    service = build_asset_service()
    entry = service.repository.get_asset_entry(asset_id)
    if not yes:
        confirmed = typer.confirm(f"Delete asset #{asset_id} ({entry.asset.name})?", default=False)
        if not confirmed:
            raise typer.Exit()
    service.repository.delete_asset(asset_id)
    typer.echo(f"Deleted asset #{asset_id}")


@asset_app.command("list")
def asset_list():
    service = build_asset_service()
    entries = service.repository.list_assets_with_state()
    if not entries:
        typer.echo("No assets tracked.")
        return

    for entry in entries:
        ticker = entry.mapping.ticker if entry.mapping is not None else "-"
        typer.echo(
            f"#{entry.asset.id} | {entry.platform.name} | {entry.account.name} | "
            f"{entry.asset.name} | {entry.asset.category} | qty={entry.asset.quantity:g} | "
            f"ticker={ticker} | state={_state_for_entry(entry)}"
        )


@asset_app.command("refresh")
def asset_refresh(
    asset_id: Optional[int] = typer.Option(None, "--asset-id", help="Refresh a single asset by id."),
    base_currency: str = typer.Option("USD", "--base-currency", help="Target base currency for totals."),
    force: bool = typer.Option(False, "--force", help="Refresh even if the latest snapshot is still fresh."),
):
    service = build_asset_service()
    if asset_id is not None:
        results = [service.refresh_asset(asset_id, base_currency=base_currency)]
    else:
        results = service.refresh_due_assets(base_currency=base_currency, force=force)

    if not results:
        typer.echo("No assets were due for refresh.")
        return

    for result in results:
        typer.echo(
            f"#{result.asset_id} | status={result.status} | "
            f"value={_format_money(result.market_value, result.base_currency)} | "
            f"pnl={_format_money(result.unrealized_pnl, result.base_currency)}"
        )


@asset_app.command("watch")
def asset_watch(
    base_currency: str = typer.Option("USD", "--base-currency", help="Target base currency for totals."),
    interval_minutes: int = typer.Option(15, "--interval-minutes", help="Refresh interval in minutes."),
    cycles: Optional[int] = typer.Option(None, "--cycles", help="Optional number of refresh iterations for local runs."),
):
    service = build_asset_service()
    typer.echo(
        f"Starting asset refresh loop every {interval_minutes} minute(s) in {base_currency.upper()}."
    )
    service.run_refresh_loop(
        base_currency=base_currency,
        interval_minutes=interval_minutes,
        cycles=cycles,
    )
    typer.echo("Asset refresh loop completed.")


@asset_app.command("summary")
def asset_summary(
    base_currency: str = typer.Option("USD", "--base-currency", help="Target base currency for grouped totals."),
    refresh_if_stale: bool = typer.Option(
        True,
        "--refresh-if-stale/--no-refresh-if-stale",
        help="Refresh resolved assets when their latest snapshot is older than 15 minutes.",
    ),
):
    service = build_asset_service()
    normalized_currency = base_currency.upper()
    if refresh_if_stale:
        service.refresh_due_assets(base_currency=normalized_currency)

    entries = service.repository.list_assets_with_state()
    auto_entries = []
    manual_entries = []
    for entry in entries:
        snapshot = entry.latest_snapshot
        if (
            snapshot is not None
            and snapshot.status == "priced"
            and snapshot.base_currency == normalized_currency
            and snapshot.market_value is not None
        ):
            auto_entries.append(entry)
        else:
            manual_entries.append(entry)

    typer.echo(f"Auto-Valued Assets ({normalized_currency})")
    if auto_entries:
        total = sum(entry.latest_snapshot.market_value for entry in auto_entries)
        typer.echo(f"Total: {_format_money(total, normalized_currency)}")
        grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for entry in auto_entries:
            grouped[entry.platform.name][entry.account.name].append(entry)
        for platform_name, account_groups in grouped.items():
            platform_total = sum(
                item.latest_snapshot.market_value
                for assets in account_groups.values()
                for item in assets
            )
            typer.echo(f"Platform: {platform_name} | Subtotal: {_format_money(platform_total, normalized_currency)}")
            for account_name, account_entries in account_groups.items():
                account_total = sum(item.latest_snapshot.market_value for item in account_entries)
                typer.echo(f"  Account: {account_name} | Subtotal: {_format_money(account_total, normalized_currency)}")
                for entry in account_entries:
                    ticker = entry.mapping.ticker if entry.mapping is not None else "-"
                    typer.echo(
                        f"    - {entry.asset.name} ({ticker}) | Qty {entry.asset.quantity:g} | "
                        f"Value {_format_money(entry.latest_snapshot.market_value, normalized_currency)} | "
                        f"P/L {_format_money(entry.latest_snapshot.unrealized_pnl, normalized_currency)}"
                    )
    else:
        typer.echo("No auto-valued assets.")

    typer.echo("")
    typer.echo("Manual/Unpriced Assets")
    if manual_entries:
        for entry in manual_entries:
            ticker = entry.mapping.ticker if entry.mapping is not None and entry.mapping.ticker else "-"
            error_message = ""
            if entry.latest_snapshot is not None and entry.latest_snapshot.error_message:
                error_message = f" | error={entry.latest_snapshot.error_message}"
            elif entry.mapping is not None and entry.mapping.error_message:
                error_message = f" | error={entry.mapping.error_message}"
            typer.echo(
                f"- {entry.asset.name} ({ticker}) | platform={entry.platform.name} | "
                f"account={entry.account.name} | state={_state_for_entry(entry)}{error_message}"
            )
    else:
        typer.echo("None")
