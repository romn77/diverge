from __future__ import annotations

import copy
import os
import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from google.adk.apps import App
from google.adk.workflow import FunctionNode, Workflow

from diverge.analysis.options import ANALYST_ORDER
from diverge.default_config import DEFAULT_CONFIG
from diverge.runtime.adk_native.runner import (
    ADK_NATIVE_RUNTIME_NAME,
    build_native_analysis_workflow,
)
from diverge.runtime.analysis_schema import (
    HISTORICAL_TRADE_FEEDBACK_KEY,
    HISTORICAL_TRADE_REVIEWS_KEY,
)
from diverge.runtime.state import create_initial_state


ADK_WEB_APP_NAME = "diverge_analysis"
ADK_WEB_WORKFLOW_NAME = "diverge_adk_web_analysis"
ADK_WEB_ANALYSTS_ENV = "DIVERGE_ADK_WEB_ANALYSTS"

_SYMBOL_RE = re.compile(r"\$?([A-Z][A-Z0-9._-]{0,9})(?:\b|$)")
_SYMBOL_STOPWORDS = {
    "A",
    "ADK",
    "ANALYSE",
    "ANALYZE",
    "BUY",
    "CN",
    "FOR",
    "HOLD",
    "SELL",
    "THE",
    "US",
}
_PRESERVED_INITIAL_STATE_KEYS = {
    "earnings_event",
    "instrument_type",
    "valuation_applicability",
    "valuation_applicability_reason",
}


def build_adk_web_app(
    *,
    config: Mapping[str, Any] | None = None,
    selected_analysts: Sequence[str] | None = None,
    app_name: str = ADK_WEB_APP_NAME,
) -> App:
    """Build the standard ADK App exposed to `adk web`."""
    return App(
        name=app_name,
        root_agent=build_adk_web_agent(
            config=config,
            selected_analysts=selected_analysts,
        ),
    )


def build_adk_web_agent(
    *,
    config: Mapping[str, Any] | None = None,
    selected_analysts: Sequence[str] | None = None,
    workflow_name: str = ADK_WEB_WORKFLOW_NAME,
) -> Workflow:
    """Build the root ADK workflow for ADK Web debugging."""
    resolved_config = _resolve_config(config)
    resolved_analysts = _resolve_selected_analysts(selected_analysts)
    initializer = FunctionNode(
        func=_make_web_state_initializer(
            config=resolved_config,
            selected_analysts=resolved_analysts,
        ),
        name="initialize_diverge_state",
    )
    return build_native_analysis_workflow(
        selected_analysts=resolved_analysts,
        config=resolved_config,
        name=workflow_name,
        prefix_nodes=[initializer],
    )


def initialize_adk_web_state(
    ctx: Any,
    *,
    config: Mapping[str, Any],
    selected_analysts: Sequence[str],
) -> None:
    """Initialize Diverge analysis state from an ADK Web session."""
    current_state = _state_to_dict(ctx.state)
    if _has_diverge_analysis_state(current_state):
        ctx.state.update(
            {
                "adk_runtime": ADK_NATIVE_RUNTIME_NAME,
                "selected_analysts": list(selected_analysts),
            }
        )
        return None

    company_name = (
        _string_value(current_state.get("company_of_interest"))
        or _string_value(current_state.get("ticker"))
        or _string_value(current_state.get("symbol"))
        or _string_value(current_state.get("company"))
        or _string_value(current_state.get("company_name"))
        or _company_from_user_content(getattr(ctx, "user_content", None))
        or "SPY"
    )
    trade_date = (
        _string_value(current_state.get("trade_date")) or date.today().isoformat()
    )
    output_language = (
        _string_value(current_state.get("output_language"))
        or _string_value(config.get("output_language"))
        or "en"
    )
    historical_trade_feedback = _string_value(
        current_state.get(HISTORICAL_TRADE_FEEDBACK_KEY)
    )
    historical_trade_reviews = current_state.get(HISTORICAL_TRADE_REVIEWS_KEY)
    if not isinstance(historical_trade_reviews, list):
        historical_trade_reviews = []

    initial_state = create_initial_state(
        company_name,
        trade_date,
        output_language=output_language,
        historical_trade_feedback=historical_trade_feedback,
        historical_trade_reviews=historical_trade_reviews,
        portfolio_context=_string_value(current_state.get("portfolio_context")),
    )
    for key in _PRESERVED_INITIAL_STATE_KEYS:
        if key in current_state and current_state[key] is not None:
            initial_state[key] = current_state[key]
    for key, value in current_state.items():
        if ":" in key:
            initial_state[key] = value

    initial_state["adk_runtime"] = ADK_NATIVE_RUNTIME_NAME
    initial_state["selected_analysts"] = list(selected_analysts)
    ctx.state.update(initial_state)
    return None


def _make_web_state_initializer(
    *,
    config: Mapping[str, Any],
    selected_analysts: Sequence[str],
):
    def initialize_diverge_state(ctx: Any) -> None:
        return initialize_adk_web_state(
            ctx,
            config=config,
            selected_analysts=selected_analysts,
        )

    return initialize_diverge_state


def _resolve_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    resolved = copy.deepcopy(DEFAULT_CONFIG)
    if config:
        resolved.update(dict(config))
    return resolved


def _resolve_selected_analysts(
    selected_analysts: Sequence[str] | None,
) -> list[str]:
    if selected_analysts is not None:
        return _normalize_analysts(selected_analysts)

    env_value = os.getenv(ADK_WEB_ANALYSTS_ENV, "")
    if env_value.strip():
        return _normalize_analysts(env_value.split(","))
    return list(ANALYST_ORDER)


def _normalize_analysts(selected_analysts: Sequence[str]) -> list[str]:
    selected = {str(analyst).strip() for analyst in selected_analysts}
    return [analyst for analyst in ANALYST_ORDER if analyst in selected]


def _has_diverge_analysis_state(state: Mapping[str, Any]) -> bool:
    return bool(
        state.get("company_of_interest")
        and state.get("trade_date")
        and state.get("investment_debate_state")
        and state.get("risk_debate_state")
    )


def _state_to_dict(state: Any) -> dict[str, Any]:
    if hasattr(state, "to_dict"):
        return dict(state.to_dict())
    return dict(state)


def _company_from_user_content(user_content: Any) -> str:
    text = _content_text(user_content)
    if not text:
        return ""

    for match in _SYMBOL_RE.finditer(text):
        symbol = match.group(1).strip("._-")
        if symbol and symbol.upper() not in _SYMBOL_STOPWORDS:
            return symbol

    first_line = text.splitlines()[0].strip()
    return first_line[:80]


def _content_text(user_content: Any) -> str:
    if user_content is None:
        return ""
    if isinstance(user_content, str):
        return user_content.strip()

    texts: list[str] = []
    for part in getattr(user_content, "parts", None) or []:
        text = getattr(part, "text", None)
        if text:
            texts.append(str(text))
    return "".join(texts).strip()


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "ADK_WEB_APP_NAME",
    "ADK_WEB_WORKFLOW_NAME",
    "build_adk_web_agent",
    "build_adk_web_app",
    "initialize_adk_web_state",
]
