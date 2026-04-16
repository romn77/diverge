from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


VALID_MARKETS = {"cn", "us"}
VALID_CN_DATA_SOURCES = {"akshare", "tushare"}
VALID_US_DATA_SOURCES = {"akshare", "alpha_vantage", "massive", "tushare", "yfinance"}


def build_cn_source_chain(
    primary_source: str,
    fallback_sources: list[str] | None = None,
) -> list[str]:
    chain: list[str] = []
    for source in [primary_source, *(fallback_sources or [])]:
        normalized = str(source).strip().lower()
        if normalized and normalized not in chain:
            chain.append(normalized)
    return chain


@dataclass(slots=True)
class ScreenRunConfig:
    markets: list[str]
    as_of_date: str
    top_k: int
    min_listing_days: int = 180
    cn_min_listing_trading_days: int = 120
    cn_min_avg_amount_20d: float = 50_000_000
    us_min_avg_dollar_volume_20d: float = 10_000_000
    cn_min_price: float = 3.0
    us_min_price: float = 5.0
    min_trading_days_20d: int = 18
    cn_universe_cap: int | None = None
    us_universe_cap: int | None = 3000
    output_dir: str = "./results/screener"
    cn_data_source: str = "tushare"
    cn_data_source_fallbacks: list[str] = field(default_factory=list)
    us_data_source: str = "yfinance"
    cn_manifest_path: str | None = None
    us_manifest_path: str | None = None

    def __post_init__(self) -> None:
        normalized_markets = [market.strip().lower() for market in self.markets]
        if not normalized_markets:
            raise ValueError("markets must include at least one value")
        if len(set(normalized_markets)) != len(normalized_markets):
            raise ValueError("markets must not contain duplicates")
        if any(market not in VALID_MARKETS for market in normalized_markets):
            raise ValueError("markets must be a subset of {'cn', 'us'}")

        self.markets = normalized_markets
        self.cn_data_source = self.cn_data_source.strip().lower()
        self.cn_data_source_fallbacks = [
            source.strip().lower() for source in self.cn_data_source_fallbacks
        ]
        self.us_data_source = self.us_data_source.strip().lower()
        if self.cn_manifest_path is not None:
            normalized_cn_manifest_path = self.cn_manifest_path.strip()
            self.cn_manifest_path = normalized_cn_manifest_path or None
        if self.us_manifest_path is not None:
            normalized_us_manifest_path = self.us_manifest_path.strip()
            self.us_manifest_path = normalized_us_manifest_path or None

        try:
            parsed_date = datetime.strptime(self.as_of_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("as_of_date must use YYYY-MM-DD format") from exc

        if parsed_date > date.today():
            raise ValueError("as_of_date cannot be in the future")

        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.min_listing_days <= 0:
            raise ValueError("min_listing_days must be positive")
        if self.cn_min_listing_trading_days <= 0:
            raise ValueError("cn_min_listing_trading_days must be positive")
        if self.cn_min_avg_amount_20d < 0 or self.us_min_avg_dollar_volume_20d < 0:
            raise ValueError("liquidity thresholds must be non-negative")
        if self.cn_min_price < 0 or self.us_min_price < 0:
            raise ValueError("price floors must be non-negative")
        if self.min_trading_days_20d <= 0:
            raise ValueError("min_trading_days_20d must be positive")
        if self.cn_universe_cap is not None and self.cn_universe_cap <= 0:
            raise ValueError("cn_universe_cap must be positive when provided")
        if self.us_universe_cap is not None and self.us_universe_cap <= 0:
            raise ValueError("us_universe_cap must be positive when provided")

        if self.cn_data_source not in VALID_CN_DATA_SOURCES:
            raise ValueError("cn_data_source must be one of {'akshare', 'tushare'}")
        if self.us_data_source not in VALID_US_DATA_SOURCES:
            raise ValueError("us_data_source must be one of {'akshare', 'alpha_vantage', 'massive', 'tushare', 'yfinance'}")

        if any(
            source not in VALID_CN_DATA_SOURCES
            for source in self.cn_data_source_fallbacks
        ):
            raise ValueError(
                "cn_data_source_fallbacks must only include values from {'akshare', 'tushare'}"
            )

        self.cn_data_source_fallbacks = [
            source
            for source in build_cn_source_chain(
                self.cn_data_source,
                self.cn_data_source_fallbacks,
            )[1:]
        ]

        if "us" in self.markets and not self.us_manifest_path:
            raise ValueError("us_manifest_path is required when 'us' is in markets")


@dataclass(slots=True)
class ScreenRunResult:
    run_dir: Path
    universe_count_by_market: dict[str, int]
    fetch_failed_count: int = 0
    filtered_count_by_reason: dict[str, int] = field(default_factory=dict)
    candidate_count: int = 0
    candidate_preview: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.candidate_preview) > 10:
            self.candidate_preview = self.candidate_preview[:10]
