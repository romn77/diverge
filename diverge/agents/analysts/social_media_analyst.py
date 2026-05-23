from typing import Any

from diverge.agents.analyst_turn import AnalystTurn
from diverge.agents.report_output import (
    SentimentReportStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.agent_context import build_agent_prompt_context
from diverge.agents.utils.agent_utils import (
    get_analyst_evidence_role_instruction,
)
from diverge.agents.utils.news_data_tools import get_news
from diverge.agents.utils.search_tools import web_search_evidence
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


SOCIAL_MEDIA_ANALYST_TOOLS = (
    get_news,
    web_search_evidence,
)


def build_social_media_analyst_prompt(state):
    context = build_agent_prompt_context(state)
    current_date = context.trade_date
    ticker = context.ticker
    role_instruction = get_analyst_evidence_role_instruction(
        "public sentiment/company news"
    )

    tools = SOCIAL_MEDIA_ANALYST_TOOLS

    web_search_instruction = """Web Search is an optional evidence supplement. You may use web_search_evidence at most 2 times in this analyst step. Prefer existing financial news tools first. Use Web Search only for fresh-news verification, missing coverage, Chinese/local sources, or source-backed risks/catalysts. If Web Search returns no results or warnings, continue with available tools and clearly note the limitation. Do not make web-search-backed claims unless supported by the returned evidence."""

    system_message = (
        "You are a public sentiment and company-specific news researcher/analyst tasked with analyzing recent company news and verifiable public sentiment for a specific company over the past week. Use the get_news(ticker, start_date, end_date) tool for company-specific news; use web_search_evidence(query, purpose, max_results) only when you need a search-style query or source-backed supplement. Do not claim broad social-media sentiment unless the tool output contains actual social-media, forum, or community evidence. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
        + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
        + f"\n\n{web_search_instruction}"
        + f"\n\n{role_instruction}\n{context.decision_boundary_instruction}\n{context.evidence_rules_instruction}"
        + """ Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis. Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in Chinese; free-form string values should follow the report language.

```json-highlights
{
  "category": "sentiment",
  "signal": "HOLD",
  "signal_confidence": "medium",
  "summary": "1-2 sentence executive summary of sentiment analysis",
  "stance": "neutral",
  "overall_sentiment": "neutral",
  "sentiment_score": "score like 65/100 if determinable",
  "key_topics": ["topic1", "topic2", "topic3"],
  "social_buzz": "moderate",
  "evidence_blocks": [
    {
      "claim": "sentiment or public narrative claim",
      "evidence": "specific source-backed fact",
      "source": "get_news or web_search_evidence result",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }
  ],
  "unknowns": ["material sentiment unknown or unavailable social input"]
}
```"""
    )

    prompt = AdkPrompt(
        system_message=(
            f"Available tools: {', '.join([tool.name for tool in tools])}. "
            "Use them only for the sentiment/company-news evidence task described below.\n"
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
        "agent": "Social Analyst",
        "ticker": ticker,
        "analysis_date": current_date,
        "language": context.output_language,
    }
    return prompt, tools, metadata


def commit_social_media_analyst_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    structured = parse_structured_output(
        structured_payload,
        SentimentReportStructuredOutput,
    )
    return {
        "sentiment_report": render_markdown_with_highlights(
            structured.report_markdown,
            structured.highlights,
        ),
        "structured_agent_outputs": merge_structured_agent_output(
            state,
            agent_name="social_media_analyst",
            payload=structured.model_dump(mode="json"),
        ),
    }


SOCIAL_MEDIA_ANALYST_AGENT = AnalystTurn(
    analyst_key="social",
    agent_name="social_media_analyst",
    display_name="Social Analyst",
    output_schema=SentimentReportStructuredOutput,
    output_key="sentiment_report_structured",
    build_prompt=build_social_media_analyst_prompt,
    evidence_output_key="sentiment_evidence_notes",
    report_key="sentiment_report",
    structured_agent_name="social_media_analyst",
    tools=SOCIAL_MEDIA_ANALYST_TOOLS,
    commit_output=commit_social_media_analyst_output,
)
