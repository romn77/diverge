import unittest
from unittest.mock import patch

from diverge.default_config import DEFAULT_CONFIG
from diverge.graph.conditional_logic import ConditionalLogic
from diverge.graph.trading_graph import DivergeGraph


class RiskDebateFlowTests(unittest.TestCase):
    def test_first_three_risk_turns_continue_into_thesis_cycle(self):
        logic = ConditionalLogic(max_risk_discuss_rounds=1)

        next_step = logic.should_continue_risk_analysis(
            {"risk_debate_state": {"count": 3, "latest_speaker": "Neutral"}}
        )

        self.assertEqual(next_step, "Aggressive Analyst")

    def test_risk_stops_after_initial_thesis_and_one_rebuttal_round(self):
        logic = ConditionalLogic(max_risk_discuss_rounds=1)

        next_step = logic.should_continue_risk_analysis(
            {"risk_debate_state": {"count": 6, "latest_speaker": "Neutral"}}
        )

        self.assertEqual(next_step, "Portfolio Manager")

    @patch("diverge.graph.trading_graph.GraphSetup")
    @patch("diverge.graph.trading_graph.SignalProcessor")
    @patch("diverge.graph.trading_graph.Reflector")
    @patch("diverge.graph.trading_graph.Propagator")
    @patch("diverge.graph.trading_graph.FinancialSituationMemory")
    @patch("diverge.graph.trading_graph.create_llm_client")
    @patch("diverge.graph.trading_graph.set_config")
    @patch.object(DivergeGraph, "_create_tool_nodes", return_value={})
    @patch("diverge.graph.trading_graph.ConditionalLogic")
    def test_trading_graph_passes_round_limits_to_conditional_logic(
        self,
        conditional_logic_cls,
        _create_tool_nodes,
        _set_config,
        create_llm_client,
        _financial_situation_memory,
        _propagator,
        _reflector,
        _signal_processor,
        graph_setup_cls,
    ):
        create_llm_client.return_value.get_llm.return_value = object()
        graph_setup_cls.return_value.setup_graph.return_value = object()

        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 4

        DivergeGraph(selected_analysts=["market"], config=config)

        conditional_logic_cls.assert_called_once_with(
            max_debate_rounds=2,
            max_risk_discuss_rounds=4,
        )


if __name__ == "__main__":
    unittest.main()
