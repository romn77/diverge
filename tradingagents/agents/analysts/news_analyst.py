from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_news,
    get_global_news,
    get_language_instruction,
)


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(query, start_date, end_date) for company-specific or targeted news searches, and get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
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
                    "\n{language_instruction}"
                    "For your reference, the current date is {current_date}. We are looking at the company {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)
        prompt = prompt.partial(language_instruction=language_instruction)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
