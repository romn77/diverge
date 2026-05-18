import re
from typing import Any

from pydantic import BaseModel, Field

from diverge.agents.base import AgentCallSpec, DivergeAgentNode
from diverge.agents.utils.agent_utils import (
    format_prompt_section,
    get_language_instruction,
)
from diverge.decision_card.schema import PortfolioAction, PortfolioRating
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


_THINKING_BLOCK_RE = re.compile(
    r"(?is)<(?:think|thinking|analysis|reasoning)>.*?</(?:think|thinking|analysis|reasoning)>"
)
_SUMMARY_LABEL_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:final|final answer|final summary|executive summary|summary|最终|最终答案|最终摘要|最终输出|执行摘要|报告摘要|摘要)\s*[:：]\s*"
)
_SUMMARY_START_RE = re.compile(
    r"(?is)"
    r"(基于对[^。！？\n]{0,180}(?:最终投资决策|最终决策|投资决策|评级)"
    r"|综合[^。！？\n]{0,180}(?:最终投资决策|最终决策|投资决策|评级|建议)"
    r"|(?:最终投资决策|最终决策|投资组合经理的?最终决策|最终评级|最终建议)\s*(?:为|是|:|：)"
    r"|(?:overall|in summary|the final|final)\b[^.\n]{0,140}\b(?:decision|recommendation|rating)\b)"
)
_META_SENTENCE_MARKERS = (
    "用户要求",
    "用户希望",
    "用户需要",
    "作为summary agent",
    "作为 summary agent",
    "我需要",
    "我应该",
    "我不能",
    "我会",
    "我看到",
    "我将",
    "需要写",
    "目标长度",
    "目标语言",
    "提供的完整报告",
    "完整报告上下文",
    "根据用户",
    "摘要应该",
    "the user asks",
    "the user requested",
    "as the summary agent",
    "i need",
    "i should",
    "i will",
    "i can see",
    "the prompt asks",
    "target length",
)
_DECISION_MARKERS = (
    "最终投资决策",
    "最终决策",
    "投资决策",
    "投资组合经理",
    "评级",
    "减持",
    "增持",
    "买入",
    "卖出",
    "持有",
    "buy",
    "sell",
    "hold",
    "underweight",
    "overweight",
    "recommendation",
    "rating",
    "decision",
)


def _coerce_summary_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                continue
            if isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part.strip())
    return str(content)


def _strip_inline_markdown(text: str) -> str:
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"```[a-zA-Z0-9_-]*\s*|\s*```", "", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    return text


def _split_sentences(text: str) -> list[str]:
    sentences = re.findall(r"[^。！？.!?\n]+[。！？.!?]?", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _drop_leading_meta_sentences(text: str) -> str:
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return text.strip()

    drop_count = 0
    for sentence in sentences:
        normalized = sentence.lower()
        has_meta_marker = any(marker in normalized for marker in _META_SENTENCE_MARKERS)
        has_decision_marker = any(marker in normalized for marker in _DECISION_MARKERS)
        if not has_meta_marker or has_decision_marker:
            break
        drop_count += 1

    if drop_count == 0:
        return text.strip()
    return "".join(sentences[drop_count:]).strip() or text.strip()


def sanitize_report_summary_output(content: Any) -> str:
    """Remove model self-talk and formatting from a user-facing report summary."""
    text = _coerce_summary_text(content).strip()
    if not text:
        return ""

    text = _THINKING_BLOCK_RE.sub("", text).strip()

    label_matches = list(_SUMMARY_LABEL_RE.finditer(text))
    if label_matches:
        text = text[label_matches[-1].end() :].strip()

    start_matches = list(_SUMMARY_START_RE.finditer(text))
    if start_matches:
        text = text[start_matches[-1].start() :].strip()
    else:
        text = _drop_leading_meta_sentences(text)

    text = _strip_inline_markdown(text)
    return " ".join(text.split()).strip()


class ReportSummaryOutput(BaseModel):
    summary_text: str = Field(
        description="One compact user-facing executive summary paragraph."
    )
    language: str = Field(description="Output language code, such as en or cn.")
    final_rating: PortfolioRating | None = Field(
        default=None,
        description="Final portfolio rating if available.",
    )
    primary_action: PortfolioAction | None = Field(
        default=None,
        description="Primary portfolio action if available.",
    )


class SummaryAgent(DivergeAgentNode):
    name = "summary_agent"

    def build_call(self, state) -> AgentCallSpec:
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        debate = state.get("investment_debate_state") or {}
        risk = state.get("risk_debate_state") or {}

        full_report_context = "\n\n".join(
            [
                format_prompt_section("Market Analyst", state.get("market_report")),
                format_prompt_section("Social Analyst", state.get("sentiment_report")),
                format_prompt_section("News Analyst", state.get("news_report")),
                format_prompt_section(
                    "Fundamentals Analyst",
                    state.get("fundamentals_report"),
                ),
                format_prompt_section("Bull Researcher", debate.get("bull_history")),
                format_prompt_section("Bear Researcher", debate.get("bear_history")),
                format_prompt_section(
                    "Research Manager",
                    debate.get("judge_decision"),
                ),
                format_prompt_section("Trader", state.get("trader_investment_plan")),
                format_prompt_section(
                    "Aggressive Risk Analyst",
                    risk.get("aggressive_history"),
                ),
                format_prompt_section(
                    "Conservative Risk Analyst",
                    risk.get("conservative_history"),
                ),
                format_prompt_section(
                    "Neutral Risk Analyst",
                    risk.get("neutral_history"),
                ),
                format_prompt_section(
                    "Portfolio Manager",
                    risk.get("judge_decision"),
                ),
            ]
        )

        prompt = f"""You are the Summary Agent for a multi-agent trading research report.

Create a concise executive summary of the complete report for {state["company_of_interest"]} on {state["trade_date"]}.

Requirements:
- Target length: about 300 Chinese characters when the output language is Chinese, or about 150 English words when the output language is English.
- Write one compact paragraph, not bullet points.
- Cover the final decision, the main thesis, the most important supporting evidence, the primary risks, and the practical trading action.
- Do not include markdown headings, code fences, JSON, citations, role labels, chain-of-thought, private reasoning, or meta commentary about the task.
- Start directly with the final decision or recommendation; do not begin with phrases like "The user asked", "I need to", "Based on the prompt", or "好的".
- Do not invent facts that are not present in the report context.
- Return only the structured response requested by the runtime schema.

Complete report context:

{full_report_context}

{language_instruction}"""

        return AgentCallSpec(
            prompt=AdkPrompt(system_message=prompt),
            output_schema=ReportSummaryOutput,
            output_key="report_summary_structured",
        )

    def apply_response(self, state, spec, response) -> dict:
        try:
            structured = parse_structured_output(response.content, ReportSummaryOutput)
        except Exception:
            return {"report_summary": sanitize_report_summary_output(response.content)}

        summary_text = sanitize_report_summary_output(structured.summary_text)
        payload = structured.model_dump(mode="json")
        payload["summary_text"] = summary_text
        return {
            "report_summary": summary_text,
            "report_summary_structured": payload,
        }
