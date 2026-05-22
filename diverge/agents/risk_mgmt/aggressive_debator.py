from diverge.agents.utils.agent_utils import (
    get_evidence_rules_instruction,
    get_language_instruction,
    get_risk_budget_role_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)
from diverge.agents.risk_mgmt.debate_phase import (
    REBUTTAL_MODE,
    get_risk_debate_mode,
)
from diverge.agents.risk_mgmt.prompt_builder import build_risk_debator_prompt
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "aggressive_analyst"


def build_aggressive_risk_prompt(state):
    risk_debate_state = state["risk_debate_state"]
    history = risk_debate_state.get("history", "")
    aggressive_history = risk_debate_state.get("aggressive_history", "")

    current_conservative_response = risk_debate_state.get(
        "current_conservative_response", ""
    )
    current_neutral_response = risk_debate_state.get("current_neutral_response", "")

    market_research_report = state["market_report"]
    sentiment_report = state["sentiment_report"]
    news_report = state["news_report"]
    fundamentals_report = state["fundamentals_report"]

    trader_decision = state["trader_investment_plan"]
    output_language = state.get("output_language", "en")
    language_instruction = get_language_instruction(output_language)
    style_instruction = get_research_note_style_instruction(output_language)
    trade_feedback_message = get_trade_feedback_message(state)
    evidence_rules_instruction = get_evidence_rules_instruction()
    decision_boundary_instruction = get_upstream_decision_boundary_instruction()
    risk_budget_instruction = get_risk_budget_role_instruction("aggressive")
    debate_mode = get_risk_debate_mode(risk_debate_state.get("count", 0))

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
        decision_boundary_instruction=decision_boundary_instruction,
        evidence_rules_instruction=evidence_rules_instruction,
        mode_instruction=mode_instruction,
        trader_decision=trader_decision,
        task_instruction=task_instruction,
        source_intro="Incorporate insights from the following sources into your arguments:",
        market_research_report=market_research_report,
        sentiment_report=sentiment_report,
        news_report=news_report,
        fundamentals_report=fundamentals_report,
        history=history,
        counterpart_context=counterpart_context,
        trade_feedback_message=trade_feedback_message,
        engagement_instruction=engagement_instruction,
        highlights_intro="Use",
        category="risk_aggressive",
        stance_label="Aggressive",
        style_instruction=style_instruction,
        language_instruction=language_instruction,
    )

    return (
        AdkPrompt(system_message=prompt),
        (),
        {
            "history": history,
            "aggressive_history": aggressive_history,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response", ""
            ),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"],
        },
    )
