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

    @patch("diverge.graph.trading_graph.SignalProcessor")
    @patch("diverge.graph.trading_graph.Reflector")
    @patch("diverge.graph.trading_graph.Propagator")
    @patch("diverge.graph.trading_graph.FinancialSituationMemory")
    @patch("diverge.graph.trading_graph.create_adk_model")
    @patch("diverge.graph.trading_graph.AdkWorkflowRunner")
    @patch("diverge.graph.trading_graph.set_config")
    @patch.object(DivergeGraph, "_create_tool_nodes", return_value={})
    def test_trading_graph_passes_round_limits_to_adk_workflow_runner(
        self,
        _create_tool_nodes,
        _set_config,
        runner_cls,
        create_adk_model,
        _financial_situation_memory,
        _propagator,
        _reflector,
        _signal_processor,
    ):
        create_adk_model.return_value = object()

        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 4

        DivergeGraph(selected_analysts=["market"], config=config)

        kwargs = runner_cls.call_args.kwargs
        self.assertEqual(kwargs["max_debate_rounds"], 2)
        self.assertEqual(kwargs["max_risk_discuss_rounds"], 4)


if __name__ == "__main__":
    unittest.main()
