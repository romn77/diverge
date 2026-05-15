from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from diverge.market_brief.quality import apply_quality_gate
from diverge.market_brief.schema import (
    MarketBriefMarket,
    MarketBriefRisk,
    MarketBriefSchedule,
    MarketBriefSignal,
    MarketBriefTheme,
    PremarketBrief,
)
from diverge.market_brief.sources.exchange_calendar import (
    MARKET_LABELS,
    build_market_calendar,
    coerce_utc,
)
from diverge.market_brief.sources.market_data import collect_market_snapshots
from diverge.market_brief.sources.web_search import collect_web_search_sources


DEFAULT_MARKETS: tuple[MarketBriefMarket, ...] = ("cn", "us")
SUPPORTED_MARKETS = set(DEFAULT_MARKETS)
DEFAULT_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True)
class MarketBriefBuildRequest:
    markets: list[MarketBriefMarket] | None = None
    output_language: str = "zh-CN"
    trigger: str = "manual"
    slot: str | None = None
    automation_key: str | None = None
    scheduler_provider: str | None = None
    output_timezone: str = DEFAULT_TIMEZONE
    now_utc: datetime | None = None


def normalize_markets(markets: list[str] | None) -> list[MarketBriefMarket]:
    if not markets:
        return list(DEFAULT_MARKETS)
    normalized: list[MarketBriefMarket] = []
    for value in markets:
        candidate = str(value).strip().lower()
        if candidate in {"a", "ashare", "a-share", "a_share", "china", "cn"}:
            candidate = "cn"
        elif candidate in {"usa", "nyse", "nasdaq", "us"}:
            candidate = "us"
        if candidate not in SUPPORTED_MARKETS:
            raise ValueError("markets must contain only cn or us")
        market = candidate  # type: ignore[assignment]
        if market not in normalized:
            normalized.append(market)
    if not normalized:
        raise ValueError("At least one market is required.")
    return normalized


def _local_generated_at(now_utc: datetime, timezone_name: str) -> datetime:
    return coerce_utc(now_utc).astimezone(ZoneInfo(timezone_name or DEFAULT_TIMEZONE))


def _brief_id(now_local: datetime) -> str:
    return f"MARKET_BRIEF_{now_local.strftime('%Y%m%d_%H%M%S')}"


def _primary_trading_day(
    trading_days: dict[MarketBriefMarket, str | None],
) -> str | None:
    for market in DEFAULT_MARKETS:
        value = trading_days.get(market)
        if value:
            return value
    return None


def _snapshot_line(market: MarketBriefMarket, change_pct: float | None) -> str:
    label = MARKET_LABELS[market]
    if change_pct is None:
        return f"{label} index data needs verification after the market data feed refreshes."
    direction = "up" if change_pct >= 0 else "down"
    return f"{label} benchmark closed {direction} {abs(change_pct):.2f}% in the latest available session."


def _source_titles(sources) -> list[str]:
    titles: list[str] = []
    for source in sources[:4]:
        if source.title and source.title not in titles:
            titles.append(source.title)
    return titles


def _build_themes(
    markets: list[MarketBriefMarket],
    sources,
) -> list[MarketBriefTheme]:
    evidence = _source_titles(sources)
    themes = [
        MarketBriefTheme(
            title="Cross-market risk appetite",
            summary=(
                "Use index breadth, high-beta leadership, and defensive yield names "
                "to confirm whether the morning is risk-on or defensive."
            ),
            markets=markets,
            evidence=evidence[:2],
            validation_signals=[
                "Benchmarks hold above the first 30-minute VWAP.",
                "Advance/decline breadth confirms the index move.",
            ],
            invalidation_signals=[
                "Opening strength fades while defensive sectors lead.",
                "Index gains rely on a narrow set of mega-cap constituents.",
            ],
        ),
        MarketBriefTheme(
            title="Policy, rates, and currency sensitivity",
            summary=(
                "Track policy headlines, rates, dollar strength, and offshore China "
                "assets before adding exposure."
            ),
            markets=markets,
            evidence=evidence[2:4],
            validation_signals=[
                "CNH, Treasury yields, and sector ETFs move consistently with the narrative.",
                "Financials and exporters confirm the macro direction.",
            ],
            invalidation_signals=[
                "FX or rates reverse sharply after the first data point.",
                "Headline-sensitive sectors fail to hold opening ranges.",
            ],
        ),
    ]
    return themes[: max(1, min(2, len(markets)))]


