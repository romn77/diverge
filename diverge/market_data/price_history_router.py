from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import time

import pandas as pd

from diverge.dataflows import vendor_usage
from diverge.dataflows.vendor_errors import (
    VendorAuthError,
    VendorDataEmptyError,
    VendorNotSupportedError,
    VendorRetryableError,
)
from diverge.dataflows.vendors.alpha_vantage.common import AlphaVantageRateLimitError

try:
    from yfinance.exceptions import YFRateLimitError
except ModuleNotFoundError:  # pragma: no cover

    class YFRateLimitError(Exception):
        pass


DEFAULT_CN_REQUEST_DELAY_SECONDS = 0.35
DEFAULT_US_REQUEST_DELAY_SECONDS = 2.0
DEFAULT_MASSIVE_US_REQUEST_DELAY_SECONDS = 0.1
DEFAULT_RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)

CN_FALLBACK_ERRORS = (
    VendorRetryableError,
    VendorAuthError,
    VendorNotSupportedError,
)
US_FALLBACK_ERRORS = (
    VendorRetryableError,
    VendorAuthError,
    VendorDataEmptyError,
    VendorNotSupportedError,
    AlphaVantageRateLimitError,
    vendor_usage.QuotaWaitRequired,
    YFRateLimitError,
)


@dataclass(slots=True)
class FetchedHistoryFrame:
    frame: pd.DataFrame
    source: str | None


def build_source_chain(
    primary_source: str,
    fallback_sources: list[str] | None = None,
) -> list[str]:
    chain: list[str] = []
    for source in [primary_source, *(fallback_sources or [])]:
        normalized = str(source).strip().lower()
        if normalized and normalized not in chain:
            chain.append(normalized)
    return chain


def unwrap_vendor_error(exc: Exception) -> Exception:
    cause = getattr(exc, "__cause__", None)
    return cause if isinstance(cause, Exception) else exc


class PriceHistoryRouter:
    """Route OHLCV fetches through provider chains, retry policy, and delays."""

    def __init__(
        self,
        *,
        as_of_date: str,
        cn_source_chain: Sequence[str],
        us_data_source: str,
        price_fetcher: Callable[..., pd.DataFrame],
        us_data_source_fallbacks: list[str] | None = None,
        retry_backoff_seconds: Sequence[float] = DEFAULT_RETRY_BACKOFF_SECONDS,
        cn_request_delay_seconds: float = DEFAULT_CN_REQUEST_DELAY_SECONDS,
        us_request_delay_seconds: float = DEFAULT_US_REQUEST_DELAY_SECONDS,
        massive_us_request_delay_seconds: float = (
            DEFAULT_MASSIVE_US_REQUEST_DELAY_SECONDS
        ),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.as_of_date = as_of_date
        self.cn_source_chain = [
            str(source).strip().lower() for source in cn_source_chain if source
        ]
        self.us_data_source = us_data_source
        self.us_source_chain = build_source_chain(
            us_data_source,
            us_data_source_fallbacks,
        )
        self.price_fetcher = price_fetcher
        self.retry_backoff_seconds = tuple(retry_backoff_seconds)
        self.cn_request_delay_seconds = cn_request_delay_seconds
        self.us_request_delay_seconds = us_request_delay_seconds
        self.massive_us_request_delay_seconds = massive_us_request_delay_seconds
        self.sleep = sleep
        self.cn_network_fetch_count = 0
        self.us_network_fetch_count = 0
        self.last_source: str | None = None

    def fetch(self, symbol: str, market: str, fetch_start: str) -> FetchedHistoryFrame:
        self.last_source = None
        if market != "cn":
            return self._fetch_us(symbol, market, fetch_start)
        return self._fetch_cn(symbol, market, fetch_start)

    def _fetch_us(
        self, symbol: str, market: str, fetch_start: str
    ) -> FetchedHistoryFrame:
        last_error: Exception | None = None
        for source in self.us_source_chain:
            attempt = 0
            while True:
                try:
                    if self.us_network_fetch_count > 0:
                        self.sleep(self._us_request_delay_seconds(source))
                    self.us_network_fetch_count += 1
                    self.last_source = source
                    frame = self.price_fetcher(
                        symbol,
                        market,
                        fetch_start,
                        self.as_of_date,
                        us_data_source=source,
                    )
                    return FetchedHistoryFrame(frame=frame, source=self.last_source)
                except US_FALLBACK_ERRORS as exc:
                    if (
                        isinstance(exc, VendorDataEmptyError)
                        and len(self.us_source_chain) == 1
                    ):
                        raise
                    last_error = exc
                    if attempt >= len(self.retry_backoff_seconds):
                        break
                    self.sleep(self.retry_backoff_seconds[attempt])
                    attempt += 1

        if last_error is not None:
            if isinstance(last_error, VendorRetryableError):
                raise unwrap_vendor_error(last_error)
            raise last_error

        raise VendorRetryableError("US history fetch failed without a fallback result")

    def _fetch_cn(
        self, symbol: str, market: str, fetch_start: str
    ) -> FetchedHistoryFrame:
        last_error: Exception | None = None
        for source in self.cn_source_chain:
            attempt = 0
            while True:
                try:
                    if self.cn_network_fetch_count > 0:
                        self.sleep(self.cn_request_delay_seconds)
                    self.cn_network_fetch_count += 1
                    self.last_source = source
                    frame = self.price_fetcher(
                        symbol,
                        market,
                        fetch_start,
                        self.as_of_date,
                        cn_data_source=source,
                    )
                    return FetchedHistoryFrame(frame=frame, source=self.last_source)
                except VendorDataEmptyError:
                    raise
                except CN_FALLBACK_ERRORS as exc:
                    last_error = exc
                    if attempt >= len(self.retry_backoff_seconds):
                        break
                    self.sleep(self.retry_backoff_seconds[attempt])
                    attempt += 1

        if last_error is not None:
            raise unwrap_vendor_error(last_error)

        raise VendorRetryableError("CN history fetch failed without a fallback result")

    def _us_request_delay_seconds(self, source: str) -> float:
        if str(source).strip().lower() == "massive":
            return self.massive_us_request_delay_seconds
        return self.us_request_delay_seconds
