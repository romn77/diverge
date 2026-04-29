import unittest

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableLambda

from diverge.agents.analysts.market_analyst import create_market_analyst
from diverge.agents.trader.trader import create_trader
from diverge.agents.utils.agent_utils import create_msg_delete
from diverge.graph.propagation import Propagator


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("Response", (), {"content": "stub response"})()

    def bind_tools(self, _tools):
        def _invoke(prompt):
            self.prompts.append(prompt.to_string())
            return AIMessage(content="market report", tool_calls=[])

        return RunnableLambda(_invoke)


class _FakeMemory:
    def get_memories(self, _curr_situation, n_matches=2):
        return [{"recommendation": f"memory {idx}"} for idx in range(n_matches)]


class TradeFeedbackPromptInjectionTests(unittest.TestCase):
    def test_propagator_places_trade_feedback_into_initial_messages(self):
        state = Propagator().create_initial_state(
            "MSFT",
            "2026-04-01",
            historical_trade_feedback="Historical trade feedback for ticker MSFT:\n1. Prior lesson",
        )

        self.assertIn("Historical trade feedback", state["messages"][0][1])

    def test_message_delete_preserves_trade_feedback_context(self):
        delete_node = create_msg_delete()
        state = {
            "messages": [HumanMessage(content="Analyze MSFT")],
            "historical_trade_feedback": "Historical trade feedback for ticker MSFT:\n1. Prior lesson",
        }

        result = delete_node(state)
        self.assertTrue(
            any(
                isinstance(message, HumanMessage)
                and "Historical trade feedback" in message.content
                for message in result["messages"]
                if not isinstance(message, RemoveMessage)
            )
        )

    def test_market_analyst_prompt_contains_historical_trade_feedback(self):
        llm = _FakeLLM()
        state = Propagator().create_initial_state(
            "MSFT",
            "2026-04-01",
            historical_trade_feedback="Historical trade feedback for ticker MSFT:\n1. Prior lesson",
        )

        node = create_market_analyst(llm)
        node(state)

        self.assertIn("Historical trade feedback for ticker MSFT", llm.prompts[0])

    def test_market_analyst_prompt_limits_price_history_to_120_trading_days(self):
        llm = _FakeLLM()
        state = Propagator().create_initial_state("MSFT", "2026-04-01")

        node = create_market_analyst(llm)
        node(state)

        self.assertIn("past 120 trading days", llm.prompts[0])
        self.assertIn("get_stock_data", llm.prompts[0])

    def test_trader_prompt_contains_historical_trade_feedback(self):
        llm = _FakeLLM()
        node = create_trader(llm, _FakeMemory())
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

        node(state)

        system_message = llm.prompts[0][0]["content"]
        self.assertIn("Historical trade feedback for ticker MSFT", system_message)


if __name__ == "__main__":
    unittest.main()
