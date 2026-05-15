from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from diverge.common.symbols import detect_market
from diverge.research.search.session import (
    SearchToolContext,
    current_search_context,
    search_sessions,
)
from diverge.runtime.analysis_schema import (
    HistoricalTradeFeedback,
    historical_trade_feedback_from_values,
)
from diverge.trade_feedback import get_trade_feedback_payload


GetTradeFeedbackPayload = Callable[..., Mapping[str, Any]]
CreateSearchSession = Callable[..., Any]


@dataclass(frozen=True)
class AnalysisContextPackRequest:
    ticker: str
    analysis_date: str
    output_language: str
    portfolio_context: str | None = None
    opportunity_context: dict[str, Any] | None = None
    reports_dir: Path | None = None
    visible_trade_ids: Collection[str] | None = None
    analysis_run_id: str | None = None


@dataclass(frozen=True)
class AnalysisContextPack:
    trade_feedback: HistoricalTradeFeedback
    portfolio_context: str
    opportunity_context: dict[str, Any] | None = None
    search_context: SearchToolContext | None = None

    @property
    def historical_trade_feedback(self) -> str:
        return self.trade_feedback.prompt

    @property
    def historical_trade_reviews(self) -> list[dict[str, Any]]:
        return self.trade_feedback.reviews()

    def initial_state_kwargs(self) -> dict[str, Any]:
        return {
            **self.trade_feedback.initial_state_fields(),
            "portfolio_context": self.portfolio_context,
            "opportunity_context": self.opportunity_context,
        }


@dataclass(frozen=True)
class AnalysisContextPackAdapters:
    get_trade_feedback_payload: GetTradeFeedbackPayload = get_trade_feedback_payload
    create_search_session: CreateSearchSession = search_sessions.create


def _search_market_for_ticker(ticker: str) -> str:
    market = detect_market(ticker)
    return market if market in {"cn", "us", "hk"} else "us"


def build_analysis_context_pack(
    request: AnalysisContextPackRequest,
    *,
    adapters: AnalysisContextPackAdapters | None = None,
) -> AnalysisContextPack:
    resolved_adapters = adapters or AnalysisContextPackAdapters()
    visible_trade_ids = (
        set(request.visible_trade_ids)
        if request.visible_trade_ids is not None
        else None
    )
    trade_feedback_payload = resolved_adapters.get_trade_feedback_payload(
        request.ticker,
        reports_dir=request.reports_dir,
        analysis_date=request.analysis_date,
        visible_trade_ids=visible_trade_ids,
    )

    search_context = None
    if request.analysis_run_id:
        resolved_adapters.create_search_session(
            analysis_run_id=request.analysis_run_id,
            ticker=request.ticker,
            analysis_date=request.analysis_date,
        )
        search_context = SearchToolContext(
            analysis_run_id=request.analysis_run_id,
            agent="Analysis",
            ticker=request.ticker,
            analysis_date=request.analysis_date,
            market=_search_market_for_ticker(request.ticker),
            language=request.output_language,
        )

    return AnalysisContextPack(
        trade_feedback=historical_trade_feedback_from_values(
            prompt=trade_feedback_payload.get("prompt"),
            reviews=trade_feedback_payload.get("reviews"),
        ),
        portfolio_context=(request.portfolio_context or "").strip(),
        opportunity_context=request.opportunity_context,
        search_context=search_context,
    )


@contextmanager
def use_search_context(pack: AnalysisContextPack) -> Iterator[None]:
    token = None
    if pack.search_context is not None:
        token = current_search_context.set(pack.search_context)
    try:
        yield
    finally:
        if token is not None:
            current_search_context.reset(token)
