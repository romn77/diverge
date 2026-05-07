from diverge.decision_card.scoring import compute_conviction_score


def test_conviction_score_is_clamped():
    assert (
        compute_conviction_score(
            rating="BUY",
            confidence="high",
            evidence_count=99,
            risk_count=0,
            data_quality_issue_count=0,
        )
        == 100
    )
    assert (
        compute_conviction_score(
            rating="SELL",
            confidence="low",
            evidence_count=0,
            risk_count=99,
            data_quality_issue_count=99,
        )
        == 0
    )
