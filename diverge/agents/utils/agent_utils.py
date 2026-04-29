from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from diverge.agents.utils.core_stock_tools import get_stock_data
from diverge.agents.utils.technical_indicators_tools import get_indicators
from diverge.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from diverge.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news,
)


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )


def get_trade_feedback_message(state) -> str:
    feedback = state.get("historical_trade_feedback")
    return str(feedback).strip() if feedback else ""


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]
        trade_feedback_message = get_trade_feedback_message(state)

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        replacement_messages = []
        if trade_feedback_message:
            replacement_messages.append(HumanMessage(content=trade_feedback_message))

        # Add a minimal placeholder message
        replacement_messages.append(HumanMessage(content="Continue"))

        return {"messages": removal_operations + replacement_messages}

    return delete_messages


def get_language_instruction(language_code: str | None) -> str:
    if (language_code or "en").lower() == "cn":
        return "Write your full response in Simplified Chinese (zh-CN)."
    return "Write your full response in English (en)."


def get_research_note_style_instruction(language_code: str | None) -> str:
    return (
        "Adopt an institutional financial research note style. "
        "Use an objective, restrained, evidence-first tone. "
        "Avoid colloquial debate, emotional language, and tutorial-style explanations. "
        "When disagreeing with another view, critique the reasoning professionally and analytically. "
        "Write in well-formed paragraphs with natural transitions instead of many short lines."
    )
