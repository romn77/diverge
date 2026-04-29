from __future__ import annotations

from ...cn_market_utils import generate_indicator_report
from .stock import _fetch_tushare_stock_df


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    start_date = "2010-01-01"
    df = _fetch_tushare_stock_df(symbol, start_date, curr_date)
    return generate_indicator_report(df, indicator, curr_date, look_back_days)
