from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from diverge.research.thesis_tracker import build_thesis_artifact
from diverge.runtime.analysis_schema import trade_feedback_artifact_from_state


@dataclass(frozen=True, slots=True)
class StateReportArtifact:
    state_key: str
    stage_dir: str
    file_name: str
    display_name: str


@dataclass(frozen=True, slots=True)
class DebateReportArtifact:
    current_key: str
    fallback_key: str | None
    stage_dir: str
    file_name: str
    display_name: str

    def content_from(self, debate: dict[str, Any]) -> str:
        content = debate.get(self.current_key)
        if not content and self.fallback_key:
            content = debate.get(self.fallback_key)
        return str(content or "").strip()


ANALYST_REPORT_ARTIFACTS = (
    StateReportArtifact("market_report", "1_analysts", "market.md", "Market Analyst"),
    StateReportArtifact(
        "sentiment_report",
        "1_analysts",
        "sentiment.md",
        "Social Analyst",
    ),
    StateReportArtifact("news_report", "1_analysts", "news.md", "News Analyst"),
    StateReportArtifact(
        "fundamentals_report",
        "1_analysts",
        "fundamentals.md",
        "Fundamentals Analyst",
    ),
)
PARTIAL_REPORT_ARTIFACTS = (
    *ANALYST_REPORT_ARTIFACTS,
    StateReportArtifact(
        "investment_plan",
        "2_research",
        "manager.md",
        "Research Manager",
    ),
    StateReportArtifact(
        "trader_investment_plan",
        "3_trading",
        "trader.md",
        "Trader",
    ),
    StateReportArtifact(
        "final_trade_decision",
        "5_portfolio",
        "decision.md",
        "Portfolio Manager",
    ),
)
RESEARCH_REPORT_ARTIFACTS = (
    DebateReportArtifact(
        "current_bull_response",
        "bull_history",
        "2_research",
        "bull.md",
        "Bull Researcher",
    ),
    DebateReportArtifact(
        "current_bear_response",
        "bear_history",
        "2_research",
        "bear.md",
        "Bear Researcher",
    ),
    DebateReportArtifact(
        "judge_decision",
        None,
        "2_research",
        "manager.md",
        "Research Manager",
    ),
)
RISK_REPORT_ARTIFACTS = (
    DebateReportArtifact(
        "current_aggressive_response",
        "aggressive_history",
        "4_risk",
        "aggressive.md",
        "Aggressive Analyst",
    ),
    DebateReportArtifact(
        "current_conservative_response",
        "conservative_history",
        "4_risk",
        "conservative.md",
        "Conservative Analyst",
    ),
    DebateReportArtifact(
        "current_neutral_response",
        "neutral_history",
        "4_risk",
        "neutral.md",
        "Neutral Analyst",
    ),
)
PARTIAL_REPORT_SECTION_FILES = {
    artifact.state_key: (artifact.stage_dir, artifact.file_name)
    for artifact in PARTIAL_REPORT_ARTIFACTS
}


def write_partial_report_section(
    *,
    base_path: Path,
    section_name: str,
    content: str,
) -> Path:
    """Write one in-progress report section to its final report folder."""

    stage_dir_name, file_name = PARTIAL_REPORT_SECTION_FILES[section_name]
    stage_dir = base_path / stage_dir_name
    stage_dir.mkdir(parents=True, exist_ok=True)
    section_path = stage_dir / file_name
    section_path.write_text(content, encoding="utf-8")
    return section_path


def _write_stage_artifact(
    *,
    base_path: Path,
    stage_dir: str,
    file_name: str,
    content: str,
) -> None:
    directory = base_path / stage_dir
    directory.mkdir(exist_ok=True)
    (directory / file_name).write_text(content, encoding="utf-8")


def save_report_to_disk(final_state: dict[str, Any], ticker: str, save_path: Path):
    """Save complete analysis report to disk with organized subfolders."""

    save_path.mkdir(parents=True, exist_ok=True)
    sections = []

    analyst_parts = []
    for artifact in ANALYST_REPORT_ARTIFACTS:
        content = str(final_state.get(artifact.state_key) or "").strip()
        if not content:
            continue
        _write_stage_artifact(
            base_path=save_path,
            stage_dir=artifact.stage_dir,
            file_name=artifact.file_name,
            content=content,
        )
        analyst_parts.append((artifact.display_name, content))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    if final_state.get("investment_debate_state"):
        debate = final_state["investment_debate_state"]
        research_parts = []
        for artifact in RESEARCH_REPORT_ARTIFACTS:
            content = artifact.content_from(debate)
            if not content:
                continue
            _write_stage_artifact(
                base_path=save_path,
                stage_dir=artifact.stage_dir,
                file_name=artifact.file_name,
                content=content,
            )
            research_parts.append((artifact.display_name, content))
        if research_parts:
            content = "\n\n".join(
                f"### {name}\n{text}" for name, text in research_parts
            )
            sections.append(f"## II. Research Team Decision\n\n{content}")

    if final_state.get("trader_investment_plan"):
        _write_stage_artifact(
            base_path=save_path,
            stage_dir="3_trading",
            file_name="trader.md",
            content=final_state["trader_investment_plan"],
        )
        sections.append(
            f"## III. Trading Team Plan\n\n### Trader\n{final_state['trader_investment_plan']}"
        )

    if final_state.get("risk_debate_state"):
        risk = final_state["risk_debate_state"]
        risk_parts = []
        for artifact in RISK_REPORT_ARTIFACTS:
            content = artifact.content_from(risk)
            if not content:
                continue
            _write_stage_artifact(
                base_path=save_path,
                stage_dir=artifact.stage_dir,
                file_name=artifact.file_name,
                content=content,
            )
            risk_parts.append((artifact.display_name, content))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")

        if risk.get("judge_decision"):
            _write_stage_artifact(
                base_path=save_path,
                stage_dir="5_portfolio",
                file_name="decision.md",
                content=risk["judge_decision"],
            )
            sections.append(
                f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n{risk['judge_decision']}"
            )

    runtime_warnings = final_state.get("runtime_warnings")
    if isinstance(runtime_warnings, list) and runtime_warnings:
        warning_lines = []
        for warning in runtime_warnings:
            if not isinstance(warning, dict):
                continue
            stage = str(warning.get("stage") or "Runtime").strip()
            message = str(warning.get("message") or warning).strip()
            warning_lines.append(f"- **{stage}**: {message}")
        if warning_lines:
            sections.append("## Runtime Warnings\n\n" + "\n".join(warning_lines))

    header = (
        f"# Trading Analysis Report: {ticker}\n\n"
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    (save_path / "complete_report.md").write_text(
        header + "\n\n".join(sections), encoding="utf-8"
    )

    thesis_artifact = build_thesis_artifact(final_state, ticker=ticker)
    artifacts_dir = save_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "thesis.json").write_text(
        json.dumps(thesis_artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    trade_feedback_artifact = trade_feedback_artifact_from_state(
        final_state,
        ticker=ticker,
    )
    if trade_feedback_artifact is not None:
        (artifacts_dir / "trade_feedback.json").write_text(
            json.dumps(trade_feedback_artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if isinstance(runtime_warnings, list) and runtime_warnings:
        runtime_warning_artifact = {
            "type": "runtime_warnings",
            "ticker": ticker,
            "warnings": runtime_warnings,
        }
        (artifacts_dir / "runtime_warnings.json").write_text(
            json.dumps(runtime_warning_artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return save_path / "complete_report.md"
