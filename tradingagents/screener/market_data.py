from __future__ import annotations

from dataclasses import dataclass
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from tradingagents.dataflows.akshare_stock import _fetch_akshare_stock_df, _fetch_akshare_us_stock_df
from tradingagents.dataflows.alpha_vantage_common import AlphaVantageRateLimitError
from tradingagents.dataflows.alpha_vantage_stock import _fetch_alpha_vantage_stock_df
from tradingagents.dataflows.cn_market_utils import normalize_symbol_for_vendor
from tradingagents.dataflows.massive_stock import _fetch_massive_stock_df
from tradingagents.dataflows.tushare_stock import _fetch_tushare_stock_df, _fetch_tushare_us_stock_df
from tradingagents.dataflows.vendor_errors import (
    VendorAuthError,
    VendorDataEmptyError,
    VendorNotSupportedError,
    VendorRetryableError,
)
from tradingagents.dataflows.y_finance import _fetch_yfinance_ohlcv_df
from .history_cache import (
    checkpoint_path,
    delete_checkpoint,
    load_checkpoint,
    load_history_cache,
    merge_history_frames,
    normalize_history_frame,
    REQUIRED_PRICE_COLUMNS,
    resolve_incremental_fetch_start,
    save_checkpoint,
    save_history_cache,
    slice_history_window,
)
from .schema import build_cn_source_chain

CN_REQUEST_DELAY_SECONDS = 0.35
US_REQUEST_DELAY_SECONDS = 2.0
RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
LOOKBACK_DAYS = 400
CHECKPOINT_TTL = timedelta(hours=24)
CN_FALLBACK_ERRORS = (
    VendorRetryableError,
    VendorAuthError,
    VendorNotSupportedError,
)

try:
    from yfinance.exceptions import YFRateLimitError
except ModuleNotFoundError:  # pragma: no cover
    class YFRateLimitError(Exception):
        pass


US_RETRYABLE_ERRORS = (
    VendorRetryableError,
    AlphaVantageRateLimitError,
    YFRateLimitError,
)


@dataclass(slots=True)
class _HistoryFetchContext:
    symbol: str
    market: str
    progress_current: int
    progress_total: int
    start_date: str
    as_of_date: str
    cache_dir: Path
    cached_frame: pd.DataFrame
    cached_span: str | None
    fetch_start: str | None


@dataclass(slots=True)
class _FetchedHistoryFrame:
    frame: pd.DataFrame
    source: str | None


@dataclass(slots=True)
class _HistoryStepResult:
    history_frame: pd.DataFrame | None = None
    should_store_history: bool = False
    processed_increment: int = 0
    failure: dict[str, str] | None = None
    status: str | None = None
    detail: str | None = None


class _HistoryFetchExecutor:
    def __init__(
        self,
        *,
        as_of_date: str,
        cn_source_chain: list[str],
        us_data_source: str,
    ) -> None:
        self.as_of_date = as_of_date
        self.cn_source_chain = list(cn_source_chain)
        self.us_data_source = us_data_source
        self.cn_network_fetch_count = 0
        self.us_network_fetch_count = 0
        self.last_source: str | None = None

    def fetch(self, symbol: str, market: str, fetch_start: str) -> _FetchedHistoryFrame:
        self.last_source = None
        if market != "cn":
            return self._fetch_us(symbol, market, fetch_start)
        return self._fetch_cn(symbol, market, fetch_start)

    def _fetch_us(self, symbol: str, market: str, fetch_start: str) -> _FetchedHistoryFrame:
        attempt = 0
        while True:
            try:
                if self.us_network_fetch_count > 0:
                    time.sleep(US_REQUEST_DELAY_SECONDS)
                self.us_network_fetch_count += 1
                self.last_source = self.us_data_source
                frame = fetch_price_history(
                    symbol,
                    market,
                    fetch_start,
                    self.as_of_date,
                    us_data_source=self.us_data_source,
                )
                return _FetchedHistoryFrame(frame=frame, source=self.last_source)
            except US_RETRYABLE_ERRORS as exc:
                if attempt >= len(RETRY_BACKOFF_SECONDS):
                    if isinstance(exc, VendorRetryableError):
                        raise _unwrap_vendor_error(exc)
                    raise
                time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                attempt += 1

    def _fetch_cn(self, symbol: str, market: str, fetch_start: str) -> _FetchedHistoryFrame:
        last_error: Exception | None = None
        for source in self.cn_source_chain:
            attempt = 0
            while True:
                try:
                    if self.cn_network_fetch_count > 0:
                        time.sleep(CN_REQUEST_DELAY_SECONDS)
                    self.cn_network_fetch_count += 1
                    self.last_source = source
                    frame = fetch_price_history(
                        symbol,
                        market,
                        fetch_start,
                        self.as_of_date,
                        cn_data_source=source,
                    )
                    return _FetchedHistoryFrame(frame=frame, source=self.last_source)
                except VendorDataEmptyError:
                    raise
                except CN_FALLBACK_ERRORS as exc:
                    last_error = exc
                    if attempt >= len(RETRY_BACKOFF_SECONDS):
                        break
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    attempt += 1

        if last_error is not None:
            raise _unwrap_vendor_error(last_error)

        raise VendorRetryableError("CN history fetch failed without a fallback result")


