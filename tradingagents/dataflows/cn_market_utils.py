from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
from stockstats import wrap


CN_TICKER_RE = re.compile(
    r"^(?:(?P<prefix>SH|SZ|BJ))?(?P<code>\d{6})(?:\.(?P<suffix>SH|SZ|BJ))?$",
    re.IGNORECASE,
)
US_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")

INDICATOR_DESCRIPTIONS = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. Usage: Identify trend direction "
        "and serve as dynamic support/resistance."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend "
        "and identify golden/death cross setups."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. Usage: Capture quick shifts in "
        "momentum and potential entry points."
    ),
    "macd": "MACD: Computes momentum via differences of EMAs.",
    "macds": "MACD Signal: An EMA smoothing of the MACD line.",
    "macdh": "MACD Histogram: Shows the gap between the MACD line and its signal.",
    "rsi": "RSI: Measures momentum to flag overbought/oversold conditions.",
    "boll": "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands.",
    "boll_ub": "Bollinger Upper Band: Typically 2 standard deviations above the middle line.",
    "boll_lb": "Bollinger Lower Band: Typically 2 standard deviations below the middle line.",
    "atr": "ATR: Averages true range to measure volatility.",
    "vwma": "VWMA: A moving average weighted by volume.",
    "mfi": (
        "MFI: A momentum indicator using both price and volume to measure buying "
        "and selling pressure."
    ),
}


def infer_cn_exchange(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "300", "301", "302")):
        return "SZ"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "920")):
        return "BJ"
    if code.startswith(("4", "8")):
        return "BJ"
    raise ValueError(f"Unable to infer exchange for ticker '{code}'")


def parse_and_normalize_cn_ticker(symbol: str) -> dict[str, str]:
    value = symbol.strip().upper()
    match = CN_TICKER_RE.match(value)
    if not match:
        raise ValueError(f"Unsupported CN ticker format: '{symbol}'")

    code = match.group("code")
    prefix = match.group("prefix")
    suffix = match.group("suffix")

    if prefix and suffix and prefix != suffix:
        raise ValueError(f"Ticker prefix/suffix mismatch: '{symbol}'")

    exchange = prefix or suffix or infer_cn_exchange(code)
    yfinance_exchange = "SS" if exchange == "SH" else exchange

    return {
        "raw": code,
        "exchange": exchange,
        "akshare": code,
        "akshare_prefixed": f"{exchange.lower()}{code}",
        "akshare_em": f"{exchange}{code}",
        "tushare": f"{code}.{exchange}",
        "yfinance": f"{code}.{yfinance_exchange}",
    }


def detect_market(symbol: str) -> str:
    value = symbol.strip().upper()
    if CN_TICKER_RE.match(value):
        return "cn"
    if US_TICKER_RE.match(value):
        return "us"
    return "unknown"


def normalize_symbol_for_vendor(symbol: str, market: str, vendor: str) -> str:
    if market != "cn":
        return symbol

    parsed = parse_and_normalize_cn_ticker(symbol)
    if vendor == "akshare":
        return parsed["akshare"]
    if vendor == "tushare":
        return parsed["tushare"]
    if vendor == "yfinance":
        return parsed["yfinance"]
    return symbol


def dataframe_to_standard_string(df: pd.DataFrame, title: str) -> str:
    if df is None or df.empty:
        return f"No data found for {title}"

    formatted = df.copy()
    for column in formatted.columns:
        if pd.api.types.is_datetime64_any_dtype(formatted[column]):
            formatted[column] = formatted[column].dt.strftime("%Y-%m-%d")

    header = f"# {title}\n"
    header += f"# Total records: {len(formatted)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + formatted.to_csv(index=False)


def rename_columns(df: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    renamed = df.rename(columns=column_map).copy()
    if "Date" in renamed.columns:
        renamed["Date"] = pd.to_datetime(renamed["Date"])
        renamed = renamed.sort_values("Date").reset_index(drop=True)
    return renamed


def generate_indicator_report(
    df: pd.DataFrame,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    if indicator not in INDICATOR_DESCRIPTIONS:
        supported = ", ".join(sorted(INDICATOR_DESCRIPTIONS.keys()))
        raise ValueError(f"Indicator {indicator} is not supported. Choose from: {supported}")

    working = df.copy()
    if "Date" not in working.columns:
        raise ValueError("Indicator data requires a 'Date' column")

    working["Date"] = pd.to_datetime(working["Date"])
    wrapped = wrap(working)
    wrapped["Date"] = pd.to_datetime(wrapped["Date"])
    wrapped[indicator]

    current_dt = pd.to_datetime(curr_date)
    before_dt = current_dt - pd.Timedelta(days=look_back_days)

    date_values = []
    cursor = current_dt
    while cursor >= before_dt:
        matches = wrapped[wrapped["Date"] == cursor]
        if matches.empty:
            value = "N/A: Not a trading day (weekend or holiday)"
        else:
            raw_value = matches.iloc[0][indicator]
            value = "N/A" if pd.isna(raw_value) else str(raw_value)
        date_values.append((cursor.strftime("%Y-%m-%d"), value))
        cursor -= pd.Timedelta(days=1)

    body = "".join(f"{date_str}: {value}\n" for date_str, value in date_values)
    return (
        f"## {indicator} values from {before_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        f"{body}\n\n"
        f"{INDICATOR_DESCRIPTIONS[indicator]}"
    )
