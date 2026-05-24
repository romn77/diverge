import unittest

from diverge.agents.analysts.market_analyst import build_market_analyst_prompt
from diverge.agents.trader.trader import build_trader_prompt
from diverge.runtime.state import create_initial_state


class _FakeMemory:
    def get_memories(self, _curr_situation, n_matches=2):
        return [{"recommendation": f"memory {idx}"} for idx in range(n_matches)]


class TradeFeedbackPromptInjectionTests(unittest.TestCase):
    def test_create_initial_state_places_trade_feedback_into_initial_messages(self):
        state = create_initial_state(
            "MSFT",
            "2026-04-01",
            historical_trade_feedback="Historical trade feedback for ticker MSFT:\n1. Prior lesson",
        )

        self.assertIn("Historical trade feedback", state["messages"][0][1])

    def test_market_analyst_prompt_contains_historical_trade_feedback(self):
        state = create_initial_state(
            "MSFT",
            "2026-04-01",
            historical_trade_feedback="Historical trade feedback for ticker MSFT:\n1. Prior lesson",
        )

        prompt, _tools, _metadata = build_market_analyst_prompt(state)

        self.assertIn(
            "Historical trade feedback for ticker MSFT",
            prompt.to_string(),
        )

    def test_market_analyst_prompt_limits_price_history_to_120_trading_days(self):
        state = create_initial_state("MSFT", "2026-04-01")

        prompt, _tools, _metadata = build_market_analyst_prompt(state)
        prompt_text = prompt.to_string()

        self.assertIn("past 120 trading days", prompt_text)
        self.assertIn("get_stock_data", prompt_text)

    def test_trader_prompt_contains_historical_trade_feedback(self):
        state = {
            "company_of_interest": "MSFT",
            "investment_plan": "Buy the pullback.",
            "market_report": "market report",
            "sentiment_report": "sentiment report",
            "news_report": "news report",
            "fundamentals_report": "fundamentals report",
            "output_language": "en",
            "historical_trade_feedback": "Historical trade feedback for ticker MSFT:\n1. Prior lesson",
        }

        prompt, _tools, _metadata = build_trader_prompt(state, _FakeMemory())

        system_message = prompt.system_message
        self.assertIn("Historical trade feedback for ticker MSFT", system_message)


if __name__ == "__main__":
    unittest.main()
