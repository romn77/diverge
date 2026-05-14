from diverge.runtime.analysis_schema import (
    HISTORICAL_TRADE_FEEDBACK_KEY,
    HISTORICAL_TRADE_REVIEWS_KEY,
    HistoricalTradeFeedback,
    trade_feedback_artifact_from_state,
)


def test_historical_trade_feedback_normalizes_initial_state_fields():
    feedback = HistoricalTradeFeedback.from_values(
        prompt=None,
        reviews=[{"trade_id": "trade-1"}, "invalid"],
    )

    assert feedback.initial_state_fields() == {
        HISTORICAL_TRADE_FEEDBACK_KEY: "",
        HISTORICAL_TRADE_REVIEWS_KEY: [{"trade_id": "trade-1"}],
    }


def test_trade_feedback_artifact_from_state_requires_structured_reviews():
    assert (
        trade_feedback_artifact_from_state(
            {
                HISTORICAL_TRADE_FEEDBACK_KEY: "prompt",
                HISTORICAL_TRADE_REVIEWS_KEY: [],
            },
            ticker="MSFT",
        )
        is None
    )

    artifact = trade_feedback_artifact_from_state(
        {
            HISTORICAL_TRADE_FEEDBACK_KEY: "prompt",
            HISTORICAL_TRADE_REVIEWS_KEY: [{"trade_id": "trade-1"}],
        },
        ticker="MSFT",
    )

    assert artifact == {
        "type": "trade_feedback",
        "ticker": "MSFT",
        "prompt": "prompt",
        "reviews": [{"trade_id": "trade-1"}],
    }
