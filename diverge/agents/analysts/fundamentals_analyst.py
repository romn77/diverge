from typing import Any

from diverge.agents.analyst_turn import AnalystTurn
from diverge.agents.report_output import (
    FundamentalsReportStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.agent_context import build_agent_prompt_context
from diverge.agents.utils.agent_utils import (
    get_analyst_evidence_role_instruction,
)
from diverge.agents.utils.fundamental_data_tools import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_valuation_ready_fundamentals,
)
from diverge.agents.utils.news_data_tools import get_insider_transactions
from diverge.research.earnings import (
    build_earnings_workflow_context,
    inject_earnings_section,
)
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output
from diverge.valuation.formatter import (
    format_valuation_sections,
    inject_valuation_sections,
)


FUNDAMENTALS_ANALYST_TOOLS = (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
)


def build_fundamentals_analyst_prompt(state):
    context = build_agent_prompt_context(state)
    current_date = context.trade_date
    ticker = context.ticker
    role_instruction = get_analyst_evidence_role_instruction("fundamentals")
    earnings_context = build_earnings_workflow_context(
        trade_date=current_date,
        ticker=ticker,
        earnings_event=state.get("earnings_event"),
    )

    tools = FUNDAMENTALS_ANALYST_TOOLS

    system_message = (
        "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
        + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
        + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements, and `get_insider_transactions` for recent insider activity."
        + f"\n\n{role_instruction}\n{context.decision_boundary_instruction}\n{context.evidence_rules_instruction}"
        + f"\n\n{earnings_context.prompt_instruction}"
        + ' Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:\n```json-highlights\n{\n  "category": "fundamentals",\n  "signal": "HOLD",\n  "signal_confidence": "medium",\n  "summary": "1-2 sentence executive summary of fundamental analysis",\n  "stance": "neutral",\n  "metrics": [\n    {\n      "name": "metric name",\n      "value": "metric value",\n      "assessment": "brief assessment"\n    }\n  ],\n  "financial_health": "brief financial health assessment",\n  "evidence_blocks": [\n    {\n      "claim": "fundamental claim",\n      "evidence": "specific reported metric or fact",\n      "source": "tool/source name",\n      "data_date": "YYYY-MM-DD or unknown",\n      "confidence": "medium",\n      "limitation": "missing/stale/ambiguous input, or null"\n    }\n  ],\n  "unknowns": ["material fundamental unknown or unavailable input"]\n}\n```'
        + " Keep keys/enums as English constants; free-form values should follow the report language."
    )

    prompt = AdkPrompt(
        system_message=(
            f"Available tools: {', '.join([tool.name for tool in tools])}. "
            "Use them only for the fundamentals evidence task described below.\n"
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
        "ticker": ticker,
        "current_date": current_date,
        "earnings_report_section": earnings_context.report_section,
    }
    return prompt, tools, metadata


def commit_fundamentals_analyst_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    structured = parse_structured_output(
        structured_payload,
        FundamentalsReportStructuredOutput,
    )
    earnings_context = build_earnings_workflow_context(
        trade_date=state["trade_date"],
        ticker=state["company_of_interest"],
        earnings_event=state.get("earnings_event"),
    )
    report_markdown = inject_earnings_section(
        structured.report_markdown,
        earnings_context.report_section,
    )
    valuation_result = build_fundamentals_valuation_result(state)
    report_markdown = inject_valuation_sections(
        report_markdown,
        valuation_result.pop("valuation_sections"),
    )
    return {
        **valuation_result,
        "fundamentals_report": render_markdown_with_highlights(
            report_markdown,
            structured.highlights,
        ),
        "structured_agent_outputs": merge_structured_agent_output(
            state,
            agent_name="fundamentals_analyst",
            payload=structured.model_dump(mode="json"),
        ),
    }


def build_fundamentals_valuation_result(state: dict[str, Any]) -> dict[str, Any]:
    instrument_type = state.get("instrument_type")
    valuation_applicability = state.get("valuation_applicability")
    valuation_applicability_reason = state.get("valuation_applicability_reason")

    try:
        valuation_input = get_valuation_ready_fundamentals(
            state["company_of_interest"],
            curr_date=state["trade_date"],
            freq="annual",
        )
        instrument_type = valuation_input.instrument_type
        valuation_applicability = valuation_input.valuation_applicability
        valuation_applicability_reason = (
            valuation_input.valuation_applicability_reason
        )
        valuation_sections = format_valuation_sections(valuation_input)
    except ValueError as exc:
        valuation_sections = (
            f"## Valuation Availability\n\nValuation sections unavailable: {exc}"
        )
    except Exception:
        valuation_sections = (
            "## Valuation Availability\n\nValuation sections unavailable due to "
            "unexpected preparation failure."
        )

    return {
        "instrument_type": instrument_type,
        "valuation_applicability": valuation_applicability,
        "valuation_applicability_reason": valuation_applicability_reason,
        "valuation_sections": valuation_sections,
    }


FUNDAMENTALS_ANALYST_AGENT = AnalystTurn(
    analyst_key="fundamentals",
    agent_name="fundamentals_analyst",
    display_name="Fundamentals Analyst",
    output_schema=FundamentalsReportStructuredOutput,
    output_key="fundamentals_report_structured",
    build_prompt=build_fundamentals_analyst_prompt,
    evidence_output_key="fundamentals_evidence_notes",
    report_key="fundamentals_report",
    structured_agent_name="fundamentals_analyst",
    tools=FUNDAMENTALS_ANALYST_TOOLS,
    commit_output=commit_fundamentals_analyst_output,
)
