const USER_FACING_REPLACEMENTS: Array<[RegExp, string]> = [
  [/当前\s+(?:Current\s+)?Portfolio\s+Ledger\s+Context/gi, "当前持仓参考"],
  [/Current\s+Portfolio\s+Ledger\s+Context/gi, "Current portfolio reference"],
  [/Portfolio\s+Ledger\s+Context/gi, "portfolio reference"],
  [/json-highlights/gi, "structured highlights"],
  [/json-decision-card/gi, "structured decision card"],
  [/Portfolio\s+Manager\s+LLM/gi, "final decision service"],
  [/LLM\s+gateway/gi, "analysis service"],
  [/model\s+gateway/gi, "analysis service"],
];

const DEBATE_LABEL_RE =
  /\b(?:Bull|Bear|Neutral|Aggressive|Conservative)\s+Analyst:/g;

const REPORT_BODY_START_PATTERNS = [
  /好的，各位同事[。！]?/g,
  /\n##\s+/g,
  /\n###\s+/g,
  /\n\*\*我的裁决\*\*/g,
  /\n\*\*新闻分析报告[:：]?/g,
];

const PLANNING_PREFIX_MARKERS = [
  /用户要求/g,
  /系统指令/g,
  /我需要/g,
  /首先/g,
  /工具/g,
  /调用/g,
  /指令/g,
  /核心任务/g,
  /输出格式/g,
  /我将采用以下结构/g,
  /最后要有/g,
  /需要包括/g,
  /```python/g,
  /"tool"\s*:/g,
  /get_[a-z_]+\s*\(/gi,
];

function keepLatestDebateTurn(value: string): string {
  const matches = [...value.matchAll(DEBATE_LABEL_RE)];
  if (matches.length < 2) {
    return value;
  }

  const lastMatch = matches.at(-1);
  if (!lastMatch || typeof lastMatch.index !== "number" || lastMatch.index <= 0) {
    return value;
  }

  return value.slice(lastMatch.index).trimStart();
}

function findEarliestBodyStart(value: string): number {
  let earliest = -1;

  for (const pattern of REPORT_BODY_START_PATTERNS) {
    pattern.lastIndex = 0;
    const match = pattern.exec(value);
    if (!match || typeof match.index !== "number") {
      continue;
    }

    const adjustedIndex =
      pattern.source.startsWith("\\n") && match.index > 0
        ? match.index + 1
        : match.index;

    if (adjustedIndex < 80) {
      continue;
    }

    if (earliest === -1 || adjustedIndex < earliest) {
      earliest = adjustedIndex;
    }
  }

  return earliest;
}

function looksLikePlanningPreface(prefix: string): boolean {
  let markerHits = 0;
  for (const pattern of PLANNING_PREFIX_MARKERS) {
    pattern.lastIndex = 0;
    if (pattern.test(prefix)) {
      markerHits += 1;
    }
  }

  return markerHits >= 2;
}

function stripPlanningPreface(value: string): string {
  const bodyStart = findEarliestBodyStart(value);
  if (bodyStart <= 0) {
    return value;
  }

  const prefix = value.slice(0, bodyStart);
  if (!looksLikePlanningPreface(prefix)) {
    return value;
  }

  return value.slice(bodyStart).trimStart();
}

export function sanitizeUserFacingReportText(value: string): string {
  const normalized = stripPlanningPreface(keepLatestDebateTurn(value.trimStart()));
  return USER_FACING_REPLACEMENTS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    normalized
  );
}