class _HistoryCheckpointState:
    def __init__(
        self,
        *,
        path: Path,
        start_date: str,
        batch_size: int,
        failure_reasons: dict[str, str],
        updated_at: str | None,
    ) -> None:
        self.path = path
        self.start_date = start_date
        self.batch_size = batch_size
        self.failure_reasons = failure_reasons
        self.updated_at = updated_at
        self.failures: list[dict[str, str]] = []
        self.processed_since_checkpoint = 0

    @classmethod
    def load(
        cls,
        *,
        path: Path,
        start_date: str,
        batch_size: int,
    ) -> _HistoryCheckpointState:
        payload = load_checkpoint(path, max_age=CHECKPOINT_TTL) or {}
        failed_symbols = payload.get("failed_symbols") or []
        failure_reasons = {
            str(item.get("symbol")): str(item.get("drop_reason") or "fetch_failed")
            for item in failed_symbols
            if item.get("symbol")
        }
        updated_at = payload.get("updated_at")
        return cls(
            path=path,
            start_date=start_date,
            batch_size=batch_size,
            failure_reasons=failure_reasons,
            updated_at=updated_at,
        )

    def checkpoint_skip_result(self, context: _HistoryFetchContext) -> _HistoryStepResult | None:
        if not context.cached_frame.empty or context.symbol not in self.failure_reasons:
            return None

        drop_reason = self.failure_reasons[context.symbol]
        detail = f"drop_reason={drop_reason} source=checkpoint"
        if self.updated_at:
            detail += f" updated_at={self.updated_at}"
        return _HistoryStepResult(
            failure=_history_failure_row(context, drop_reason),
            status="skip_checkpoint_failure",
            detail=detail,
        )

    def record(self, result: _HistoryStepResult) -> None:
        self.processed_since_checkpoint += result.processed_increment
        if result.failure is not None:
            self.failures.append(result.failure)

    def flush_if_needed(self) -> None:
        if self.processed_since_checkpoint < self.batch_size:
            return
        self.persist()
        self.processed_since_checkpoint = 0

    def persist(self) -> None:
        if not self.failures:
            delete_checkpoint(self.path)
            return
        save_checkpoint(
            self.path,
            start_date=self.start_date,
            failed_symbols=self.failures,
        )

    def finish(self) -> None:
        delete_checkpoint(self.path)

    def failure_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.failures, columns=["symbol", "market", "drop_reason"])


def _unwrap_vendor_error(exc: Exception) -> Exception:
    cause = getattr(exc, "__cause__", None)
    return cause if isinstance(cause, Exception) else exc


