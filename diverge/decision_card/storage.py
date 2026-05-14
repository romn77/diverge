from __future__ import annotations

from pathlib import Path

from diverge.decision_card.schema import DecisionCard


def save_decision_card(card: DecisionCard, report_dir: Path) -> Path:
    artifacts_dir = report_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    path = artifacts_dir / "decision_card.json"
    path.write_text(
        card.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path
