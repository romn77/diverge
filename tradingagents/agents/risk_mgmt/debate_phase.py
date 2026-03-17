RISK_ANALYSTS_PER_ROUND = 3
THESIS_MODE = "thesis"
REBUTTAL_MODE = "rebuttal"


def get_risk_debate_mode(turn_count: int) -> str:
    """Return the prompt mode for the next risk speaker.

    The first full Aggressive/Conservative/Neutral cycle is thesis mode. Every
    subsequent cycle is rebuttal mode.
    """

    if turn_count < RISK_ANALYSTS_PER_ROUND:
        return THESIS_MODE
    return REBUTTAL_MODE


def get_total_risk_turn_limit(max_rebuttal_rounds: int) -> int:
    """Return the total number of risk turns before the judge should act."""

    safe_rebuttal_rounds = max(0, max_rebuttal_rounds)
    return RISK_ANALYSTS_PER_ROUND * (1 + safe_rebuttal_rounds)
