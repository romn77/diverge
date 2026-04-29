from __future__ import annotations

from .stock import _fetch_akshare_stock_df
from ...cn_market_utils import generate_indicator_report


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    start_date = "2010-01-01"
    df = _fetch_akshare_stock_df(symbol, start_date, curr_date)
    return generate_indicator_report(df, indicator, curr_date, look_back_days)
