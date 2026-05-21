import json

from diverge.agents.managers.summary_agent import (
    ReportSummaryOutput,
    build_summary_agent_prompt,
    build_summary_agent_result,
)


def _base_state():
    return {
        "company_of_interest": "MSFT",
        "trade_date": "2026-04-01",
        "output_language": "en",
        "market_report": "Market trend remains constructive.",
        "sentiment_report": "Sentiment is neutral.",
        "news_report": "Cloud demand remains a catalyst.",
        "fundamentals_report": "Cash generation remains durable.",
        "trader_investment_plan": "Scale in gradually.",
        "investment_debate_state": {
            "bull_history": "Bull Analyst: upside remains intact.",
            "bear_history": "Bear Analyst: valuation is stretched.",
            "judge_decision": "Research Manager: BUY with discipline.",
        },
        "risk_debate_state": {
            "aggressive_history": "Aggressive Analyst: momentum supports adding.",
            "conservative_history": "Conservative Analyst: protect downside.",
            "neutral_history": "Neutral Analyst: keep balanced sizing.",
            "judge_decision": "Portfolio Manager: BUY with tight risk controls.",
        },
    }


def test_summary_agent_builds_concise_report_summary_from_final_state():
    prompt, _tools, _metadata = build_summary_agent_prompt(_base_state())
    result = build_summary_agent_result(
        _base_state(),
        response_content="BUY with disciplined sizing because cash generation is durable while valuation risk remains the key constraint.",
    )

    assert result["report_summary"].startswith("BUY with disciplined sizing")
    assert "about 150 English words" in prompt.system_message
    assert "Do not include markdown headings" in prompt.system_message
    assert "private reasoning" in prompt.system_message
    assert "Bull Analyst: upside remains intact." in prompt.system_message
    assert "Conservative Analyst: protect downside." in prompt.system_message


def test_summary_agent_strips_model_self_talk_from_report_summary():
    result = build_summary_agent_result(
        _base_state(),
        response_content=(
            "好的，用户要求我作为Summary Agent来创建一个关于SMH的执行摘要。"
            "目标长度大约300个中文字符，我需要写成紧凑段落。"
            "基于对SMH截至2026年5月11日的多维度研究辩论，"
            "最终投资决策为**减持（UNDERWEIGHT）**。"
            "主要论点是估值偏高、动能转弱，风险来自AI资本开支周期和政策转向。"
        ),
    )

    assert result["report_summary"].startswith("基于对SMH")
    assert "用户要求" not in result["report_summary"]
    assert "我需要" not in result["report_summary"]
    assert "**" not in result["report_summary"]


def test_summary_agent_uses_adk_output_schema_when_model_supports_it():
    payload = {
            "summary_text": "HOLD while waiting for a cleaner trigger.",
            "language": "en",
            "final_rating": "HOLD",
            "primary_action": "WATCH",
    }
    result = build_summary_agent_result(
        _base_state(),
        response_content=json.dumps(payload),
    )

    assert ReportSummaryOutput.model_validate(payload)
    assert result["report_summary"] == "HOLD while waiting for a cleaner trigger."
    assert result["report_summary_structured"]["final_rating"] == "HOLD"
