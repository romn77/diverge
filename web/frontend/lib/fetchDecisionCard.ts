import { getContent } from "./api";
import type { DecisionCard } from "./decisionCard";

export async function fetchDecisionCard(
  reportId: string,
  path: string
): Promise<DecisionCard> {
  const content = await getContent(reportId, path);
  return JSON.parse(content) as DecisionCard;
}
