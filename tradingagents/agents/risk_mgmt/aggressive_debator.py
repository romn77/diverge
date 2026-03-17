from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.risk_mgmt.debate_phase import (
    REBUTTAL_MODE,
    get_risk_debate_mode,
)


def create_aggressive_debator(llm):
    def aggressive_node(state) -> dict:
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

        prompt = f"""As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views.

{mode_instruction}

Here is the trader's decision:

{trader_decision}

{task_instruction}
Incorporate insights from the following sources into your arguments:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history}
{counterpart_context}

{engagement_instruction}
After your complete argument, append a structured highlights block:

```json-highlights
{{
  "category": "risk_aggressive",
  "signal": "BUY or HOLD or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence summary of your aggressive risk stance",
  "stance_label": "Aggressive",
  "core_argument": "one sentence core thesis",
  "risk_assessment": "high or moderate or low",
  "key_recommendations": ["recommendation 1", "recommendation 2"]
}}
```
Keep the `json-highlights` fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.
{language_instruction}"""

        response = llm.invoke(prompt)

        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response", ""
            ),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
