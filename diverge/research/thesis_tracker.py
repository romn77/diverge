from __future__ import annotations

import re
from datetime import datetime
from typing import Mapping


def build_thesis_artifact(final_state: Mapping[str, object], *, ticker: str) -> dict:
    investment_plan = _as_text(final_state.get("investment_plan"))
    fundamentals_report = _as_text(final_state.get("fundamentals_report"))
    news_report = _as_text(final_state.get("news_report"))

    debate = final_state.get("investment_debate_state") or {}
    risk = final_state.get("risk_debate_state") or {}

    bull_history = _as_text(_from_mapping(debate, "bull_history"))
    bear_history = _as_text(_from_mapping(debate, "bear_history"))
    judge_decision = _as_text(_from_mapping(debate, "judge_decision"))
    conservative_history = _as_text(_from_mapping(risk, "conservative_history"))

    thesis_summary = (
        _first_sentence(investment_plan)
        or _first_sentence(judge_decision)
        or _first_sentence(fundamentals_report)
        or f"Maintain active thesis tracking for {ticker}."
    )

    supporting_evidence = _dedupe(
        _extract_bullets(fundamentals_report)
        + _extract_bullets(news_report)
        + _extract_key_sentences(bull_history)
    )[:5]
    if not supporting_evidence:
        supporting_evidence = ["Supporting evidence was not explicitly extracted from the report set."]

    invalidation_signals = _dedupe(
        _extract_key_sentences(bear_history)
        + _extract_key_sentences(conservative_history)
    )[:5]
    if not invalidation_signals:
        invalidation_signals = ["Watch for thesis drift, weaker guidance, or deteriorating balance-sheet quality."]

    next_catalysts = _dedupe(
        _extract_bullets(news_report)
        + _extract_section_lines(news_report, "Earnings")
        + _extract_key_sentences(judge_decision)
    )[:5]
    if not next_catalysts:
        next_catalysts = ["Track the next earnings print, management guidance, and market reaction."]

    return {
        "type": "thesis",
        "ticker": ticker,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "thesis_summary": thesis_summary,
        "supporting_evidence": supporting_evidence,
        "invalidation_signals": invalidation_signals,
        "next_catalysts": next_catalysts,
    }


def _from_mapping(value: object, key: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(key)
    return None


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_sentence(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    match = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    return match[0][:280].strip()


def _extract_bullets(text: str) -> list[str]:
    bullets = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
    return [bullet for bullet in bullets if bullet]


def _extract_key_sentences(text: str) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return [sentence.strip() for sentence in sentences if sentence.strip()][:3]


def _extract_section_lines(text: str, needle: str) -> list[str]:
    results = []
    capture = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            capture = needle.lower() in line.lower()
            continue
        if capture and line:
            results.append(line.lstrip("- ").strip())
    return results[:3]


def _clean_text(text: str) -> str:
    text = re.sub(r"```[\w-]*\n[\s\S]*?\n```", " ", text)
    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("```") or line.startswith("|"):
            continue
        cleaned_lines.append(line)
    return " ".join(cleaned_lines).strip()


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
