from .portfolio_manager import create_portfolio_manager


def create_risk_manager(llm, memory):
    """Backward-compatible alias for the renamed portfolio manager."""
    return create_portfolio_manager(llm, memory)
