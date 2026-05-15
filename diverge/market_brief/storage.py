from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from diverge.common.json_io import write_json_atomic
from diverge.market_brief.renderer import render_market_brief_markdown
from diverge.market_brief.schema import PremarketBrief


@dataclass(frozen=True)
class MarketBriefStorageResult:
    report_id: str
    report_dir: Path
    artifact_path: Path
    markdown_path: Path


def _safe_report_id(brief_id: str) -> str:
    candidate = "".join(
        character if character.isalnum() or character in {"_", "-"} else "_"
        for character in brief_id.strip().upper()
    )
    return candidate or "MARKET_BRIEF"


def save_market_brief_report(
    brief: PremarketBrief,
    *,
    reports_dir: Path,
    tmp_reports_dir: Path,
) -> MarketBriefStorageResult:
    report_id = _safe_report_id(brief.brief_id)
    reports_root = reports_dir.resolve()
    report_dir = (reports_dir / report_id).resolve()
    tmp_dir = (tmp_reports_dir / report_id).resolve()
    try:
        report_dir.relative_to(reports_root)
        tmp_dir.relative_to(tmp_reports_dir.resolve())
    except ValueError as exc:
        raise ValueError(
            "Market brief report path must stay inside reports root"
        ) from exc

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = tmp_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = artifacts_dir / "premarket_brief.json"
    markdown_path = tmp_dir / "complete_report.md"
    write_json_atomic(
        artifact_path,
        brief.model_dump(mode="json"),
    )
    markdown_path.write_text(render_market_brief_markdown(brief), encoding="utf-8")

    reports_dir.mkdir(parents=True, exist_ok=True)
    if report_dir.exists():
        shutil.rmtree(report_dir)
    tmp_dir.replace(report_dir)

    return MarketBriefStorageResult(
        report_id=report_id,
        report_dir=report_dir,
        artifact_path=report_dir / "artifacts" / "premarket_brief.json",
        markdown_path=report_dir / "complete_report.md",
    )
