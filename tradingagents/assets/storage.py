from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .models import (
    AssetAccount,
    AssetLedgerEntry,
    AssetMappingState,
    AssetRecord,
    PlatformGroup,
    ValuationSnapshot,
    utc_now_iso,
)
from .paths import resolve_assets_db_path


class AssetRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_assets_db_path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS platform_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_group_id INTEGER NOT NULL REFERENCES platform_groups(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(platform_group_id, name)
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL,
                cost_basis REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asset_mappings (
                asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                ticker TEXT,
                market TEXT,
                exchange TEXT,
                quote_type TEXT,
                resolved_name TEXT,
                currency TEXT,
                vendor TEXT,
                error_message TEXT,
                confirmed_at TEXT,
                last_attempted_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS valuation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                price REAL,
                quote_currency TEXT,
                base_currency TEXT,
                fx_rate REAL,
                market_value REAL,
                unrealized_pnl REAL,
                source TEXT,
                error_message TEXT,
                captured_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def create_platform_group(self, name: str) -> PlatformGroup:
        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO platform_groups (name, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (name, now, now),
        )
        self.connection.commit()
        return self.get_platform_group(cursor.lastrowid)

    def get_or_create_platform_group(self, name: str) -> PlatformGroup:
        existing = self.find_platform_group_by_name(name)
        return existing if existing is not None else self.create_platform_group(name)

    def get_platform_group(self, platform_group_id: int) -> PlatformGroup:
        row = self.connection.execute(
            "SELECT * FROM platform_groups WHERE id = ?",
            (platform_group_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown platform group: {platform_group_id}")
        return self._row_to_platform(row)

    def find_platform_group_by_name(self, name: str) -> PlatformGroup | None:
        row = self.connection.execute(
            "SELECT * FROM platform_groups WHERE name = ?",
            (name,),
        ).fetchone()
        return None if row is None else self._row_to_platform(row)

    def list_platform_groups(self) -> list[PlatformGroup]:
        rows = self.connection.execute(
            "SELECT * FROM platform_groups ORDER BY name ASC"
        ).fetchall()
        return [self._row_to_platform(row) for row in rows]

    def update_platform_group(self, platform_group_id: int, *, name: str) -> PlatformGroup:
        now = utc_now_iso()
        self.connection.execute(
            "UPDATE platform_groups SET name = ?, updated_at = ? WHERE id = ?",
            (name, now, platform_group_id),
        )
        self.connection.commit()
        return self.get_platform_group(platform_group_id)

    def delete_platform_group(self, platform_group_id: int) -> None:
        self.connection.execute(
            "DELETE FROM platform_groups WHERE id = ?",
            (platform_group_id,),
        )
        self.connection.commit()

    def create_account(self, platform_group_id: int, name: str) -> AssetAccount:
        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO accounts (platform_group_id, name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (platform_group_id, name, now, now),
        )
        self.connection.commit()
        return self.get_account(cursor.lastrowid)

    def get_or_create_account(self, platform_group_id: int, name: str) -> AssetAccount:
        existing = self.find_account_by_name(platform_group_id, name)
        return existing if existing is not None else self.create_account(platform_group_id, name)

    def get_account(self, account_id: int) -> AssetAccount:
        row = self.connection.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown account: {account_id}")
        return self._row_to_account(row)

    def find_account_by_name(self, platform_group_id: int, name: str) -> AssetAccount | None:
        row = self.connection.execute(
            """
            SELECT * FROM accounts
            WHERE platform_group_id = ? AND name = ?
            """,
            (platform_group_id, name),
        ).fetchone()
        return None if row is None else self._row_to_account(row)

    def list_accounts(self, platform_group_id: int | None = None) -> list[AssetAccount]:
        if platform_group_id is None:
            rows = self.connection.execute(
                "SELECT * FROM accounts ORDER BY id ASC"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM accounts WHERE platform_group_id = ? ORDER BY id ASC",
                (platform_group_id,),
            ).fetchall()
        return [self._row_to_account(row) for row in rows]

    def update_account(self, account_id: int, *, name: str) -> AssetAccount:
        now = utc_now_iso()
        self.connection.execute(
            "UPDATE accounts SET name = ?, updated_at = ? WHERE id = ?",
            (name, now, account_id),
        )
        self.connection.commit()
        return self.get_account(account_id)

    def delete_account(self, account_id: int) -> None:
        self.connection.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.connection.commit()

    def create_asset(
        self,
        *,
        account_id: int,
        name: str,
        category: str,
        quantity: float,
        cost_basis: float,
    ) -> AssetRecord:
        now = utc_now_iso()
        cursor = self.connection.execute(
            """
            INSERT INTO assets (account_id, name, category, quantity, cost_basis, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, name, category, quantity, cost_basis, now, now),
        )
        self.connection.commit()
        return self.get_asset(cursor.lastrowid)

    def get_asset(self, asset_id: int) -> AssetRecord:
        row = self.connection.execute(
            "SELECT * FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown asset: {asset_id}")
        return self._row_to_asset(row)

    def update_asset(self, asset_id: int, **changes: Any) -> AssetRecord:
        if not changes:
            return self.get_asset(asset_id)
        allowed_fields = {"account_id", "name", "category", "quantity", "cost_basis"}
        invalid = set(changes) - allowed_fields
        if invalid:
            raise ValueError(f"Unsupported asset fields: {sorted(invalid)}")

        now = utc_now_iso()
        assignments = ", ".join(f"{field} = ?" for field in changes)
        values = list(changes.values())
        values.extend([now, asset_id])
        self.connection.execute(
            f"UPDATE assets SET {assignments}, updated_at = ? WHERE id = ?",
            values,
        )
        self.connection.commit()
        return self.get_asset(asset_id)

    def delete_asset(self, asset_id: int) -> None:
        self.connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self.connection.commit()

    def upsert_mapping(self, asset_id: int, **mapping_fields: Any) -> AssetMappingState:
        allowed_fields = {
            "status",
            "ticker",
            "market",
            "exchange",
            "quote_type",
            "resolved_name",
            "currency",
            "vendor",
            "error_message",
            "confirmed_at",
            "last_attempted_at",
        }
        invalid = set(mapping_fields) - allowed_fields
        if invalid:
            raise ValueError(f"Unsupported mapping fields: {sorted(invalid)}")

        now = utc_now_iso()
        mapping_fields = dict(mapping_fields)
        mapping_fields["updated_at"] = now
        mapping_fields.setdefault("last_attempted_at", now)
        if mapping_fields.get("status") == "resolved" and "confirmed_at" not in mapping_fields:
            mapping_fields["confirmed_at"] = now
        if mapping_fields.get("status") == "resolved":
            mapping_fields["error_message"] = None

        columns = ["asset_id", *mapping_fields.keys()]
        placeholders = ", ".join("?" for _ in columns)
        values = [asset_id, *mapping_fields.values()]
        update_columns = ", ".join(
            f"{column} = excluded.{column}" for column in mapping_fields.keys()
        )
        self.connection.execute(
            f"""
            INSERT INTO asset_mappings ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(asset_id) DO UPDATE SET {update_columns}
            """,
            values,
        )
        self.connection.commit()
        return self.get_mapping(asset_id)

    def get_mapping(self, asset_id: int) -> AssetMappingState | None:
        row = self.connection.execute(
            "SELECT * FROM asset_mappings WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        return None if row is None else self._row_to_mapping(row)

    def add_valuation_snapshot(self, asset_id: int, **snapshot_fields: Any) -> ValuationSnapshot:
        allowed_fields = {
            "status",
            "price",
            "quote_currency",
            "base_currency",
            "fx_rate",
            "market_value",
            "unrealized_pnl",
            "source",
            "error_message",
            "captured_at",
        }
        invalid = set(snapshot_fields) - allowed_fields
        if invalid:
            raise ValueError(f"Unsupported valuation snapshot fields: {sorted(invalid)}")

        payload = dict(snapshot_fields)
        payload.setdefault("captured_at", utc_now_iso())
        columns = ["asset_id", *payload.keys()]
        values = [asset_id, *payload.values()]
        placeholders = ", ".join("?" for _ in columns)
        cursor = self.connection.execute(
            f"""
            INSERT INTO valuation_snapshots ({", ".join(columns)})
            VALUES ({placeholders})
            """,
            values,
        )
        self.connection.commit()
        return self.get_snapshot(cursor.lastrowid)

    def get_snapshot(self, snapshot_id: int) -> ValuationSnapshot:
        row = self.connection.execute(
            "SELECT * FROM valuation_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown snapshot: {snapshot_id}")
        return self._row_to_snapshot(row)

    def get_latest_snapshot(self, asset_id: int) -> ValuationSnapshot | None:
        row = self.connection.execute(
            """
            SELECT * FROM valuation_snapshots
            WHERE asset_id = ?
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            (asset_id,),
        ).fetchone()
        return None if row is None else self._row_to_snapshot(row)

    def get_asset_entry(self, asset_id: int) -> AssetLedgerEntry:
        row = self.connection.execute(
            """
            SELECT
                a.id AS asset_id,
                a.account_id,
                a.name AS asset_name,
                a.category,
                a.quantity,
                a.cost_basis,
                a.created_at AS asset_created_at,
                a.updated_at AS asset_updated_at,
                ac.id AS account_row_id,
                ac.platform_group_id,
                ac.name AS account_name,
                ac.created_at AS account_created_at,
                ac.updated_at AS account_updated_at,
                pg.id AS platform_id,
                pg.name AS platform_name,
                pg.created_at AS platform_created_at,
                pg.updated_at AS platform_updated_at
            FROM assets a
            JOIN accounts ac ON ac.id = a.account_id
            JOIN platform_groups pg ON pg.id = ac.platform_group_id
            WHERE a.id = ?
            """,
            (asset_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown asset: {asset_id}")
        return self._ledger_entry_from_row(row)

    def list_assets_with_state(self) -> list[AssetLedgerEntry]:
        rows = self.connection.execute(
            """
            SELECT
                a.id AS asset_id,
                a.account_id,
                a.name AS asset_name,
                a.category,
                a.quantity,
                a.cost_basis,
                a.created_at AS asset_created_at,
                a.updated_at AS asset_updated_at,
                ac.id AS account_row_id,
                ac.platform_group_id,
                ac.name AS account_name,
                ac.created_at AS account_created_at,
                ac.updated_at AS account_updated_at,
                pg.id AS platform_id,
                pg.name AS platform_name,
                pg.created_at AS platform_created_at,
                pg.updated_at AS platform_updated_at
            FROM assets a
            JOIN accounts ac ON ac.id = a.account_id
            JOIN platform_groups pg ON pg.id = ac.platform_group_id
            ORDER BY pg.name ASC, ac.name ASC, a.name ASC, a.id ASC
            """
        ).fetchall()
        return [self._ledger_entry_from_row(row) for row in rows]

    def _ledger_entry_from_row(self, row: sqlite3.Row) -> AssetLedgerEntry:
        asset_id = row["asset_id"]
        platform = PlatformGroup(
            id=row["platform_id"],
            name=row["platform_name"],
            created_at=row["platform_created_at"],
            updated_at=row["platform_updated_at"],
        )
        account = AssetAccount(
            id=row["account_row_id"],
            platform_group_id=row["platform_group_id"],
            name=row["account_name"],
            created_at=row["account_created_at"],
            updated_at=row["account_updated_at"],
        )
        asset = AssetRecord(
            id=asset_id,
            account_id=row["account_id"],
            name=row["asset_name"],
            category=row["category"],
            quantity=row["quantity"],
            cost_basis=row["cost_basis"],
            created_at=row["asset_created_at"],
            updated_at=row["asset_updated_at"],
        )
        return AssetLedgerEntry(
            platform=platform,
            account=account,
            asset=asset,
            mapping=self.get_mapping(asset_id),
            latest_snapshot=self.get_latest_snapshot(asset_id),
        )

    def _row_to_platform(self, row: sqlite3.Row) -> PlatformGroup:
        return PlatformGroup(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_account(self, row: sqlite3.Row) -> AssetAccount:
        return AssetAccount(
            id=row["id"],
            platform_group_id=row["platform_group_id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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

    def _row_to_mapping(self, row: sqlite3.Row) -> AssetMappingState:
        return AssetMappingState(
            asset_id=row["asset_id"],
            status=row["status"],
            ticker=row["ticker"],
            market=row["market"],
            exchange=row["exchange"],
            quote_type=row["quote_type"],
            resolved_name=row["resolved_name"],
            currency=row["currency"],
            vendor=row["vendor"],
            error_message=row["error_message"],
            confirmed_at=row["confirmed_at"],
            last_attempted_at=row["last_attempted_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_snapshot(self, row: sqlite3.Row) -> ValuationSnapshot:
        return ValuationSnapshot(
            id=row["id"],
            asset_id=row["asset_id"],
            status=row["status"],
            price=row["price"],
            quote_currency=row["quote_currency"],
            base_currency=row["base_currency"],
            fx_rate=row["fx_rate"],
            market_value=row["market_value"],
            unrealized_pnl=row["unrealized_pnl"],
            source=row["source"],
            error_message=row["error_message"],
            captured_at=row["captured_at"],
        )
