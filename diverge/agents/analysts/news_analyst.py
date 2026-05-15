from contextlib import contextmanager

from diverge.agents.base import AgentCallSpec, DivergeAgentNode
from diverge.agents.utils.agent_utils import (
    build_instrument_context,
    get_analyst_evidence_role_instruction,
    get_evidence_rules_instruction,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)
from diverge.agents.utils.news_data_tools import get_global_news, get_news
from diverge.agents.utils.search_tools import web_search_evidence
from diverge.research.earnings import (
    build_earnings_workflow_context,
    inject_earnings_section,
)
from diverge.research.search.session import current_search_context
from diverge.runtime.messages import AdkPrompt


class NewsAnalyst(DivergeAgentNode):
    name = "news_analyst"

    def build_call(self, state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        evidence_rules_instruction = get_evidence_rules_instruction()
        role_instruction = get_analyst_evidence_role_instruction("news/macro")
        decision_boundary_instruction = get_upstream_decision_boundary_instruction()
        earnings_context = build_earnings_workflow_context(
            trade_date=current_date,
            ticker=ticker,
            earnings_event=state.get("earnings_event"),
        )

        tools = [
            get_news,
            get_global_news,
            web_search_evidence,
        ]

        web_search_instruction = """Web Search is an optional evidence supplement. You may use web_search_evidence at most 2 times in this analyst step. Prefer existing financial news tools first. Use Web Search only for fresh-news verification, missing coverage, Chinese/local sources, or source-backed risks/catalysts. If Web Search returns no results or warnings, continue with available tools and clearly note the limitation. Do not make web-search-backed claims unless supported by the returned evidence."""

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(ticker, start_date, end_date) for company-specific news, get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news, and web_search_evidence(query, purpose, max_results) when you need a targeted search-style query or source-backed supplement. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + f"\n\n{web_search_instruction}"
            + f"\n\n{role_instruction}\n{decision_boundary_instruction}\n{evidence_rules_instruction}"
            + f"\n\n{earnings_context.prompt_instruction}"
            + """ After the markdown table, append exactly one structured highlights block in this exact format:

```json-highlights
{
  "category": "news",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "medium",
  "summary": "concise summary of the key news implications",
  "stance": "bullish or neutral or bearish or mixed",
  "market_impact": "mixed",
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
      "confidence": "high or medium or low",
      "limitation": "missing/stale/ambiguous input, or null"
    }
  ],
  "unknowns": ["material news or macro unknown"]
}
```

Keep the `json-highlights` fence, JSON keys, and enum literals in English constants exactly as shown (`category` must be `news`; `signal` must be one of `BUY`, `OVERWEIGHT`, `HOLD`, `UNDERWEIGHT`, `SELL`; `signal_confidence` must be one of `high`, `medium`, `low`; `stance` must be one of `bullish`, `neutral`, `bearish`, `mixed`; `market_impact` must be one of `positive`, `negative`, `neutral`, `mixed`). Free-form string values should follow the report language. `signal_confidence` and `macro_outlook` are optional when uncertain."""
        )

        prompt = AdkPrompt(
            system_message=(
                "You are a helpful AI assistant, collaborating with other assistants."
                " Use the provided tools to progress towards answering the question."
                " If you are unable to fully answer, that's OK; another assistant with different tools"
                " will help where you left off. Execute what you can to make progress."
                f" You have access to the following tools: {', '.join([tool.name for tool in tools])}.\n{system_message}"
                f"\n{style_instruction}"
                f"\n{language_instruction}"
                f"\n{trade_feedback_message}"
                f"\nFor your reference, the current date is {current_date}. {instrument_context}"
            ),
            messages=tuple(state["messages"]),
        )
        return AgentCallSpec(
            prompt=prompt,
            tools=tuple(tools),
            metadata={
                "agent": "News Analyst",
                "ticker": ticker,
                "analysis_date": current_date,
                "language": output_language,
                "earnings_report_section": earnings_context.report_section,
            },
        )

    @contextmanager
    def call_context(self, state, spec):
        context_token = None
        parent_context = current_search_context.get()
        if parent_context is not None:
            context_token = current_search_context.set(
                parent_context.model_copy(
                    update={
                        key: value
                        for key, value in spec.metadata.items()
                        if key != "earnings_report_section"
                    }
                )
            )
        try:
            yield
        finally:
            if context_token is not None:
                current_search_context.reset(context_token)

    def apply_response(self, state, spec, response):
        report = ""

        if len(response.tool_calls) == 0:
            report = inject_earnings_section(
                response.content,
                spec.metadata["earnings_report_section"],
            )

        return {
            "messages": [response],
            "news_report": report,
        }
