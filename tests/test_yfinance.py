from __future__ import annotations

import traceback

from diverge.dataflows.y_finance import _fetch_yfinance_ohlcv_df
from diverge.market_data.price_history import fetch_price_history


SYMBOL = "BRK.B"
START_DATE = "2026-03-20"
END_DATE = "2026-03-26"


def _print_success(df) -> None:
    print(f"SUCCESS: rows={len(df)}")
    print("columns:", list(df.columns))
    print(df.head(5).to_string(index=False))


def probe_raw_yfinance_interface() -> None:
    print("=== Probe 1: raw yfinance via _fetch_yfinance_ohlcv_df() ===")
    print(f"symbol={SYMBOL}")
    print(f"date range: {START_DATE} -> {END_DATE}")

    try:
        df = _fetch_yfinance_ohlcv_df(
            SYMBOL,
            START_DATE,
            END_DATE,
            use_cache=True,
            auto_adjust=False,
        )
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return

    _print_success(df)


def probe_screener_history_interface() -> None:
    print("\n=== Probe 2: screener history via fetch_price_history() ===")
    print(f"symbol={SYMBOL}")
    print("market=us")
    print(f"date range: {START_DATE} -> {END_DATE}")

    try:
        df = fetch_price_history(SYMBOL, "us", START_DATE, END_DATE)
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return

    _print_success(df)


def main() -> None:
    probe_raw_yfinance_interface()
    probe_screener_history_interface()


if __name__ == "__main__":
    main()
