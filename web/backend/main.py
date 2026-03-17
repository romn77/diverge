"""
TradingAgents Report Viewer — FastAPI read-only backend.

3 endpoints:
  GET /api/reports                               — list all reports
  GET /api/reports/{report_id}/structure         — list actual files present
  GET /api/reports/{report_id}/content?path=...  — return markdown content
"""

import os
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Use env var REPORTS_DIR if set; otherwise default to project-root/reports
# (this file lives at web/backend/main.py → project root is ../../)
_DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", _DEFAULT_REPORTS_DIR)).resolve()

# Category directory names as they appear on disk (with numeric prefix)
CATEGORY_DIR_MAP: dict[str, str] = {
    "analysts": "1_analysts",
    "research": "2_research",
    "trading": "3_trading",
    "risk": "4_risk",
    "portfolio": "5_portfolio",
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="TradingAgents Report Viewer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_complete_report_header(
    report_dir: Path,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Read the first few lines of complete_report.md to extract ticker, date, time.

    Expected format (from cli/main.py:725):
        # Trading Analysis Report: {TICKER}

        Generated: YYYY-MM-DD HH:MM:SS

    Returns (ticker, date_str, time_str) or (None, None, None) on failure.
    """
    complete = report_dir / "complete_report.md"
    if not complete.is_file():
        return None, None, None

    try:
        with complete.open(encoding="utf-8") as fh:
            lines = [fh.readline() for _ in range(4)]  # read up to 4 lines

        ticker: Optional[str] = None
        date_str: Optional[str] = None
        time_str: Optional[str] = None

        # Line 0: "# Trading Analysis Report: SPY"
        m = re.match(r"^#\s+Trading Analysis Report:\s+(\S+)", lines[0])
        if m:
            ticker = m.group(1).strip()

        # Lines 1-3: blank, then "Generated: YYYY-MM-DD HH:MM:SS"
        for line in lines[1:]:
            m = re.match(
                r"^Generated:\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})", line
            )
            if m:
                date_str = m.group(1)
                time_str = m.group(2)
                break

        return ticker, date_str, time_str

    except (OSError, UnicodeDecodeError):
        return None, None, None


def _scan_categories(report_dir: Path) -> dict[str, list[str]]:
    """
    Return a dict of category_key → [file_stems] for .md files actually present.
    Only includes categories whose directory exists and contains at least one .md.
    """
    categories: dict[str, list[str]] = {}
    for key, dir_name in CATEGORY_DIR_MAP.items():
        cat_dir = report_dir / dir_name
        if cat_dir.is_dir():
            stems = sorted(
                p.stem for p in cat_dir.iterdir() if p.suffix == ".md" and p.is_file()
            )
            if stems:
                categories[key] = stems
    return categories


def _resolve_report_dir(report_id: str) -> Path:
    """
    Resolve a report directory path and raise 404 if it doesn't exist.
    Basic sanity-check: report_id must not contain path separators.
    """
    # Prevent path separators in the id itself
    if "/" in report_id or "\\" in report_id or ".." in report_id:
        raise HTTPException(status_code=404, detail="Report not found")

    report_dir = REPORTS_DIR / report_id
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report_dir


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/reports")
def list_reports() -> list[dict]:
    """
    Return a list of all reports sorted by date descending.

    Response shape:
        [{"id": "SPY_20260305_155836", "ticker": "SPY", "date": "2026-03-05", "time": "15:58:40"}, ...]
    """
    if not REPORTS_DIR.is_dir():
        return []

    results = []
    for entry in REPORTS_DIR.iterdir():
        if not entry.is_dir():
            continue

        report_id = entry.name
        ticker, date_str, time_str = _parse_complete_report_header(entry)

        # Fallback: use directory name as ticker, leave date/time None
        if ticker is None:
            ticker = report_id

        results.append(
            {
                "id": report_id,
                "ticker": ticker,
                "date": date_str,
                "time": time_str,
            }
        )

    # Sort by date desc (None dates go last)
    results.sort(key=lambda r: (r["date"] or "", r["time"] or ""), reverse=True)
    return results


@app.get("/api/reports/{report_id}/structure")
def get_structure(report_id: str) -> dict:
    """
    Return the actual files present in a report directory.

    Response shape:
        {
          "id": "SPY_20260305_155836",
          "ticker": "SPY",
          "has_complete": true,
          "categories": {
            "analysts": ["market", "sentiment", "news", "fundamentals"],
            ...
          }
        }
    """
    report_dir = _resolve_report_dir(report_id)

    ticker, _date, _time = _parse_complete_report_header(report_dir)
    if ticker is None:
        ticker = report_id

    has_complete = (report_dir / "complete_report.md").is_file()
    categories = _scan_categories(report_dir)

    return {
        "id": report_id,
        "ticker": ticker,
        "has_complete": has_complete,
        "categories": categories,
    }


@app.get("/api/reports/{report_id}/content")
def get_content(report_id: str, path: str) -> dict:
    """
    Return the markdown content of a file within a report directory.

    Query param `path` is a relative path within the report (e.g.,
    ``complete_report.md`` or ``1_analysts/market.md``).

    Path traversal is blocked: resolved target must remain inside report_dir.

    Response shape:
        {"content": "markdown string..."}
    """
    report_dir = _resolve_report_dir(report_id)

    # --- PATH SAFETY ---
    # Resolve both the report dir and the target to absolute paths, then verify
    # the target is strictly inside the report dir.
    report_dir_resolved = report_dir.resolve()
    target = (report_dir_resolved / path).resolve()

    try:
        target.relative_to(report_dir_resolved)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{path}' not found")

    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read file: {exc}"
        ) from exc

    return {"content": content}
