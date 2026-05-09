from diverge.agents.base import DivergeAgentNode
from diverge.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
)
from diverge.agents.utils.news_data_tools import get_news
from diverge.agents.utils.search_tools import web_search_evidence
from diverge.research.search.session import current_search_context
from diverge.runtime.messages import AdkPrompt


class SocialMediaAnalyst(DivergeAgentNode):
    name = "social_media_analyst"

    def run(self, state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)

        tools = [
            get_news,
            web_search_evidence,
        ]

        web_search_instruction = """Web Search is an optional evidence supplement. You may use web_search_evidence at most 2 times in this analyst step. Prefer existing financial news tools first. Use Web Search only for fresh-news verification, missing coverage, Chinese/local sources, or source-backed risks/catalysts. If Web Search returns no results or warnings, continue with available tools and clearly note the limitation. Do not make web-search-backed claims unless supported by the returned evidence."""

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Use the get_news(ticker, start_date, end_date) tool for company-specific news; use web_search_evidence(query, purpose, max_results) only when you need a search-style query or source-backed supplement. Try to look at all sources possible from social media to sentiment to news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + f"\n\n{web_search_instruction}"
            + """ After the markdown table, also append a structured highlights block. Keep the fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in Chinese; free-form string values should follow the report language.

```json-highlights
{
  "category": "sentiment",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence executive summary of sentiment analysis",
  "overall_sentiment": "positive or negative or neutral or mixed",
  "sentiment_score": "score like 65/100 if determinable",
  "key_topics": ["topic1", "topic2", "topic3"],
  "social_buzz": "high or moderate or low"
}
```""",
        )

        prompt = AdkPrompt(
            system_message=(
                "You are a helpful AI assistant, collaborating with other assistants."
                " Use the provided tools to progress towards answering the question."
                " If you are unable to fully answer, that's OK; another assistant with different tools"
                " will help where you left off. Execute what you can to make progress."
                " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL** or deliverable,"
                " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL** so the team knows to stop."
                f" You have access to the following tools: {', '.join([tool.name for tool in tools])}.\n{system_message}"
                f"\n{style_instruction}"
                f"\n{language_instruction}"
                f"\n{trade_feedback_message}"
                f"\nFor your reference, the current date is {current_date}. {instrument_context}"
            ),
            messages=tuple(state["messages"]),
        )

        context_token = None
        parent_context = current_search_context.get()
        if parent_context is not None:
            context_token = current_search_context.set(
                parent_context.model_copy(
                    update={
                        "agent": "Social Analyst",
                        "ticker": ticker,
                        "analysis_date": current_date,
                        "language": output_language,
                    }
                )
            )
        try:
            result = self.llm.bind_tools(tools).invoke(prompt)
        finally:
            if context_token is not None:
                current_search_context.reset(context_token)

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }


def create_social_media_analyst(llm):
    return SocialMediaAnalyst(llm)
