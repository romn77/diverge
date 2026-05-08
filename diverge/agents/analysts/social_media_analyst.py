from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from diverge.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_news,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    web_search_evidence,
)
from diverge.research.search.session import current_search_context


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
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
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Use the get_news(query, start_date, end_date) tool to search for company-specific news and social media discussions. Try to look at all sources possible from social media to sentiment to news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
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

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "\n{style_instruction}"
                    "\n{language_instruction}"
                    "\n{trade_feedback_message}"
                    "\nFor your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(style_instruction=style_instruction)
        prompt = prompt.partial(language_instruction=language_instruction)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(trade_feedback_message=trade_feedback_message)

        chain = prompt | llm.bind_tools(tools)

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
            result = chain.invoke(state["messages"])
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

    return social_media_analyst_node
