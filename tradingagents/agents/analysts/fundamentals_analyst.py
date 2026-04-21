from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
<<<<<<< HEAD

=======
>>>>>>> agent/implement-dev/9e0b812f
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_valuation_ready_fundamentals,
)
from tradingagents.research.earnings import (
    build_earnings_workflow_context,
    inject_earnings_section,
)
from tradingagents.valuation.formatter import (
    format_valuation_sections,
    inject_valuation_sections,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
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
            + ' At the very end of your report, append exactly one fenced `json-highlights` block using this schema:\n```json-highlights\n{\n  "category": "fundamentals",\n  "signal": "BUY|HOLD|SELL",\n  "signal_confidence": "high|medium|low",\n  "summary": "string",\n  "metrics": [\n    {\n      "name": "string",\n      "value": "string",\n      "assessment": "string"\n    }\n  ],\n  "financial_health": "string"\n}\n```'
            + " Keep fence/keys/enums as English constants; free-form values should follow the report language."
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

    return fundamentals_analyst_node
