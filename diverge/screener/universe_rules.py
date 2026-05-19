from __future__ import annotations

import re

import pandas as pd


US_UNIVERSE_CAP_DEFAULT = 4500
US_PRIMARY_EXCHANGES = {"NYSE", "NASDAQ"}
US_ALLOWED_DOT_SUFFIXES = {"A", "B", "C", "V"}
US_NON_PRIMARY_SYMBOL_SUFFIXES = {"R", "RT", "RU", "U", "UN", "W", "WS", "WT"}
US_NON_PRIMARY_NAME_RE = re.compile(
    r"\b(WARRANT|WARRANTS|RIGHT|RIGHTS|UNIT|UNITS)\b", re.IGNORECASE
)
US_SPAC_NAME_RE = re.compile(r"\b(ACQUISITION|BLANK CHECK)\b", re.IGNORECASE)
US_TEST_LISTING_NAME_RE = re.compile(r"\bTICK PILOT TEST\b", re.IGNORECASE)
US_TEST_LISTING_SYMBOL_RE = re.compile(r"^(?:A|C|N|P)TEST(?:[.-]|$)", re.IGNORECASE)
US_FUND_LIKE_NAME_RE = re.compile(
    r"\b("
    r"ETF|ETN|FUND|TRUST|PORTFOLIO|INDEX|ISHARES|SPDR|PROSHARES|VANGUARD|INVESCO|"
    r"DIREXION|FIRST TRUST|GLOBAL X|ROUNDHILL|NEOS|KRANESHARES|WISDOMTREE|XTRACKERS"
    r")\b",
    re.IGNORECASE,
)
US_CLOSED_END_NAME_RE = re.compile(r"\b(CLOSED[- ]END|CEF)\b", re.IGNORECASE)
US_PREFERRED_NAME_RE = re.compile(
    r"\b(PREFERRED|PREF(?:ERRED)? STOCK|PREFERENCE|DEPOSITARY SHARES?)\b",
    re.IGNORECASE,
)
US_ADR_NAME_RE = re.compile(
    r"\b(ADR|ADS|AMERICAN DEPOSITARY|DEPOSITARY RECEIPT)\b",
    re.IGNORECASE,
)


def sort_rows_by_mktcap(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "mktcap" not in frame.columns:
        return frame.copy().reset_index(drop=True)

    ranked = frame.copy()
    ranked["mktcap"] = pd.to_numeric(ranked["mktcap"], errors="coerce").fillna(0.0)
    return ranked.sort_values(
        ["mktcap", "symbol"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def us_prefilter_drop_reason(row: pd.Series) -> str | None:
    market = str(row.get("market") or "us").strip().lower()
    if market != "us":
        return None

    symbol = str(row.get("symbol") or "").strip().upper()
    name = str(row.get("name") or "").strip()
    exchange = str(row.get("exchange") or "").strip().upper()
    suffix = symbol.split(".")[-1] if "." in symbol else ""

    if US_TEST_LISTING_NAME_RE.search(name) or US_TEST_LISTING_SYMBOL_RE.match(symbol):
        return "us_test_listing"
    if suffix in US_NON_PRIMARY_SYMBOL_SUFFIXES or US_NON_PRIMARY_NAME_RE.search(name):
        return "us_non_primary_issue"
    if US_PREFERRED_NAME_RE.search(name):
        return "us_preferred"
    if US_ADR_NAME_RE.search(name):
        return "us_adr"
    if US_SPAC_NAME_RE.search(name):
        return "us_spac"
    if US_FUND_LIKE_NAME_RE.search(name) or US_CLOSED_END_NAME_RE.search(name):
        return "us_fund_like"
    if "." in symbol and suffix not in US_ALLOWED_DOT_SUFFIXES:
        return "us_symbol_variant"
    if exchange not in US_PRIMARY_EXCHANGES:
        return "us_exchange"
    return None


def filter_us_common_stock_rows(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        dropped_columns = list(frame.columns)
        if "drop_reason" not in dropped_columns:
            dropped_columns.append("drop_reason")
        return frame.copy(), pd.DataFrame(columns=dropped_columns)

    kept_rows: list[dict] = []
    dropped_rows: list[dict] = []
    for _, row in frame.iterrows():
        reason = us_prefilter_drop_reason(row)
        if reason is not None:
            dropped_rows.append({**row.to_dict(), "drop_reason": reason})
            continue
        kept_rows.append(row.to_dict())

    kept = pd.DataFrame(kept_rows, columns=frame.columns)
    dropped_columns = list(frame.columns)
    if "drop_reason" not in dropped_columns:
        dropped_columns.append("drop_reason")
    dropped = pd.DataFrame(dropped_rows, columns=dropped_columns)
    return kept, dropped


def cap_market_bucket_rows(
    frame: pd.DataFrame,
    *,
    market: str,
    limit: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    market_rows = frame.loc[frame["market"] == market].copy().reset_index(drop=True)
    if limit is None or market_rows.empty or len(market_rows) <= limit:
        return market_rows, pd.DataFrame(columns=market_rows.columns)
    if "mktcap" not in market_rows.columns:
        raise ValueError(f"{market.upper()} universe cap requires an mktcap column")

    ranked_rows = sort_rows_by_mktcap(market_rows)
    kept = ranked_rows.head(limit).reset_index(drop=True)
    dropped = ranked_rows.iloc[limit:].reset_index(drop=True)
    return kept, dropped