def _normalize_us_symbol_for_yfinance(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def _history_span(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None
    start = str(frame["Date"].min())
    end = str(frame["Date"].max())
    return f"{start}..{end}"


def _emit_progress(
    progress_callback: Callable[..., None] | None,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    *,
    status: str | None = None,
    detail: str | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        stage,
        current,
        total,
        symbol,
        status=status,
        detail=detail,
    )


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_PRICE_COLUMNS)

    return normalize_history_frame(df)


def _history_failure_row(context: _HistoryFetchContext, drop_reason: str) -> dict[str, str]:
    return {
        "symbol": context.symbol,
        "market": context.market,
        "drop_reason": drop_reason,
    }


def _fetch_range(fetch_start: str, as_of_date: str) -> str:
    return f"{fetch_start}..{as_of_date}"


def _source_detail(source: str | None) -> str:
    return f" source={source}" if source is not None else ""


def _build_history_fetch_context(
    row: pd.Series,
    *,
    index: int,
    total: int,
    start_date: str,
    as_of_date: str,
    cache_dir: Path,
) -> _HistoryFetchContext:
    symbol = row["symbol"]
    market = row["market"]
    cached_frame = load_history_cache(cache_dir, market, symbol)
    return _HistoryFetchContext(
        symbol=symbol,
        market=market,
        progress_current=index + 1,
        progress_total=total,
        start_date=start_date,
        as_of_date=as_of_date,
        cache_dir=cache_dir,
        cached_frame=cached_frame,
        cached_span=_history_span(cached_frame),
        fetch_start=resolve_incremental_fetch_start(cached_frame, start_date, as_of_date),
    )


def _cache_hit_result(context: _HistoryFetchContext) -> _HistoryStepResult | None:
    if context.fetch_start is not None:
        return None

    cached_window = slice_history_window(
        context.cached_frame,
        context.start_date,
        context.as_of_date,
    )
    has_window = not cached_window.empty
    return _HistoryStepResult(
        history_frame=cached_window if has_window else None,
        should_store_history=has_window,
        processed_increment=1 if has_window else 0,
        status="cache_hit",
        detail=f"cache={context.cached_span}" if context.cached_span else None,
    )


def _reconcile_fetched_history(
    context: _HistoryFetchContext,
    fetched: _FetchedHistoryFrame,
) -> _HistoryStepResult:
    fetch_start = context.fetch_start
    if fetch_start is None:
        raise ValueError("fetch_start must be set before fetching history")

    fetch_range = _fetch_range(fetch_start, context.as_of_date)
    source_detail = _source_detail(fetched.source)

    if fetched.frame.empty:
        cached_window = slice_history_window(
            context.cached_frame,
            context.start_date,
            context.as_of_date,
        )
        if not cached_window.empty:
            detail = (
                f"cache={context.cached_span} fetch={fetch_range}{source_detail}"
                if context.cached_span
                else f"fetch={fetch_range}{source_detail}"
            )
            return _HistoryStepResult(
                history_frame=cached_window,
                should_store_history=True,
                processed_increment=1,
                status="fetch_empty_reuse_cache",
                detail=detail,
            )

        return _HistoryStepResult(
            failure=_history_failure_row(context, "history_empty"),
            status="history_empty",
            detail=f"fetch={fetch_range}{source_detail}",
        )

    merged_frame = merge_history_frames(context.cached_frame, fetched.frame)
    save_history_cache(context.cache_dir, context.market, context.symbol, merged_frame)
    history_window = slice_history_window(merged_frame, context.start_date, context.as_of_date)
    if context.cached_frame.empty or fetch_start == context.start_date:
        status = "fetch_full"
        detail = f"fetch={fetch_range}{source_detail}"
    else:
        status = "fetch_tail"
        detail = f"cache={context.cached_span} fetch={fetch_range}{source_detail}"
    return _HistoryStepResult(
        history_frame=history_window,
        should_store_history=True,
        processed_increment=1,
        status=status,
        detail=detail,
    )


def _failure_result(
    context: _HistoryFetchContext,
    *,
    drop_reason: str,
    status: str,
    source: str | None,
) -> _HistoryStepResult:
    fetch_start = context.fetch_start
    if fetch_start is None:
        raise ValueError("fetch_start must be set before classifying fetch failures")

    return _HistoryStepResult(
        failure=_history_failure_row(context, drop_reason),
        status=status,
        detail=f"fetch={_fetch_range(fetch_start, context.as_of_date)}{_source_detail(source)}",
    )


def _fetch_symbol_history(
    context: _HistoryFetchContext,
    *,
    executor: _HistoryFetchExecutor,
) -> _HistoryStepResult:
    fetch_start = context.fetch_start
    if fetch_start is None:
        raise ValueError("fetch_start must be set before requesting history")

    try:
        fetched = executor.fetch(context.symbol, context.market, fetch_start)
        return _reconcile_fetched_history(context, fetched)
    except VendorDataEmptyError:
        return _failure_result(
            context,
            drop_reason="history_empty",
            status="history_empty",
            source=executor.last_source,
        )
    except VendorRetryableError:
        return _failure_result(
            context,
            drop_reason="fetch_failed",
            status="fetch_failed",
            source=executor.last_source,
        )


def _process_history_symbol(
    context: _HistoryFetchContext,
    *,
    executor: _HistoryFetchExecutor,
    checkpoint_state: _HistoryCheckpointState,
) -> _HistoryStepResult:
    cache_hit = _cache_hit_result(context)
    if cache_hit is not None:
        return cache_hit

    checkpoint_skip = checkpoint_state.checkpoint_skip_result(context)
    if checkpoint_skip is not None:
        return checkpoint_skip

    return _fetch_symbol_history(context, executor=executor)


def fetch_price_history(
    symbol: str,
    market: str,
    start_date: str,
    end_date: str,
    cn_data_source: str = "tushare",
    us_data_source: str = "yfinance",
) -> pd.DataFrame:
    if market == "cn":
        vendor_symbol = normalize_symbol_for_vendor(symbol, market="cn", vendor=cn_data_source)
        if cn_data_source == "tushare":
            frame = _fetch_tushare_stock_df(vendor_symbol, start_date, end_date)
        elif cn_data_source == "akshare":
            frame = _fetch_akshare_stock_df(vendor_symbol, start_date, end_date)
        else:
            raise ValueError(f"Unsupported CN data source '{cn_data_source}'")

        if cn_data_source == "tushare" and not frame.empty and "Amount" in frame.columns:
            frame = frame.copy()
            frame["Amount"] = pd.to_numeric(frame["Amount"], errors="coerce") * 1000
        return _normalize_price_frame(frame)

    if market == "us":
        if us_data_source == "yfinance":
            vendor_symbol = _normalize_us_symbol_for_yfinance(symbol)
            frame = _fetch_yfinance_ohlcv_df(
                vendor_symbol,
                start_date,
                end_date,
                use_cache=True,
                auto_adjust=False,
            )
        elif us_data_source == "alpha_vantage":
            frame = _fetch_alpha_vantage_stock_df(symbol, start_date, end_date)
        elif us_data_source == "tushare":
            frame = _fetch_tushare_us_stock_df(symbol, start_date, end_date)
        elif us_data_source == "akshare":
            frame = _fetch_akshare_us_stock_df(symbol, start_date, end_date)
        elif us_data_source == "massive":
            frame = _fetch_massive_stock_df(symbol, start_date, end_date)
        else:
            raise ValueError(f"Unsupported US data source '{us_data_source}'")
        return _normalize_price_frame(frame)

    raise ValueError(f"Unsupported market '{market}'")


def fetch_history_for_universe(
    universe_df: pd.DataFrame,
    as_of_date: str,
    cn_data_source: str = "tushare",
    cn_data_source_fallbacks: list[str] | None = None,
    us_data_source: str = "yfinance",
    progress_callback: Callable[..., None] | None = None,
    cache_dir: str | Path | None = None,
    checkpoint_dir: str | Path | None = None,
    checkpoint_batch_size: int = 100,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    start_date = (as_of_dt - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    history_cache_dir = Path(cache_dir) if cache_dir is not None else Path("./results/screener/.cache")
    history_checkpoint_dir = (
        Path(checkpoint_dir)
        if checkpoint_dir is not None
        else history_cache_dir / "checkpoints"
    )
    history_checkpoint_path = checkpoint_path(
        history_checkpoint_dir,
        universe_df,
        as_of_date,
        cn_data_source,
        cn_data_source_fallbacks=cn_data_source_fallbacks,
        us_data_source=us_data_source,
    )
    histories: dict[str, pd.DataFrame] = {}
    total = len(universe_df.index)
    cn_source_chain = build_cn_source_chain(
        cn_data_source,
        cn_data_source_fallbacks,
    )
    executor = _HistoryFetchExecutor(
        as_of_date=as_of_date,
        cn_source_chain=cn_source_chain,
        us_data_source=us_data_source,
    )
    checkpoint_state = _HistoryCheckpointState.load(
        path=history_checkpoint_path,
        start_date=start_date,
        batch_size=checkpoint_batch_size,
    )

    try:
        for index, row in universe_df.reset_index(drop=True).iterrows():
            context = _build_history_fetch_context(
                row,
                index=index,
                total=total,
                start_date=start_date,
                as_of_date=as_of_date,
                cache_dir=history_cache_dir,
            )
            result = _process_history_symbol(
                context,
                executor=executor,
                checkpoint_state=checkpoint_state,
            )
            if result.should_store_history and result.history_frame is not None:
                histories[context.symbol] = result.history_frame
            checkpoint_state.record(result)
            checkpoint_state.flush_if_needed()

            _emit_progress(
                progress_callback,
                "history",
                context.progress_current,
                context.progress_total,
                context.symbol,
                status=result.status,
                detail=result.detail,
            )
    except BaseException:
        checkpoint_state.persist()
        raise

    checkpoint_state.finish()

    return histories, checkpoint_state.failure_frame()