def _build_ambush_directions(
    markets: list[MarketBriefMarket],
) -> list[MarketBriefTheme]:
    directions: list[MarketBriefTheme] = []
    if "cn" in markets:
        directions.append(
            MarketBriefTheme(
                title="A-share policy and dividend confirmation",
                summary=(
                    "Watch policy-linked large caps, high-dividend names, and liquid ETFs "
                    "for early confirmation."
                ),
                markets=["cn"],
                validation_signals=[
                    "SSE Composite and CSI-style proxies hold the opening range.",
                    "Turnover expands without a simultaneous spike in defensive selling.",
                ],
                invalidation_signals=[
                    "Large-cap strength fades while small caps lead only briefly.",
                ],
            )
        )
    if "us" in markets:
        directions.append(
            MarketBriefTheme(
                title="US rates and mega-cap leadership",
                summary=(
                    "Use futures, Treasury yields, and mega-cap breadth to decide whether "
                    "US risk appetite supports later cross-market context."
                ),
                markets=["us"],
                validation_signals=[
                    "S&P 500 and Nasdaq proxies move with yields and dollar direction.",
                ],
                invalidation_signals=[
                    "Index strength narrows while yields or dollar pressure rises.",
                ],
            )
        )
    return directions


def _build_risks(
    markets: list[MarketBriefMarket], source_count: int
) -> list[MarketBriefRisk]:
    risks = [
        MarketBriefRisk(
            risk="Source coverage may lag real-time market-moving headlines.",
            severity="medium" if source_count else "high",
            markets=markets,
            mitigation="Recheck official releases and wire headlines before the open.",
        ),
        MarketBriefRisk(
            risk="Opening liquidity can invalidate premarket narratives quickly.",
            severity="medium",
            markets=markets,
            mitigation="Wait for breadth, turnover, and VWAP confirmation.",
        ),
    ]
    if "us" in markets:
        risks.append(
            MarketBriefRisk(
                risk="US rates, dollar, and futures can reverse Asia risk appetite.",
                severity="medium",
                markets=[
                    "us",
                    *[market for market in markets if market == "cn"],
                ],
                mitigation="Track Treasury yields, dollar index proxies, and US index futures.",
            )
        )
    return risks


def _build_validation_signals(
    markets: list[MarketBriefMarket],
) -> list[MarketBriefSignal]:
    signals = [
        MarketBriefSignal(
            signal="First 30-minute index VWAP hold or rejection",
            markets=markets,
            why_it_matters="Confirms whether the premarket direction is accepted by cash trading.",
        ),
        MarketBriefSignal(
            signal="Advance/decline breadth and turnover expansion",
            markets=markets,
            why_it_matters="Separates broad participation from index-only moves.",
        ),
        MarketBriefSignal(
            signal="FX, rates, and commodity proxies moving with the stated theme",
            markets=markets,
            why_it_matters="Macro confirmation reduces headline-only false positives.",
        ),
    ]
    return signals


def build_market_brief(request: MarketBriefBuildRequest) -> PremarketBrief:
    markets = normalize_markets(request.markets)
    now_utc = coerce_utc(request.now_utc)
    output_timezone = request.output_timezone or DEFAULT_TIMEZONE
    now_local = _local_generated_at(now_utc, output_timezone)
    calendar = build_market_calendar(markets, now_utc=now_utc)
    trading_days = {item.market: item.trading_day for item in calendar}
    primary_trading_day = _primary_trading_day(trading_days)
    snapshots = collect_market_snapshots(markets, trading_days=trading_days)
    sources = collect_web_search_sources(
        markets=markets,
        trading_day=primary_trading_day,
        output_language=request.output_language,
    )
    available_snapshot_lines = [
        _snapshot_line(snapshot.market, snapshot.change_pct) for snapshot in snapshots
    ]
    market_labels = ", ".join(MARKET_LABELS[market] for market in markets)
    source_count = len(sources)
    summary = (
        f"{market_labels} premarket brief generated at "
        f"{now_local.strftime('%Y-%m-%d %H:%M')} {output_timezone}. "
        f"{source_count} source link(s) collected; verify the opening tape before action."
    )
    brief = PremarketBrief(
        brief_id=_brief_id(now_local),
        title=f"{market_labels} Premarket Brief",
        summary=summary,
        markets=markets,
        trading_day=primary_trading_day,
        trading_days=trading_days,
        generated_at=now_local.isoformat(),
        information_cutoff_at=now_local.isoformat(),
        data_quality_level="low",
        schedule=MarketBriefSchedule(
            trigger="scheduled" if request.trigger == "scheduled" else "manual",
            slot=request.slot,
            provider=request.scheduler_provider,
            automation_key=request.automation_key,
        ),
        market_calendar=calendar,
        market_snapshots=snapshots,
        overnight_moves=available_snapshot_lines,
        yesterday_review=available_snapshot_lines,
        today_variables=[
            "Official exchange notices and regulator announcements",
            "Index breadth, opening auction, and turnover",
            "FX, rates, commodities, and overseas index futures",
        ],
        main_themes=_build_themes(markets, sources),
        ambush_directions=_build_ambush_directions(markets),
        risks=_build_risks(markets, source_count),
        opening_validation_signals=_build_validation_signals(markets),
        sources=sources,
        metadata={
            "builder": "diverge.market_brief.builder",
            "output_language": request.output_language,
        },
    )
    return apply_quality_gate(brief)
