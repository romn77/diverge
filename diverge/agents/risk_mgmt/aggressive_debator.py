from diverge.agents.report_output import AggressiveRiskStructuredOutput
from diverge.agents.agent_context import (
    build_agent_prompt_context,
    risk_debate_from_state,
    upstream_reports_from_state,
)
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.agents.risk_mgmt.output import commit_risk_debater_output
from diverge.agents.utils.agent_utils import (
    get_risk_budget_role_instruction,
)
from diverge.agents.risk_mgmt.debate_phase import (
    REBUTTAL_MODE,
    get_risk_debate_mode,
)
from diverge.agents.risk_mgmt.prompt_builder import build_risk_debator_prompt
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "aggressive_analyst"


def build_aggressive_risk_prompt(state):
    context = build_agent_prompt_context(state)
    reports = upstream_reports_from_state(state)
    risk_context = risk_debate_from_state(state)
    history = risk_context.history
    current_conservative_response = risk_context.current_conservative_response
    current_neutral_response = risk_context.current_neutral_response

    trader_decision = state["trader_investment_plan"]
    risk_budget_instruction = get_risk_budget_role_instruction("aggressive")
    debate_mode = get_risk_debate_mode(risk_context.count)

    if debate_mode == REBUTTAL_MODE:
        mode_instruction = """Debate mode: rebuttal
This is a rebuttal round. Respond directly to each point made by the conservative and neutral analysts. Counter their claims with data-driven rebuttals, explain where their caution misses upside, and defend why your higher-risk posture is superior."""
        task_instruction = """Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward."""
        engagement_instruction = """Engage actively by addressing any specific concerns raised, refuting the weaknesses in their logic, and asserting the benefits of risk-taking to outpace market norms. Maintain a focus on debating and persuading, presented conversationally in your own voice. Challenge each counterpoint to underscore why a high-risk approach is optimal."""
    else:
        mode_instruction = """Debate mode: thesis
This is the opening cycle of the risk debate. Lead with your own aggressive thesis on the trader's plan, emphasizing upside, catalysts, and the bold actions you support. If earlier comments exist, you may reference them briefly, but do not structure the response as a point-by-point rebuttal and do not mention missing counterpart arguments."""
        task_instruction = """Your task is to present a standalone aggressive risk thesis for the trader's decision, showing where decisive positioning, asymmetry, or optionality could justify leaning into risk."""
        engagement_instruction = """Focus on building your own high-conviction case in a conversational voice. Recommend the bold actions, sizing, or risk budget adjustments you believe best capture upside, and avoid meta commentary about whether counterpart arguments are available."""

    if debate_mode == REBUTTAL_MODE:
        counterpart_context = (
            f"Here are the last arguments from the conservative analyst: {current_conservative_response or 'None yet.'}\n"
            f"Here are the last arguments from the neutral analyst: {current_neutral_response or 'None yet.'}"
        )
    else:
        parts = []
        if current_conservative_response:
            parts.append(
                f"Here are the last arguments from the conservative analyst: {current_conservative_response}"
            )
        if current_neutral_response:
            parts.append(
                f"Here are the last arguments from the neutral analyst: {current_neutral_response}"
            )
        counterpart_context = "\n".join(parts)

    prompt = build_risk_debator_prompt(
        posture_title="aggressive",
        opening_role=(
            "As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, "
            "emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, "
            "focus intently on the potential upside, growth potential, and innovative benefits-even when these come "
            "with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments "
            "and challenge the opposing views."
        ),
        risk_budget_instruction=risk_budget_instruction,
        decision_boundary_instruction=context.decision_boundary_instruction,
        evidence_rules_instruction=context.evidence_rules_instruction,
        mode_instruction=mode_instruction,
        trader_decision=trader_decision,
        task_instruction=task_instruction,
        source_intro="Incorporate insights from the following sources into your arguments:",
        market_research_report=reports.market,
        sentiment_report=reports.sentiment,
        news_report=reports.news,
        fundamentals_report=reports.fundamentals,
        history=history,
        counterpart_context=counterpart_context,
        trade_feedback_message=context.trade_feedback_message,
        engagement_instruction=engagement_instruction,
        highlights_intro="Use",
        category="risk_aggressive",
        stance_label="Aggressive",
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
            "current_conservative_response": risk_context.current_conservative_response,
            "current_neutral_response": risk_context.current_neutral_response,
            "count": risk_context.count,
        },
    )


def commit_aggressive_risk_output(state, structured_payload):
    return commit_risk_debater_output(
        state,
        structured_payload,
        schema=AggressiveRiskStructuredOutput,
        agent_name=AGENT_NAME,
        speaker_label="Aggressive Analyst",
        speaker="aggressive",
    )


AGGRESSIVE_RISK_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name="Aggressive Analyst",
    output_schema=AggressiveRiskStructuredOutput,
    output_key="risk_aggressive_structured",
    build_prompt=build_aggressive_risk_prompt,
    commit_output=commit_aggressive_risk_output,
)
