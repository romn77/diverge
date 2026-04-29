from __future__ import annotations

import traceback

import akshare as ak

from diverge.dataflows.akshare_stock import _fetch_akshare_stock_df
from diverge.dataflows.cn_market_utils import normalize_symbol_for_vendor


SYMBOL = "000913.SZ"
START_DATE = "2025-02-19"
END_DATE = "2026-03-26"


def _print_success(df) -> None:
    print(f"SUCCESS: rows={len(df)}")
    print("columns:", list(df.columns))
    print(df.head(5).to_string(index=False))


def probe_universe_interface() -> None:
    print("=== Probe 1: ak.stock_info_a_code_name() ===")
    try:
        df = ak.stock_info_a_code_name()
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return

    _print_success(df)


def probe_cli_history_interface() -> None:
    akshare_symbol = normalize_symbol_for_vendor(SYMBOL, market="cn", vendor="akshare")
    print("\n=== Probe 2: CLI history via _fetch_akshare_stock_df() ===")
    print(f"symbol={SYMBOL} -> {akshare_symbol}")
    print(f"date range: {START_DATE} -> {END_DATE}")

    try:
        df = _fetch_akshare_stock_df(akshare_symbol, START_DATE, END_DATE)
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return

    _print_success(df)


def main() -> None:
    probe_universe_interface()
    probe_cli_history_interface()


if __name__ == "__main__":
    main()
