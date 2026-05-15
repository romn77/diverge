from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from diverge.market_brief.schema import MarketBriefMarket, MarketSnapshot
from diverge.market_brief.sources.exchange_calendar import MARKET_LABELS


INDEX_REFERENCES: dict[MarketBriefMarket, dict[str, str]] = {
    "cn": {
        "symbol": "000001.SS",
        "name": "SSE Composite",
        "currency": "CNY",
    },
    "hk": {
        "symbol": "^HSI",
        "name": "Hang Seng Index",
        "currency": "HKD",
    },
    "us": {
        "symbol": "^GSPC",
        "name": "S&P 500",
        "currency": "USD",
    },
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _snapshot_unavailable(
    market: MarketBriefMarket,
    *,
    retrieved_at: str,
    warning: str,
) -> MarketSnapshot:
    reference = INDEX_REFERENCES[market]
    return MarketSnapshot(
        market=market,
        label=MARKET_LABELS[market],
        index_symbol=reference["symbol"],
        index_name=reference["name"],
        retrieved_at=retrieved_at,
        source="yfinance",
        currency=reference.get("currency"),
        status="unavailable",
        warning=warning,
    )


def _latest_two_closes(history: Any) -> tuple[float | None, float | None]:
    if history is None or getattr(history, "empty", True):
        return None, None
    if "Close" not in getattr(history, "columns", []):
        return None, None
    closes = [
        _float_or_none(value) for value in history["Close"].dropna().tail(2).tolist()
    ]
    closes = [value for value in closes if value is not None]
    if not closes:
        return None, None
    if len(closes) == 1:
        return closes[-1], None
    return closes[-1], closes[-2]


def collect_market_snapshots(
    markets: list[MarketBriefMarket],
    *,
    trading_days: dict[MarketBriefMarket, str | None],
) -> list[MarketSnapshot]:
    retrieved_at = _utc_iso()
    try:
        import yfinance as yf
    except Exception as exc:
        return [
            _snapshot_unavailable(
                market,
                retrieved_at=retrieved_at,
                warning=f"yfinance unavailable: {exc.__class__.__name__}",
            )
            for market in markets
        ]

    snapshots: list[MarketSnapshot] = []
    for market in markets:
        reference = INDEX_REFERENCES[market]
        try:
            history = yf.Ticker(reference["symbol"]).history(period="7d", interval="1d")
            last_close, previous_close = _latest_two_closes(history)
            if last_close is None:
                snapshots.append(
                    _snapshot_unavailable(
                        market,
                        retrieved_at=retrieved_at,
                        warning="No recent index close was returned.",
                    )
                )
                continue
            change_pct = None
            if previous_close not in (None, 0):
                change_pct = round((last_close / previous_close - 1) * 100, 2)
            snapshots.append(
                MarketSnapshot(
                    market=market,
                    label=MARKET_LABELS[market],
                    index_symbol=reference["symbol"],
                    index_name=reference["name"],
                    trading_day=trading_days.get(market),
                    retrieved_at=retrieved_at,
                    source="yfinance",
                    currency=reference.get("currency"),
                    last_close=round(last_close, 4),
                    previous_close=(
                        round(previous_close, 4) if previous_close is not None else None
                    ),
                    change_pct=change_pct,
                    status="ok",
                )
            )
        except Exception as exc:
            snapshots.append(
                _snapshot_unavailable(
                    market,
                    retrieved_at=retrieved_at,
                    warning=f"Index snapshot failed: {exc.__class__.__name__}",
                )
            )
    return snapshots
