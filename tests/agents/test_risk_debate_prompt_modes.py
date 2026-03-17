import unittest

from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import (
    create_conservative_debator,
)
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator


class _FakeResponse:
    def __init__(self, content="stub response"):
        self.content = content


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return _FakeResponse()


def _base_state():
    return {
        "market_report": "market report",
        "sentiment_report": "sentiment report",
        "news_report": "news report",
        "fundamentals_report": "fundamentals report",
        "trader_investment_plan": "trader plan",
        "output_language": "en",
        "risk_debate_state": {
            "history": "risk history",
            "aggressive_history": "aggressive history",
            "conservative_history": "conservative history",
            "neutral_history": "neutral history",
            "current_aggressive_response": "agg response",
            "current_conservative_response": "con response",
            "current_neutral_response": "neu response",
            "latest_speaker": "Aggressive",
            "count": 1,
        },
    }


class RiskDebatePromptModeTests(unittest.TestCase):
    def test_risk_debators_use_thesis_mode_in_opening_cycle(self):
        cases = ["aggressive", "conservative", "neutral"]

        for name in cases:
            with self.subTest(node=name):
                llm = _FakeLLM()
                node = {
                    "aggressive": create_aggressive_debator,
                    "conservative": create_conservative_debator,
                    "neutral": create_neutral_debator,
                }[name](llm)
                state = _base_state()
                state["risk_debate_state"]["count"] = 0
                state["risk_debate_state"]["current_aggressive_response"] = ""
                state["risk_debate_state"]["current_conservative_response"] = ""
                state["risk_debate_state"]["current_neutral_response"] = ""

                node(state)

                prompt = llm.prompts[-1]
                self.assertIn("Debate mode: thesis", prompt)
                self.assertNotIn(
                    "respond directly to each point made by the conservative and neutral analysts",
                    prompt.lower(),
                )

    def test_risk_debators_use_rebuttal_mode_after_opening_cycle(self):
        cases = [
            ("aggressive", create_aggressive_debator),
            ("conservative", create_conservative_debator),
            ("neutral", create_neutral_debator),
        ]

        for name, factory in cases:
            with self.subTest(node=name):
                llm = _FakeLLM()
                node = factory(llm)
                state = _base_state()
                state["risk_debate_state"]["count"] = 3

                node(state)

                prompt = llm.prompts[-1]
                self.assertIn("Debate mode: rebuttal", prompt)

    def test_thesis_mode_omits_missing_counterpart_placeholder(self):
        FORBIDDEN_FRAGMENTS = [
            "No prior conservative argument is available in this opening cycle.",
            "No prior aggressive argument is available in this opening cycle.",
            "No prior neutral argument is available in this opening cycle.",
        ]

        cases = [
            ("aggressive", create_aggressive_debator),
            ("conservative", create_conservative_debator),
            ("neutral", create_neutral_debator),
        ]

        for name, factory in cases:
            with self.subTest(node=name):
                llm = _FakeLLM()
                node = factory(llm)
                state = _base_state()
                state["risk_debate_state"]["count"] = 0
                state["risk_debate_state"]["current_aggressive_response"] = ""
                state["risk_debate_state"]["current_conservative_response"] = ""
                state["risk_debate_state"]["current_neutral_response"] = ""

                node(state)

                prompt = llm.prompts[-1]
                for fragment in FORBIDDEN_FRAGMENTS:
                    self.assertNotIn(
                        fragment,
                        prompt,
                        msg=(
                            f"[{name}] thesis-mode prompt must not contain "
                            f"missing-counterpart placeholder: {fragment!r}"
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
