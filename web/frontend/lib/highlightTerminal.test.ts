import test from "node:test";
import assert from "node:assert/strict";

import type {
  MarketHighlights,
  PortfolioDecisionHighlights,
} from "./highlights.ts";
import { buildHighlightDeck } from "./highlightTerminal.ts";

test("buildHighlightDeck creates a command-oriented portfolio terminal deck", () => {
  const highlights: PortfolioDecisionHighlights = {
    category: "portfolio_decision",
    signal: "SELL",
    signal_confidence: "medium",
    summary: "Reduce exposure first and only re-enter after the trend repairs.",
    final_decision: "SELL",
    decision_basis:
      "Trend remains weak and failed rebounds are not worth chasing before structure improves.",
    strategic_actions: [
      {
        action: "Cut gross exposure to 25% immediately and park the rest in cash.",
        priority: "immediate",
      },
      {
        action: "Reassess if price can reclaim 678-680 with momentum confirmation.",
        priority: "conditional",
      },
    ],
    risk_warnings: [
      "ATR expansion means small mistakes will widen quickly.",
      "A failed reclaim near the 200SMA can trap late dip buyers.",
    ],
  };

  const deck = buildHighlightDeck(highlights);

  assert.equal(deck.categoryLabel, "Portfolio Decision");
  assert.equal(deck.heroTitle, "Allocation Command");
  assert.deepEqual(
    deck.heroChips.map((chip) => [chip.label, chip.value]),
    [
      ["Decision", "SELL"],
      ["Queued Actions", "2"],
      ["Risk Flags", "2"],
    ]
  );
  assert.deepEqual(
    deck.consoles.map((console) => [console.key, console.title]),
    [
      ["decision-console", "Decision Console"],
      ["execution-console", "Execution Console"],
    ]
  );
  assert.deepEqual(
    deck.consoles[0]?.panels.map((panel) => [panel.key, panel.variant]),
    [
      ["decision-basis", "story"],
      ["risk-watch", "bullet"],
    ]
  );
  assert.deepEqual(
    deck.consoles[1]?.panels.map((panel) => [panel.key, panel.variant]),
    [
      ["execution-queue", "queue"],
    ]
  );
  assert.equal(deck.consoles[1]?.panels[0]?.entries?.[0]?.meta, "immediate");
  assert.ok(!("heroEyebrow" in deck));
  assert.ok(deck.consoles.every((consolePanel) => !("eyebrow" in consolePanel)));
  assert.ok(
    deck.consoles.flatMap((consolePanel) => consolePanel.panels).every((panel) => !("eyebrow" in panel))
  );
});

test("buildHighlightDeck creates a market deck with levels and indicator grid", () => {
  const highlights: MarketHighlights = {
    category: "market",
    signal: "HOLD",
    signal_confidence: "high",
    summary: "The trend is still constructive, but volatility argues for patience.",
    trend_direction: "bullish",
    volatility: "Elevated",
    key_levels: {
      support: ["652", "645"],
      resistance: ["668", "680"],
    },
    indicators: [
      {
        name: "50D vs 200D",
        value: "668.9 vs 652.4",
        interpretation: "Bullish long-term structure remains intact.",
      },
      {
        name: "ATR",
        value: "9.4",
        interpretation: "Range expansion still demands smaller sizing.",
      },
    ],
  };

  const deck = buildHighlightDeck(highlights);

  assert.equal(deck.categoryLabel, "Market Outlook");
  assert.deepEqual(
    deck.heroChips.map((chip) => [chip.label, chip.value]),
    [
      ["Trend", "bullish"],
      ["Volatility", "Elevated"],
      ["Indicators", "2"],
    ]
  );
  assert.deepEqual(
    deck.consoles.map((console) => [console.key, console.title]),
    [
      ["market-console", "Market Console"],
      ["indicator-console", "Indicator Console"],
    ]
  );
  assert.deepEqual(
    deck.consoles[0]?.panels.map((panel) => [panel.key, panel.variant]),
    [
      ["market-regime", "story"],
      ["key-levels", "columns"],
    ]
  );
  assert.deepEqual(
    deck.consoles[1]?.panels.map((panel) => [panel.key, panel.variant]),
    [["indicator-grid", "table"]]
  );
  assert.deepEqual(
    deck.consoles[0]?.panels[1]?.columns?.map((column) => column.title),
    ["Support", "Resistance"]
  );
  assert.equal(deck.consoles[1]?.panels[0]?.table?.rows[0]?.label, "50D vs 200D");
  assert.ok(!("heroEyebrow" in deck));
  assert.ok(deck.consoles.every((consolePanel) => !("eyebrow" in consolePanel)));
  assert.ok(
    deck.consoles.flatMap((consolePanel) => consolePanel.panels).every((panel) => !("eyebrow" in panel))
  );
});

test("buildHighlightDeck accepts the UI translator for static chrome copy", () => {
  const highlights: PortfolioDecisionHighlights = {
    category: "portfolio_decision",
    signal: "BUY",
    signal_confidence: "high",
    summary: "Portfolio can add on confirmed strength.",
    final_decision: "BUY",
    decision_basis: "Risk/reward has improved.",
    strategic_actions: [{ action: "Add one tranche.", priority: "now" }],
    risk_warnings: ["Failed breakout invalidates the setup."],
  };
  const dictionary: Record<string, string> = {
    "highlights.portfolio.category": "组合决策",
    "highlights.portfolio.hero": "配置指令",
    "highlights.chip.decision": "决策",
    "highlights.chip.queuedActions": "待执行动作",
    "highlights.chip.riskFlags": "风险标记",
  };
  const deck = buildHighlightDeck(highlights, (key, fallback, params) => {
    const translated = dictionary[key];
    if (translated) {
      return translated;
    }
    return typeof fallback === "function" ? fallback(params ?? {}) : fallback;
  });

  assert.equal(deck.categoryLabel, "组合决策");
  assert.equal(deck.heroTitle, "配置指令");
  assert.deepEqual(
    deck.heroChips.map((chip) => chip.label),
    ["决策", "待执行动作", "风险标记"]
  );
});
