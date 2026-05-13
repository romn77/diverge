from pathlib import Path

from diverge.research.search.session import current_search_context
from diverge.runtime.analysis_context import (
    AnalysisContextPackAdapters,
    AnalysisContextPackRequest,
    build_analysis_context_pack,
    use_search_context,
)


def test_build_analysis_context_pack_normalizes_feedback_and_portfolio_context():
    calls = []

    def get_trade_feedback_payload(
        ticker, *, reports_dir, analysis_date, visible_trade_ids
    ):
        calls.append(
            {
                "ticker": ticker,
                "reports_dir": reports_dir,
                "analysis_date": analysis_date,
                "visible_trade_ids": visible_trade_ids,
            }
        )
        return {
            "prompt": "Historical trade feedback for ticker MSFT:\n1. Prior lesson",
            "reviews": [{"trade_id": "trade-1"}, "invalid"],
        }

    pack = build_analysis_context_pack(
        AnalysisContextPackRequest(
            ticker="MSFT",
            analysis_date="2026-04-20",
            output_language="en",
            portfolio_context="  Current portfolio reference.  ",
            reports_dir=Path("/tmp/reports"),
            visible_trade_ids=["trade-2", "trade-1", "trade-1"],
        ),
        adapters=AnalysisContextPackAdapters(
            get_trade_feedback_payload=get_trade_feedback_payload,
        ),
    )

    assert calls == [
        {
            "ticker": "MSFT",
            "reports_dir": Path("/tmp/reports"),
            "analysis_date": "2026-04-20",
            "visible_trade_ids": {"trade-1", "trade-2"},
        }
    ]
    assert pack.historical_trade_feedback.startswith("Historical trade feedback")
    assert pack.historical_trade_reviews == [{"trade_id": "trade-1"}]
    assert pack.portfolio_context == "Current portfolio reference."
    assert pack.initial_state_kwargs() == {
        "historical_trade_feedback": pack.historical_trade_feedback,
        "historical_trade_reviews": [{"trade_id": "trade-1"}],
        "portfolio_context": "Current portfolio reference.",
    }


def test_search_context_pack_creates_session_and_restores_contextvar():
    created_sessions = []

    def create_search_session(**kwargs):
        created_sessions.append(kwargs)

    token = current_search_context.set(None)
    try:
        pack = build_analysis_context_pack(
            AnalysisContextPackRequest(
                ticker="MSFT",
                analysis_date="2026-04-20",
                output_language="cn",
                analysis_run_id="analysis-run-1",
            ),
            adapters=AnalysisContextPackAdapters(
                get_trade_feedback_payload=lambda *_args, **_kwargs: {
                    "prompt": "",
                    "reviews": [],
                },
                create_search_session=create_search_session,
            ),
        )

        assert created_sessions == [
            {
                "analysis_run_id": "analysis-run-1",
                "ticker": "MSFT",
                "analysis_date": "2026-04-20",
            }
        ]
        assert current_search_context.get() is None
        with use_search_context(pack):
            active_context = current_search_context.get()
            assert active_context is not None
            assert active_context.analysis_run_id == "analysis-run-1"
            assert active_context.market == "us"
            assert active_context.language == "cn"
        assert current_search_context.get() is None
    finally:
        current_search_context.reset(token)
