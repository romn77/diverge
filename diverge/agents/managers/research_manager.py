from diverge.agents.base import AgentCallSpec, DivergeAgentNode
from diverge.agents.utils.agent_utils import (
    get_evidence_rules_instruction,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)

from diverge.agents.utils.agent_utils import build_instrument_context
from diverge.runtime.messages import AdkPrompt


class ResearchManager(DivergeAgentNode):
    name = "research_manager"

    def build_call(self, state) -> AgentCallSpec:
        instrument_context = build_instrument_context(state["company_of_interest"])
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        evidence_rules_instruction = get_evidence_rules_instruction()
        decision_boundary_instruction = get_upstream_decision_boundary_instruction()

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = self.memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the research debate facilitator, your role is to critically evaluate this round of debate and produce a provisional research stance for the trader and Portfolio Manager: align with the bear analyst, align with the bull analyst, or recommend a neutral/hold research posture only if it is strongly justified based on the evidence.

{decision_boundary_instruction}
{evidence_rules_instruction}

Summarize the key points from both sides concisely, focusing on the most compelling evidence or reasoning. Your provisional recommendation must be clear and actionable for the trader, but it is not the final user-facing portfolio verdict. Avoid defaulting to Hold simply because both sides have valid points; commit to a stance grounded in the debate's strongest arguments.

Additionally, develop a detailed investment plan for the trader. This should include:

Your Recommendation: A decisive stance supported by the most convincing arguments.
Rationale: An explanation of why these arguments lead to your conclusion.
Strategic Actions: Concrete steps for implementing the recommendation.
Take into account your past mistakes on similar situations. Use these insights to refine your decision-making and ensure you are learning and improving. Present your analysis conversationally, as if speaking naturally, with a structured decision block at the end.

Here are your past reflections on mistakes:
\"{past_memory_str}\"

{trade_feedback_message}

{instrument_context}

Here is the debate:
Debate History:
{history}

After your complete decision, append a structured highlights block in the following exact format:

```json-highlights
{{
  "category": "research_decision",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence executive summary of your ruling",
  "stance": "bullish or neutral or bearish or mixed",
  "decision": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "aligned_with": "bull or bear",
  "rationale": "one sentence explaining why you sided this way",
  "action_items": ["action 1", "action 2", "action 3"],
  "evidence_blocks": [
    {{
      "claim": "research synthesis claim",
      "evidence": "specific debate or analyst-report evidence",
      "source": "bull researcher, bear researcher, or analyst report",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "high or medium or low",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ],
  "unknowns": ["material unresolved research question"]
}}
```

Keep the fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in another language; free-form string values should follow the report language.

{style_instruction}
{language_instruction}"""
        return AgentCallSpec(
            prompt=AdkPrompt(system_message=prompt),
            metadata={
                "history": investment_debate_state.get("history", ""),
                "bear_history": investment_debate_state.get("bear_history", ""),
                "bull_history": investment_debate_state.get("bull_history", ""),
                "count": investment_debate_state["count"],
            },
        )

    def apply_response(self, state, spec, response) -> dict:
        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": spec.metadata["history"],
            "bear_history": spec.metadata["bear_history"],
            "bull_history": spec.metadata["bull_history"],
            "current_response": response.content,
            "count": spec.metadata["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }
