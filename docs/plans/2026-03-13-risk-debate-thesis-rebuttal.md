# Risk Debate Thesis/Rebuttal Plan

Date: 2026-03-13

## Problem

The risk-management debate currently starts in rebuttal mode even though the
first speaker does not have complete counterpart arguments yet. This creates a
prompt conflict:

- the speaker is told to rebut the other two analysts point by point
- one or two counterpart responses are still empty in the opening cycle
- the prompt also says not to hallucinate missing arguments

That contradiction leaks into the generated report as meta commentary instead of
actual analysis.

## Decisions

1. Keep the existing speaker order unchanged:
   `Aggressive -> Conservative -> Neutral`
2. Redefine `max_risk_discuss_rounds` as the number of rebuttal rounds
3. Add one implicit opening thesis round before rebuttal begins
4. Leave bull/bear debate unchanged for now because only the first bull turn has
   an empty opponent response, while the risk debate has a stronger three-party
   mismatch
5. Fix config propagation so `TradingAgentsGraph` passes configured round limits
   into `ConditionalLogic`

## Intended Behavior

- Turns `0, 1, 2` are `thesis` mode:
  - each risk analyst presents their own stance
  - no prompt asks them to rebut missing counterpart text
- Turn `3` onward is `rebuttal` mode:
  - each risk analyst responds directly to the latest counterpart arguments
- Total risk turns become:
  - `3 * (1 + max_risk_discuss_rounds)`

Examples:

- `max_risk_discuss_rounds = 0` -> 3 turns total -> thesis only
- `max_risk_discuss_rounds = 1` -> 6 turns total -> 1 thesis round + 1 rebuttal round
- `max_risk_discuss_rounds = 2` -> 9 turns total -> 1 thesis round + 2 rebuttal rounds

## Implementation Scope

- `tradingagents/graph/conditional_logic.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- `tradingagents/agents/risk_mgmt/conservative_debator.py`
- `tradingagents/agents/risk_mgmt/neutral_debator.py`
- tests covering phase semantics, prompt mode switching, and config propagation

## Verification Plan

- unit tests for risk debate phase semantics
- unit tests for risk prompt mode switching
- unit test proving `TradingAgentsGraph` passes configured round limits to
  `ConditionalLogic`
- `py_compile` on modified Python modules
