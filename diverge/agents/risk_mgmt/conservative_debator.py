from diverge.agents.report_output import ConservativeRiskStructuredOutput
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


AGENT_NAME = "conservative_analyst"


def build_conservative_risk_prompt(state):
    context = build_agent_prompt_context(state)
    reports = upstream_reports_from_state(state)
    risk_context = risk_debate_from_state(state)
    history = risk_context.history
    current_aggressive_response = risk_context.current_aggressive_response
    current_neutral_response = risk_context.current_neutral_response

    trader_decision = state["trader_investment_plan"]
    risk_budget_instruction = get_risk_budget_role_instruction("conservative")
    debate_mode = get_risk_debate_mode(risk_context.count)

    if debate_mode == REBUTTAL_MODE:
        mode_instruction = """Debate mode: rebuttal
This is a rebuttal round. Respond directly to the latest points from the aggressive and neutral analysts. Expose where their arguments underweight downside, liquidity stress, volatility, or sustainability risk."""
        task_instruction = """Your task is to actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability."""
        engagement_instruction = """Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets. Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches."""
    else:
        mode_instruction = """Debate mode: thesis
This is the opening cycle of the risk debate. Lead with your own conservative thesis on the trader's plan, focusing on capital preservation, volatility control, and downside containment. If earlier comments exist, you may reference them briefly, but do not structure the response as a point-by-point rebuttal and do not mention missing counterpart arguments."""
        task_instruction = """Your task is to present a standalone conservative risk thesis for the trader's decision, identifying loss scenarios, drawdown risks, and the protective adjustments required to preserve capital."""
        engagement_instruction = """Focus on building your own low-risk case in a conversational voice. Recommend hedges, position limits, or timing adjustments that reduce downside, and avoid meta commentary about whether counterpart arguments are available."""

    if debate_mode == REBUTTAL_MODE:
        counterpart_context = (
            f"Here is the last response from the aggressive analyst: {current_aggressive_response or 'None yet.'}\n"
            f"Here is the last response from the neutral analyst: {current_neutral_response or 'None yet.'}"
        )
    else:
        parts = []
        if current_aggressive_response:
            parts.append(
                f"Here is the last response from the aggressive analyst: {current_aggressive_response}"
            )
        if current_neutral_response:
            parts.append(
                f"Here is the last response from the neutral analyst: {current_neutral_response}"
            )
        counterpart_context = "\n".join(parts)

    prompt = build_risk_debator_prompt(
        posture_title="conservative",
        opening_role=(
            "As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, "
            "and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully "
            "assessing potential losses, economic downturns, and market volatility. When evaluating the trader's "
            "decision or plan, critically examine high-risk elements, pointing out where the decision may expose "
            "the firm to undue risk and where more cautious alternatives could secure long-term gains."
        ),
        risk_budget_instruction=risk_budget_instruction,
        decision_boundary_instruction=context.decision_boundary_instruction,
        evidence_rules_instruction=context.evidence_rules_instruction,
        mode_instruction=mode_instruction,
        trader_decision=trader_decision,
        task_instruction=task_instruction,
        source_intro="Draw from the following data sources to build a convincing case for a low-risk adjustment to the trader's decision:",
        market_research_report=reports.market,
        sentiment_report=reports.sentiment,
        news_report=reports.news,
        fundamentals_report=reports.fundamentals,
        history=history,
        counterpart_context=counterpart_context,
        trade_feedback_message=context.trade_feedback_message,
        engagement_instruction=engagement_instruction,
        highlights_intro="Use",
        category="risk_conservative",
        stance_label="Conservative",
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
            "current_neutral_response": risk_context.current_neutral_response,
            "count": risk_context.count,
        },
    )


def commit_conservative_risk_output(state, structured_payload):
    return commit_risk_debater_output(
        state,
        structured_payload,
        schema=ConservativeRiskStructuredOutput,
        agent_name=AGENT_NAME,
        speaker_label="Conservative Analyst",
        speaker="conservative",
    )


CONSERVATIVE_RISK_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name="Conservative Analyst",
    output_schema=ConservativeRiskStructuredOutput,
    output_key="risk_conservative_structured",
    build_prompt=build_conservative_risk_prompt,
    commit_output=commit_conservative_risk_output,
)
