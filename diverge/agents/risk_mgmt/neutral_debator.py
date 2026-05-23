from diverge.agents.report_output import NeutralRiskStructuredOutput
from diverge.agents.agent_context import (
    build_agent_prompt_context,
    risk_debate_from_state,
    upstream_reports_from_state,
)
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.agents.risk_mgmt.output import commit_risk_debater_output
from diverge.agents.utils.agent_utils import get_risk_budget_role_instruction
from diverge.agents.risk_mgmt.debate_phase import (
    REBUTTAL_MODE,
    get_risk_debate_mode,
)
from diverge.agents.risk_mgmt.prompt_builder import build_risk_debator_prompt
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "neutral_analyst"


def build_neutral_risk_prompt(state):
    context = build_agent_prompt_context(state)
    reports = upstream_reports_from_state(state)
    risk_context = risk_debate_from_state(state)
    history = risk_context.history
    current_aggressive_response = risk_context.current_aggressive_response
    current_conservative_response = risk_context.current_conservative_response

    trader_decision = state["trader_investment_plan"]
    risk_budget_instruction = get_risk_budget_role_instruction("neutral")
    debate_mode = get_risk_debate_mode(risk_context.count)

    if debate_mode == REBUTTAL_MODE:
        mode_instruction = """Debate mode: rebuttal
This is a rebuttal round. Respond directly to the latest aggressive and conservative arguments. Challenge where either side becomes too extreme and defend a balanced risk posture with specific evidence."""
        task_instruction = """Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious."""
        engagement_instruction = """Engage actively by analyzing both sides critically, addressing weaknesses in the aggressive and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes."""
    else:
        mode_instruction = """Debate mode: thesis
This is the opening cycle of the risk debate. Lead with your own neutral thesis on the trader's plan, balancing upside and downside while proposing a moderate execution path. If earlier comments exist, you may reference them briefly, but do not structure the response as a point-by-point rebuttal and do not mention missing counterpart arguments."""
        task_instruction = """Your task is to present a standalone neutral risk thesis for the trader's decision, balancing upside participation against downside protection and proposing a moderate execution path."""
        engagement_instruction = """Focus on building your own balanced case in a conversational voice. Explain how you would combine participation and protection, and avoid meta commentary about whether counterpart arguments are available."""

    if debate_mode == REBUTTAL_MODE:
        counterpart_context = (
            f"Here is the last response from the aggressive analyst: {current_aggressive_response or 'None yet.'} "
            f"Here is the last response from the conservative analyst: {current_conservative_response or 'None yet.'}."
        )
    else:
        parts = []
        if current_aggressive_response:
            parts.append(
                f"Here is the last response from the aggressive analyst: {current_aggressive_response}"
            )
        if current_conservative_response:
            parts.append(
                f"Here is the last response from the conservative analyst: {current_conservative_response}"
            )
        counterpart_context = " ".join(parts)

    prompt = build_risk_debator_prompt(
        posture_title="neutral",
        opening_role=(
            "As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the "
            "potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, "
            "evaluating the upsides and downsides while factoring in broader market trends, potential economic "
            "shifts, and diversification strategies."
        ),
        risk_budget_instruction=risk_budget_instruction,
        decision_boundary_instruction=context.decision_boundary_instruction,
        evidence_rules_instruction=context.evidence_rules_instruction,
        mode_instruction=mode_instruction,
        trader_decision=trader_decision,
        task_instruction=task_instruction,
        source_intro="Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:",
        market_research_report=reports.market,
        sentiment_report=reports.sentiment,
        news_report=reports.news,
        fundamentals_report=reports.fundamentals,
        history=history,
        counterpart_context=counterpart_context,
        trade_feedback_message=context.trade_feedback_message,
        engagement_instruction=engagement_instruction,
        highlights_intro="Output conversationally, then use",
        category="risk_neutral",
        stance_label="Neutral",
        style_instruction=context.style_instruction,
        language_instruction=context.language_instruction,
    )

    return (
        AdkPrompt(system_message=prompt),
        (),
        {
            "history": history,
            "aggressive_history": risk_context.aggressive_history,
            "conservative_history": risk_context.conservative_history,
            "neutral_history": risk_context.neutral_history,
            "current_aggressive_response": risk_context.current_aggressive_response,
            "current_conservative_response": risk_context.current_conservative_response,
            "count": risk_context.count,
        },
    )


def commit_neutral_risk_output(state, structured_payload):
    return commit_risk_debater_output(
        state,
        structured_payload,
        schema=NeutralRiskStructuredOutput,
        agent_name=AGENT_NAME,
        speaker_label="Neutral Analyst",
        speaker="neutral",
    )


NEUTRAL_RISK_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name="Neutral Analyst",
    output_schema=NeutralRiskStructuredOutput,
    output_key="risk_neutral_structured",
    build_prompt=build_neutral_risk_prompt,
    commit_output=commit_neutral_risk_output,
)
