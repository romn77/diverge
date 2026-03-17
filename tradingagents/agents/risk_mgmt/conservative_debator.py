from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.risk_mgmt.debate_phase import (
    REBUTTAL_MODE,
    get_risk_debate_mode,
)


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get(
            "current_aggressive_response", ""
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

        prompt = f"""As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains.

{mode_instruction}

Here is the trader's decision:

{trader_decision}

{task_instruction}
Draw from the following data sources to build a convincing case for a low-risk adjustment to the trader's decision:

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
  "category": "risk_conservative",
  "signal": "BUY or HOLD or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence summary of your conservative risk stance",
  "stance_label": "Conservative",
  "core_argument": "one sentence core thesis",
  "risk_assessment": "high or moderate or low",
  "key_recommendations": ["recommendation 1", "recommendation 2"]
}}
```
Keep the `json-highlights` fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.
{language_instruction}"""

        response = llm.invoke(prompt)

        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
