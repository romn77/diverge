from diverge.agents.report_output import (
    SentimentReportStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.utils.agent_utils import (
    build_instrument_context,
    get_analyst_evidence_role_instruction,
    get_evidence_rules_instruction,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)
from diverge.agents.utils.news_data_tools import get_news
from diverge.agents.utils.search_tools import web_search_evidence
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


def build_social_media_analyst_prompt(state):
    current_date = state["trade_date"]
    ticker = state["company_of_interest"]
    instrument_context = build_instrument_context(ticker)
    output_language = state.get("output_language", "en")
    language_instruction = get_language_instruction(output_language)
    style_instruction = get_research_note_style_instruction(output_language)
    trade_feedback_message = get_trade_feedback_message(state)
    evidence_rules_instruction = get_evidence_rules_instruction()
    role_instruction = get_analyst_evidence_role_instruction(
        "public sentiment/company news"
    )
    decision_boundary_instruction = get_upstream_decision_boundary_instruction()

    tools = (
        get_news,
        web_search_evidence,
    )

    web_search_instruction = """Web Search is an optional evidence supplement. You may use web_search_evidence at most 2 times in this analyst step. Prefer existing financial news tools first. Use Web Search only for fresh-news verification, missing coverage, Chinese/local sources, or source-backed risks/catalysts. If Web Search returns no results or warnings, continue with available tools and clearly note the limitation. Do not make web-search-backed claims unless supported by the returned evidence."""

    system_message = (
        "You are a public sentiment and company-specific news researcher/analyst tasked with analyzing recent company news and verifiable public sentiment for a specific company over the past week. Use the get_news(ticker, start_date, end_date) tool for company-specific news; use web_search_evidence(query, purpose, max_results) only when you need a search-style query or source-backed supplement. Do not claim broad social-media sentiment unless the tool output contains actual social-media, forum, or community evidence. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
        + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
        + f"\n\n{web_search_instruction}"
        + f"\n\n{role_instruction}\n{decision_boundary_instruction}\n{evidence_rules_instruction}"
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
            f"\n{style_instruction}"
            f"\n{language_instruction}"
            f"\n{trade_feedback_message}"
            f"\n{structured_agent_output_instruction()}"
            f"\nFor your reference, the current date is {current_date}. {instrument_context}"
        ),
        messages=tuple(state["messages"]),
    )
    metadata = {
        "agent": "Social Analyst",
        "ticker": ticker,
        "analysis_date": current_date,
        "language": output_language,
    }
    return prompt, tools, metadata


def build_social_media_analyst_result(
    state,
    *,
    response_content,
    tool_calls=None,
    **_unused,
):
    report = ""

    if len(tool_calls or []) == 0:
        try:
            structured = parse_structured_output(
                response_content,
                SentimentReportStructuredOutput,
            )
        except Exception:
            report = response_content
        else:
            report = render_markdown_with_highlights(
                structured.report_markdown,
                structured.highlights,
            )
            return {
                "sentiment_report": report,
                "structured_agent_outputs": merge_structured_agent_output(
                    state,
                    agent_name="social_media_analyst",
                    payload=structured.model_dump(mode="json"),
                ),
            }

    return {"sentiment_report": report}
