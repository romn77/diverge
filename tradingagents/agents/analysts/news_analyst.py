from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_global_news,
    get_language_instruction,
    get_news,
    get_research_note_style_instruction,
    get_trade_feedback_message,
)
from tradingagents.research.earnings import (
    build_earnings_workflow_context,
    inject_earnings_section,
)


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        earnings_context = build_earnings_workflow_context(
            trade_date=current_date,
            ticker=ticker,
            earnings_event=state.get("earnings_event"),
        )

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(query, start_date, end_date) for company-specific or targeted news searches, and get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + f"\n\n{earnings_context.prompt_instruction}"
            + """ After the markdown table, append exactly one structured highlights block in this exact format:

```json-highlights
{
  "category": "news",
  "signal": "BUY",
  "signal_confidence": "medium",
  "summary": "concise summary of the key news implications",
  "market_impact": "mixed",
  "key_events": [
    {
      "event": "event name/description",
      "impact": "description of market impact"
    }
  ],
  "macro_outlook": "forward-looking macro outlook"
}
```

Keep the `json-highlights` fence, JSON keys, and enum literals in English constants exactly as shown (`category` must be `news`; `signal` must be one of `BUY`, `HOLD`, `SELL`; `signal_confidence` must be one of `high`, `medium`, `low`; `market_impact` must be one of `positive`, `negative`, `neutral`, `mixed`). Free-form string values should follow the report language. `signal_confidence` and `macro_outlook` are optional when uncertain."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
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
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = inject_earnings_section(
                result.content,
                earnings_context.report_section,
            )

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
