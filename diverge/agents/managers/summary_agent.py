from diverge.agents.utils.agent_utils import get_language_instruction


def _section(title: str, content: str | None, limit: int = 8000) -> str:
    text = (content or "").strip()
    if not text:
        return f"## {title}\nNot available."
    if len(text) > limit:
        text = text[:limit].rstrip() + "\n...[truncated]"
    return f"## {title}\n{text}"


def create_summary_agent(llm):
    def summary_agent_node(state) -> dict:
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        debate = state.get("investment_debate_state") or {}
        risk = state.get("risk_debate_state") or {}

        full_report_context = "\n\n".join(
            [
                _section("Market Analyst", state.get("market_report")),
                _section("Social Analyst", state.get("sentiment_report")),
                _section("News Analyst", state.get("news_report")),
                _section("Fundamentals Analyst", state.get("fundamentals_report")),
                _section("Bull Researcher", debate.get("bull_history")),
                _section("Bear Researcher", debate.get("bear_history")),
                _section("Research Manager", debate.get("judge_decision")),
                _section("Trader", state.get("trader_investment_plan")),
                _section("Aggressive Risk Analyst", risk.get("aggressive_history")),
                _section("Conservative Risk Analyst", risk.get("conservative_history")),
                _section("Neutral Risk Analyst", risk.get("neutral_history")),
                _section("Portfolio Manager", risk.get("judge_decision")),
            ]
        )

        prompt = f"""You are the Summary Agent for a multi-agent trading research report.

Create a concise executive summary of the complete report for {state["company_of_interest"]} on {state["trade_date"]}.

Requirements:
- Target length: about 300 Chinese characters when the output language is Chinese, or about 150 English words when the output language is English.
- Write one compact paragraph, not bullet points.
- Cover the final decision, the main thesis, the most important supporting evidence, the primary risks, and the practical trading action.
- Do not include markdown headings, code fences, JSON, citations, or meta commentary.
- Do not invent facts that are not present in the report context.

Complete report context:

{full_report_context}

{language_instruction}"""

        response = llm.invoke(prompt)
        return {"report_summary": response.content.strip()}

    return summary_agent_node
