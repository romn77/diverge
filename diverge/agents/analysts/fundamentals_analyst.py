from diverge.agents.base import DivergeAgentNode
from diverge.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
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
from diverge.valuation.formatter import (
    format_valuation_sections,
    inject_valuation_sections,
)


class FundamentalsAnalyst(DivergeAgentNode):
    name = "fundamentals_analyst"

    def run(self, state):
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
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_insider_transactions,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements, and `get_insider_transactions` for recent insider activity."
            + f"\n\n{earnings_context.prompt_instruction}"
            + ' At the very end of your report, append exactly one fenced `json-highlights` block using this schema:\n```json-highlights\n{\n  "category": "fundamentals",\n  "signal": "BUY|OVERWEIGHT|HOLD|UNDERWEIGHT|SELL",\n  "signal_confidence": "high|medium|low",\n  "summary": "string",\n  "metrics": [\n    {\n      "name": "string",\n      "value": "string",\n      "assessment": "string"\n    }\n  ],\n  "financial_health": "string"\n}\n```'
            + " Keep fence/keys/enums as English constants; free-form values should follow the report language."
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
        result = self.llm.bind_tools(tools).invoke(prompt)

        report = ""
        instrument_type = state.get("instrument_type")
        valuation_applicability = state.get("valuation_applicability")
        valuation_applicability_reason = state.get("valuation_applicability_reason")

        if len(result.tool_calls) == 0:
            report = inject_earnings_section(
                result.content,
                earnings_context.report_section,
            )
            try:
                valuation_input = get_valuation_ready_fundamentals(
                    ticker,
                    curr_date=current_date,
                    freq="annual",
                )
                instrument_type = valuation_input.instrument_type
                valuation_applicability = valuation_input.valuation_applicability
                valuation_applicability_reason = (
                    valuation_input.valuation_applicability_reason
                )
                valuation_sections = format_valuation_sections(valuation_input)
                report = inject_valuation_sections(report, valuation_sections)
            except ValueError as exc:
                report = inject_valuation_sections(
                    report,
                    f"## Valuation Availability\n\nValuation sections unavailable: {exc}",
                )
            except Exception:
                report = inject_valuation_sections(
                    report,
                    "## Valuation Availability\n\nValuation sections unavailable due to unexpected preparation failure.",
                )

        return {
            "messages": [result],
            "fundamentals_report": report,
            "instrument_type": instrument_type,
            "valuation_applicability": valuation_applicability,
            "valuation_applicability_reason": valuation_applicability_reason,
        }


def create_fundamentals_analyst(llm):
    return FundamentalsAnalyst(llm)
