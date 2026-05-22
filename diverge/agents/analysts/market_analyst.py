from diverge.agents.report_output import (
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
from diverge.agents.utils.core_stock_tools import get_stock_data
from diverge.agents.utils.technical_indicators_tools import get_indicators
from diverge.runtime.messages import AdkPrompt


def build_market_analyst_prompt(state):
    current_date = state["trade_date"]
    ticker = state["company_of_interest"]
    instrument_context = build_instrument_context(ticker)
    output_language = state.get("output_language", "en")
    language_instruction = get_language_instruction(output_language)
    style_instruction = get_research_note_style_instruction(output_language)
    trade_feedback_message = get_trade_feedback_message(state)
    evidence_rules_instruction = get_evidence_rules_instruction()
    role_instruction = get_analyst_evidence_role_instruction("market/technical")
    decision_boundary_instruction = get_upstream_decision_boundary_instruction()

    tools = (
        get_stock_data,
        get_indicators,
    )

    system_message = (
        """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

Moving Averages:
- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

MACD Related:
- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

Momentum Indicators:
- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

Volatility Indicators:
- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

Volume-Based Indicators:
- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

- Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. When calling get_stock_data, request only the past 120 trading days ending at the current date; do not request a longer price-history window. Then use get_indicators with the specific indicator names. Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
        + f"\n\n{role_instruction}\n{decision_boundary_instruction}\n{evidence_rules_instruction}"
        + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read. Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:

```json-highlights
{
  "category": "market",
  "signal": "HOLD",
  "signal_confidence": "medium",
  "summary": "1-2 sentence executive summary of your analysis",
  "stance": "neutral",
  "trend_direction": "neutral",
  "key_levels": {
    "support": ["level1", "level2"],
    "resistance": ["level1", "level2"]
  },
  "indicators": [
    {"name": "indicator name", "value": "current value", "interpretation": "brief meaning"}
  ],
  "volatility": "moderate",
  "evidence_blocks": [
    {
      "claim": "technical claim",
      "evidence": "specific OHLC/indicator evidence",
      "source": "get_stock_data or get_indicators",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }
  ],
  "unknowns": ["material technical unknown or unavailable input"]
}
```

Keep the JSON keys and enum literals in English constants exactly as shown; free-form string values should follow the report language."""
    )

    prompt = AdkPrompt(
        system_message=(
            f"Available tools: {', '.join([tool.name for tool in tools])}. "
            "Use them only for the market/technical evidence task described below.\n"
            f"{system_message}"
            f"\n{style_instruction}"
            f"\n{language_instruction}"
            f"\n{trade_feedback_message}"
            f"\n{structured_agent_output_instruction()}"
            f"\nFor your reference, the current date is {current_date}. {instrument_context}"
        ),
        messages=tuple(state["messages"]),
    )
    return prompt, tools, {}
