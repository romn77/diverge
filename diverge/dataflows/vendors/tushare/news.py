from __future__ import annotations

from ...vendor_errors import VendorNotSupportedError


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    raise VendorNotSupportedError("tushare company news is not implemented.")


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    raise VendorNotSupportedError("tushare global macro news is not implemented.")


def get_insider_transactions(ticker: str) -> str:
    raise VendorNotSupportedError("tushare insider transactions are not implemented.")
