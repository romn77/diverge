from typing import Any

from diverge.agents.analyst_turn import AnalystTurn
from diverge.agents.report_output import (
    NewsReportStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.agent_context import build_agent_prompt_context
from diverge.agents.utils.agent_utils import (
    get_analyst_evidence_role_instruction,
)
from diverge.agents.utils.news_data_tools import get_global_news, get_news
from diverge.agents.utils.search_tools import web_search_evidence
from diverge.research.earnings import (
    build_earnings_workflow_context,
    inject_earnings_section,
)
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


NEWS_ANALYST_TOOLS = (
    get_news,
    get_global_news,
    web_search_evidence,
)


def build_news_analyst_prompt(state):
    context = build_agent_prompt_context(state)
    current_date = context.trade_date
    ticker = context.ticker
    role_instruction = get_analyst_evidence_role_instruction("news/macro")
    earnings_context = build_earnings_workflow_context(
        trade_date=current_date,
        ticker=ticker,
        earnings_event=state.get("earnings_event"),
    )

    tools = NEWS_ANALYST_TOOLS

    web_search_instruction = """Web Search is an optional evidence supplement. You may use web_search_evidence at most 2 times in this analyst step. Prefer existing financial news tools first. Use Web Search only for fresh-news verification, missing coverage, Chinese/local sources, or source-backed risks/catalysts. If Web Search returns no results or warnings, continue with available tools and clearly note the limitation. Do not make web-search-backed claims unless supported by the returned evidence."""

    system_message = (
        "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(ticker, start_date, end_date) for company-specific news, get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news, and web_search_evidence(query, purpose, max_results) when you need a targeted search-style query or source-backed supplement. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
        + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
        + f"\n\n{web_search_instruction}"
        + f"\n\n{role_instruction}\n{context.decision_boundary_instruction}\n{context.evidence_rules_instruction}"
        + f"\n\n{earnings_context.prompt_instruction}"
        + """ Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:

```json-highlights
{
  "category": "news",
  "signal": "HOLD",
  "signal_confidence": "medium",
  "summary": "concise summary of the key news implications",
  "stance": "neutral",
  "market_impact": "neutral",
  "key_events": [
    {
      "event": "event name/description",
      "impact": "description of market impact"
    }
  ],
  "macro_outlook": "forward-looking macro outlook",
  "evidence_blocks": [
    {
      "claim": "news or macro claim",
      "evidence": "specific source-backed fact",
      "source": "get_news, get_global_news, or web_search_evidence result",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }
  ],
  "unknowns": ["material news or macro unknown"]
}
```

Keep the JSON keys and enum literals in English constants exactly as shown (`category` must be `news`; `signal` must be one of `BUY`, `OVERWEIGHT`, `HOLD`, `UNDERWEIGHT`, `SELL`; `signal_confidence` must be one of `high`, `medium`, `low`; `stance` must be one of `bullish`, `neutral`, `bearish`, `mixed`; `market_impact` must be one of `positive`, `negative`, `neutral`, `mixed`). Free-form string values should follow the report language. `signal_confidence` and `macro_outlook` are optional when uncertain."""
    )

    prompt = AdkPrompt(
        system_message=(
            f"Available tools: {', '.join([tool.name for tool in tools])}. "
            "Use them only for the news/macro evidence task described below.\n"
            f"{system_message}"
            f"\n{context.style_instruction}"
            f"\n{context.language_instruction}"
            f"\n{context.trade_feedback_message}"
            f"\n{structured_agent_output_instruction()}"
            f"\nFor your reference, the current date is {current_date}. {context.instrument_context}"
        ),
        messages=tuple(state["messages"]),
    )
    metadata = {
        "agent": "News Analyst",
        "ticker": ticker,
        "analysis_date": current_date,
        "language": context.output_language,
        "earnings_report_section": earnings_context.report_section,
    }
    return prompt, tools, metadata


def commit_news_analyst_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    structured = parse_structured_output(structured_payload, NewsReportStructuredOutput)
    payload = structured.model_dump(mode="json")
    earnings_context = build_earnings_workflow_context(
        trade_date=state["trade_date"],
        ticker=state["company_of_interest"],
        earnings_event=state.get("earnings_event"),
    )
    report_markdown = inject_earnings_section(
        structured.report_markdown,
        earnings_context.report_section,
    )
    return {
        "news_report": render_markdown_with_highlights(
            report_markdown,
            structured.highlights,
        ),
        "structured_agent_outputs": merge_structured_agent_output(
            state,
            agent_name="news_analyst",
            payload=payload,
        ),
    }


NEWS_ANALYST_AGENT = AnalystTurn(
    analyst_key="news",
    agent_name="news_analyst",
    display_name="News Analyst",
    output_schema=NewsReportStructuredOutput,
    output_key="news_report_structured",
    build_prompt=build_news_analyst_prompt,
    evidence_output_key="news_evidence_notes",
    report_key="news_report",
    structured_agent_name="news_analyst",
    tools=NEWS_ANALYST_TOOLS,
    commit_output=commit_news_analyst_output,
)
