import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from diverge.default_config import DEFAULT_CONFIG
from diverge.runner import (
    ADK_NATIVE_ANALYSIS_RUNTIME,
    ANALYSIS_RUNTIME_ENV,
    AnalysisRequest,
    AnalysisTracker,
    build_analysis_config,
    resolve_analysis_runtime,
    run_analysis_streaming,
    save_report_to_disk,
)


class AnalysisTrackerTests(unittest.TestCase):
    def test_analysis_request_keeps_trading_session_date(self):
        request = AnalysisRequest(
            ticker="SPY",
            analysis_date="2024-03-15",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.analysis_date, "2024-03-15")

    def test_analysis_request_moves_us_weekend_to_previous_close(self):
        request = AnalysisRequest(
            ticker="SPY",
            analysis_date="2024-03-17",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.analysis_date, "2024-03-15")

    def test_analysis_request_moves_cn_holiday_to_previous_close(self):
        request = AnalysisRequest(
            ticker="600519.SH",
            analysis_date="2025-10-05",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.analysis_date, "2025-09-30")

    def test_analysis_request_infers_cn_exchange_for_plain_sz_ticker(self):
        request = AnalysisRequest(
            ticker="000830",
            analysis_date="2026-04-29",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.ticker, "000830.SZ")

    def test_analysis_request_applies_explicit_cn_exchange(self):
        request = AnalysisRequest(
            ticker="000830",
            ticker_exchange="SZ",
            analysis_date="2026-04-29",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.ticker, "000830.SZ")

    def test_analysis_request_rejects_beijing_exchange_ticker(self):
        with self.assertRaises(ValueError) as context:
            AnalysisRequest(
                ticker="920000",
                analysis_date="2026-04-29",
                analysts=["market"],
                research_depth=1,
                llm_provider="openai",
                quick_think_llm="gpt-5-mini",
                deep_think_llm="gpt-5.2",
                output_language="en",
                openai_reasoning_effort="medium",
            )

        self.assertIn("BJ", str(context.exception))
        self.assertIn("not supported", str(context.exception))

    def test_tracker_derives_three_state_stage_progress_from_agent_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = AnalysisTracker(["market", "news"], Path(temp_dir))

            initial = tracker.to_progress(status="pending", message="Queued")
            self.assertEqual(initial.stage_status["Analysts"], "not_started")
            self.assertEqual(initial.stage_status["Research"], "not_started")
            self.assertEqual(initial.stage_status["Portfolio"], "not_started")

            tracker.update_agent_status("Market Analyst", "in_progress")
            running = tracker.to_progress(
                status="running", message="Market analyst started"
            )
            self.assertEqual(running.stage_status["Analysts"], "processing")
            self.assertEqual(running.current_agent, "Market Analyst")

            tracker.update_agent_status("Market Analyst", "completed")
            tracker.update_agent_status("News Analyst", "completed")
            finished = tracker.to_progress(
                status="running", message="Analysts finished"
            )
            self.assertEqual(finished.stage_status["Analysts"], "completed")

    def test_tracker_writes_partial_reports_into_final_stage_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = AnalysisTracker(["market"], Path(temp_dir))

            tracker.update_report_section(
                "market_report", "# Market\n\nMomentum is positive."
            )
            tracker.update_report_section(
                "trader_investment_plan", "Reduce risk and wait."
            )

            market_path = Path(temp_dir) / "1_analysts" / "market.md"
            trader_path = Path(temp_dir) / "3_trading" / "trader.md"

            self.assertTrue(market_path.is_file())
            self.assertTrue(trader_path.is_file())
            self.assertIn(
                "Momentum is positive", market_path.read_text(encoding="utf-8")
            )
            self.assertIn("Reduce risk", trader_path.read_text(encoding="utf-8"))

    def test_tracker_surfaces_runtime_warning_progress_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = AnalysisTracker(["market"], Path(temp_dir))

            progress = tracker.consume_chunk(
                {
                    "runtime_warnings": [
                        {
                            "stage": "Portfolio Manager",
                            "kind": "transient_llm_error",
                            "message": "Portfolio Manager used fallback: Connection error.",
                        }
                    ]
                },
                status="running",
            )

            self.assertIsNotNone(progress)
            self.assertIn("Warning:", progress.message)
            self.assertEqual(progress.warnings[0]["stage"], "Portfolio Manager")

    def test_tracker_surfaces_adk_runtime_progress_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = AnalysisTracker(["market"], Path(temp_dir))

            progress = tracker.consume_chunk(
                {
                    "runtime_progress_events": [
                        {
                            "id": "runtime-progress-1",
                            "current_agent": "Market Analyst",
                            "message": "Market Analyst requested tools: get_stock_data.",
                        }
                    ]
                },
                status="running",
            )
            duplicate = tracker.consume_chunk(
                {
                    "runtime_progress_events": [
                        {
                            "id": "runtime-progress-1",
                            "current_agent": "Market Analyst",
                            "message": "Market Analyst requested tools: get_stock_data.",
                        }
                    ]
                },
                status="running",
            )

            self.assertIsNotNone(progress)
            self.assertEqual(
                progress.message,
                "Market Analyst requested tools: get_stock_data.",
            )
            self.assertEqual(progress.current_agent, "Market Analyst")
            self.assertIsNone(duplicate)

    def test_save_report_to_disk_keeps_fundamentals_report_and_writes_thesis_artifact(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            final_state = {
                "market_report": "# Market\n\nStable backdrop.",
                "sentiment_report": "# Sentiment\n\nNeutral buzz.",
                "news_report": "# News\n\nCatalysts remain active.",
                "fundamentals_report": (
                    "# Fundamentals\n\n"
                    "## DCF Summary\n\n"
                    "| Metric | Value |\n| --- | --- |\n| Fair Value / Share | $420.00 |\n\n"
                    "```json-highlights\n"
                    '{\n  "category": "fundamentals",\n  "signal": "BUY",\n'
                    '  "signal_confidence": "medium",\n  "summary": "Durable cash generation.",\n'
                    '  "metrics": [],\n  "financial_health": "Strong"\n}\n'
                    "```"
                ),
                "investment_plan": "Lean long with a quality bias.",
                "trader_investment_plan": "Build the position gradually.",
                "investment_debate_state": {
                    "bull_history": "Bull Analyst: Free cash flow remains durable.",
                    "bear_history": "Bear Analyst: Multiple compression is still a risk.",
                    "current_bull_response": "Bull Analyst: Final bull case only.",
                    "current_bear_response": "Bear Analyst: Final bear case only.",
                    "judge_decision": "Research Manager: BUY with disciplined sizing.",
                },
                "risk_debate_state": {
                    "aggressive_history": "Aggressive Analyst: Momentum confirms the setup.",
                    "conservative_history": "Conservative Analyst: Guard against event volatility.",
                    "neutral_history": "Neutral Analyst: Keep exposure balanced.",
                    "current_aggressive_response": "Aggressive Analyst: Final aggressive case only.",
                    "current_conservative_response": "Conservative Analyst: Final conservative case only.",
                    "current_neutral_response": "Neutral Analyst: Final neutral case only.",
                    "judge_decision": "Portfolio Manager: BUY with risk controls.",
                },
                "historical_trade_feedback": "Historical trade feedback for ticker MSFT:\n1. Respect the planned stop.",
                "historical_trade_reviews": [
                    {
                        "trade_id": "trade-1",
                        "review_type": "entry_review",
                        "thesis_assessment": "Thesis was grounded in durable cloud demand.",
                    }
                ],
                "runtime_warnings": [
                    {
                        "stage": "Portfolio Manager",
                        "kind": "transient_llm_error",
                        "message": "Portfolio Manager used fallback: Connection error.",
                    }
                ],
            }

            report_path = save_report_to_disk(final_state, "MSFT", Path(temp_dir))

            fundamentals_path = Path(temp_dir) / "1_analysts" / "fundamentals.md"
            bull_path = Path(temp_dir) / "2_research" / "bull.md"
            bear_path = Path(temp_dir) / "2_research" / "bear.md"
            aggressive_path = Path(temp_dir) / "4_risk" / "aggressive.md"
            conservative_path = Path(temp_dir) / "4_risk" / "conservative.md"
            neutral_path = Path(temp_dir) / "4_risk" / "neutral.md"
            thesis_path = Path(temp_dir) / "artifacts" / "thesis.json"
            trade_feedback_path = Path(temp_dir) / "artifacts" / "trade_feedback.json"
            runtime_warnings_path = (
                Path(temp_dir) / "artifacts" / "runtime_warnings.json"
            )

            self.assertTrue(report_path.is_file())
            self.assertTrue(fundamentals_path.is_file())
            self.assertTrue(bull_path.is_file())
            self.assertTrue(bear_path.is_file())
            self.assertTrue(aggressive_path.is_file())
            self.assertTrue(conservative_path.is_file())
            self.assertTrue(neutral_path.is_file())
            self.assertTrue(thesis_path.is_file())
            self.assertTrue(trade_feedback_path.is_file())
            self.assertTrue(runtime_warnings_path.is_file())
            self.assertEqual(
                bull_path.read_text(encoding="utf-8"),
                "Bull Analyst: Final bull case only.",
            )
            self.assertEqual(
                bear_path.read_text(encoding="utf-8"),
                "Bear Analyst: Final bear case only.",
            )
            self.assertEqual(
                aggressive_path.read_text(encoding="utf-8"),
                "Aggressive Analyst: Final aggressive case only.",
            )
            self.assertEqual(
                conservative_path.read_text(encoding="utf-8"),
                "Conservative Analyst: Final conservative case only.",
            )
            self.assertEqual(
                neutral_path.read_text(encoding="utf-8"),
                "Neutral Analyst: Final neutral case only.",
            )
            self.assertIn(
                "## DCF Summary", fundamentals_path.read_text(encoding="utf-8")
            )
            self.assertIn(
                "Runtime Warnings",
                report_path.read_text(encoding="utf-8"),
            )

            thesis_payload = json.loads(thesis_path.read_text(encoding="utf-8"))
            self.assertEqual(thesis_payload["type"], "thesis")
            self.assertEqual(thesis_payload["ticker"], "MSFT")

            trade_feedback_payload = json.loads(
                trade_feedback_path.read_text(encoding="utf-8")
            )
            self.assertEqual(trade_feedback_payload["type"], "trade_feedback")
            self.assertEqual(len(trade_feedback_payload["reviews"]), 1)

            runtime_warning_payload = json.loads(
                runtime_warnings_path.read_text(encoding="utf-8")
            )
            self.assertEqual(runtime_warning_payload["type"], "runtime_warnings")
            self.assertIn(
                "Connection error.",
                runtime_warning_payload["warnings"][0]["message"],
            )

    def test_run_analysis_streaming_requests_only_visible_trade_feedback(self):
        request = AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-03",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "diverge.runner.get_trade_feedback_payload",
                return_value={"prompt": "", "reviews": []},
            ) as mock_feedback:
                generator = run_analysis_streaming(request, Path(temp_dir))
                next(generator)
                generator.close()

        mock_feedback.assert_called_once_with(
            "MSFT",
            reports_dir=None,
            analysis_date="2026-04-02",
            visible_trade_ids=None,
        )

    def test_build_analysis_config_can_prefer_massive_for_us_market_data(self):
        request = AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-03",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
            market_data_source="massive",
        )

        config = build_analysis_config(request)

        self.assertEqual(
            config["market_overrides"]["us"]["core_stock_apis"],
            "massive",
        )
        self.assertEqual(
            config["market_overrides"]["us"]["technical_indicators"],
            "local",
        )
        self.assertEqual(
            config["market_overrides"]["us"]["fundamental_data"],
            "fmp,alpha_vantage,yfinance",
        )

    def test_build_analysis_config_preserves_default_us_route_when_source_omitted(
        self,
    ):
        request = AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-03",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        with patch.dict(
            DEFAULT_CONFIG["market_overrides"]["us"],
            {"core_stock_apis": "yfinance"},
        ):
            config = build_analysis_config(request)

        self.assertEqual(
            config["market_overrides"]["us"]["core_stock_apis"],
            "yfinance",
        )

    def test_build_analysis_config_preserves_resolved_backend_url(self):
        request = AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-03",
            analysts=["market"],
            research_depth=1,
            llm_provider="google",
            quick_think_llm="gemini-2.5-flash",
            deep_think_llm="gemini-2.5-pro",
            output_language="en",
            backend_url="https://cc.z2blog.com",
            google_thinking_level="high",
        )

        config = build_analysis_config(request)

        self.assertEqual(config["backend_url"], "https://cc.z2blog.com")

    def test_resolve_analysis_runtime_defaults_to_adk_native(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_analysis_runtime(), ADK_NATIVE_ANALYSIS_RUNTIME)

    def test_resolve_analysis_runtime_accepts_adk_native(self):
        self.assertEqual(
            resolve_analysis_runtime(ADK_NATIVE_ANALYSIS_RUNTIME),
            ADK_NATIVE_ANALYSIS_RUNTIME,
        )

    def test_resolve_analysis_runtime_rejects_legacy_wrapper(self):
        with self.assertRaises(ValueError):
            resolve_analysis_runtime("legacy_adk_wrapper")

    def test_run_analysis_streaming_can_dispatch_to_adk_native_runtime(self):
        request = AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-03",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        def fake_stream_analysis_state_chunks(**kwargs):
            self.assertEqual(kwargs["selected_analysts"], ["market"])
            self.assertEqual(kwargs["init_agent_state"]["company_of_interest"], "MSFT")
            yield {
                "market_report": "ADK native market report",
                "runtime_progress_events": [
                    {
                        "id": "runtime-progress-1",
                        "current_agent": "Market Analyst",
                        "message": "Market Analyst completed with market report.",
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            from diverge.runtime.adk_native import runner as adk_native_runner

            with patch.dict(
                "os.environ",
                {ANALYSIS_RUNTIME_ENV: ADK_NATIVE_ANALYSIS_RUNTIME},
            ):
                with patch(
                    "diverge.runner.get_trade_feedback_payload",
                    return_value={"prompt": "", "reviews": []},
                ):
                    with patch.object(
                        adk_native_runner,
                        "stream_analysis_state_chunks",
                        fake_stream_analysis_state_chunks,
                    ):
                        generator = run_analysis_streaming(
                            request,
                            Path(temp_dir),
                        )
                        first = next(generator)
                        second = next(generator)
                        try:
                            while True:
                                next(generator)
                        except StopIteration as stop:
                            final_state = stop.value

        self.assertIn("Analyzing MSFT", first.message)
        self.assertEqual(
            second.message,
            "Market Analyst completed with market report.",
        )
        self.assertEqual(final_state["market_report"], "ADK native market report")


if __name__ == "__main__":
    unittest.main()
