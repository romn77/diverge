from datetime import datetime
from io import StringIO

import pandas as pd

from .common import _make_api_request, _filter_csv_by_date_range
from ...cn_market_utils import rename_columns
from ...vendor_errors import VendorDataEmptyError, VendorRetryableError


AV_RENAME_MAP = {
    "timestamp": "Date",
    "open": "Open",
    "close": "Close",
    "high": "High",
    "low": "Low",
    "volume": "Volume",
}

def get_stock(
    symbol: str,
    start_date: str,
    end_date: str
) -> str:
    """
    Returns raw daily OHLCV values, adjusted close values, and historical split/dividend events
    filtered to the specified date range.

    Args:
        symbol: The name of the equity. For example: symbol=IBM
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing the daily adjusted time series data filtered to the date range.
    """
    # Parse dates to determine the range
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    today = datetime.now()

    # Choose outputsize based on whether the requested range is within the latest 100 days
    # Compact returns latest 100 data points, so check if start_date is recent enough
    days_from_today_to_start = (today - start_dt).days
    outputsize = "compact" if days_from_today_to_start < 100 else "full"

    params = {
        "symbol": symbol,
        "outputsize": outputsize,
        "datatype": "csv",
    }

    response = _make_api_request("TIME_SERIES_DAILY_ADJUSTED", params)

    return _filter_csv_by_date_range(response, start_date, end_date)


def _fetch_alpha_vantage_stock_df(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    csv_text = get_stock(symbol, start_date, end_date)
    if not csv_text or not str(csv_text).strip():
        raise VendorDataEmptyError(f"No Alpha Vantage stock data found for {symbol}")

    try:
        df = pd.read_csv(StringIO(csv_text))
    except Exception as exc:
        raise VendorRetryableError(f"alpha_vantage stock fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No Alpha Vantage stock data found for {symbol}")

    return rename_columns(df, AV_RENAME_MAP)


def get_latest_price(symbol: str):
    today = datetime.now()
    start_date = today.replace(day=max(today.day - 7, 1)).strftime("%Y-%m-%d")
    df = _fetch_alpha_vantage_stock_df(symbol, start_date, today.strftime("%Y-%m-%d"))
    if df.empty:
        raise VendorDataEmptyError(f"No latest price found for {symbol}")

    if "Date" in df.columns:
        latest_row = df.sort_values("Date").iloc[-1]
        as_of = str(latest_row["Date"])
    else:
        latest_row = df.iloc[-1]
        as_of = today.strftime("%Y-%m-%d")

    return {
        "ticker": symbol.upper(),
        "price": float(latest_row["Close"]),
        "currency": "USD",
        "as_of": as_of,
        "source": "alpha_vantage",
    }
