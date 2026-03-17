import functools
from tradingagents.agents.utils.agent_utils import get_language_instruction


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        messages = [
            {
                "role": "system",
                "content": f"""You are a trading agent analyzing market data to make investment decisions. Based on your analysis, provide a specific recommendation to buy, sell, or hold. Do not forget to utilize lessons from past decisions to learn from your mistakes. Here is some reflections from similar situations you traded in and the lessons learned: {past_memory_str}

Conclude your narrative analysis with 'FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**' as your final narrative line.

Then append a structured highlights block at the end of your response:

```json-highlights
{{
  "category": "trader",
  "signal": "BUY or HOLD or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence executive summary of your trading decision",
  "decision": "BUY or HOLD or SELL",
  "entry_exit": {{
    "action": "core trading action description",
    "exit_target": "target exit price or condition",
    "stop_loss": "stop loss level",
    "re_entry": "conditions for re-entry"
  }},
  "risk_factors": ["risk 1", "risk 2"]
}}
```

Keep the `json-highlights` fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.

{language_instruction}""",
            },
            context,
        ]

        result = llm.invoke(messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
