from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from web.backend import app_config


MARKET_BRIEF_COMPLETE_PATH = "complete_report.md"
MARKET_BRIEF_ARTIFACT_PATH = "artifacts/premarket_brief.json"
MARKET_BRIEF_REPORT_ID_PREFIX = "MARKET_BRIEF_"
MARKET_BRIEF_REPORT_TICKER = "MARKET_BRIEF"
MARKET_BRIEF_RETENTION_DAYS = 7
MARKET_BRIEF_TIMEZONE = ZoneInfo("Asia/Shanghai")
MARKET_BRIEF_MAX_FILE_BYTES = 2 * 1024 * 1024
_MARKDOWN_SUFFIXES = (".md", ".markdown")


@dataclass(frozen=True)
class ExternalMarketBrief:
    path: Path
    markdown: str
    summary: dict[str, Any]


def _market_briefs_dir() -> Path:
    configured = os.environ.get("MARKET_BRIEFS_DIR", "").strip()
    if configured:
        return Path(configured).resolve()
    return app_config.MARKET_BRIEFS_DIR.resolve()


def _today_in_market_timezone() -> date:
    return datetime.now(MARKET_BRIEF_TIMEZONE).date()


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            source = candidate[:10] if pattern == "%Y-%m-%d" else candidate[:8]
            return datetime.strptime(source, pattern).date()
        except ValueError:
            continue
    match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", candidate)
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _normalize_markdown_stem(path_or_name: Path | str) -> str:
    name = Path(path_or_name).name
    lowered = name.lower()
    while lowered.endswith(_MARKDOWN_SUFFIXES):
        suffix = ".markdown" if lowered.endswith(".markdown") else ".md"
        name = name[: -len(suffix)]
        lowered = name.lower()
    return name


def _report_id_from_path(path: Path) -> str:
    stem = _normalize_markdown_stem(path)
    safe = re.sub(r"[^A-Za-z0-9]+", "_", stem.upper()).strip("_")
    return f"{MARKET_BRIEF_REPORT_ID_PREFIX}{safe or 'EXTERNAL'}"


def _safe_markdown_filename(filename: str | None, *, fallback_id: str | None = None) -> str:
    candidate = Path(str(filename or fallback_id or "market-brief.md")).name
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip(".-")
    if not candidate:
        candidate = "market-brief.md"
    lowered = candidate.lower()
    while lowered.endswith(".md.md"):
        candidate = candidate[:-3]
        lowered = candidate.lower()
    if not lowered.endswith(_MARKDOWN_SUFFIXES):
        candidate = f"{candidate}.md"
    return candidate


def _markdown_files(root: Path | None = None) -> list[Path]:
    brief_root = (root or _market_briefs_dir()).resolve()
    if not brief_root.is_dir():
        return []
    files: list[Path] = []
    for path in brief_root.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in _MARKDOWN_SUFFIXES:
            continue
        files.append(path.resolve())
    return sorted(files)


def _metadata_candidates(path: Path) -> tuple[Path, Path]:
    return (
        path.with_suffix(".meta.json"),
        path.with_name(f"{path.name}.meta.json"),
    )


def _load_sidecar_metadata(path: Path) -> dict[str, Any]:
    for candidate in _metadata_candidates(path):
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _parse_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    if not markdown.startswith("---"):
        return {}, markdown
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, markdown

    payload: dict[str, Any] = {}
    for raw_line in lines[1:end_index]:
        if ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip().strip("\"'")
        if not key:
            continue
        if value.startswith("[") and value.endswith("]"):
            payload[key] = [
                item.strip().strip("\"'")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        else:
            payload[key] = value
    return payload, "\n".join(lines[end_index + 1 :]).lstrip()


def _first_heading(markdown: str) -> str | None:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_information_cutoff(markdown: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"信息截至[:：]\s*(20\d{2}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?::\d{2})?",
        markdown,
    )
    if match:
        return match.group(1), match.group(2)
    match = re.search(
        r"(?:Generated|Information cutoff|信息截至)[:：]\s*"
        r"(20\d{2}-\d{2}-\d{2})[T\s]+(\d{1,2}:\d{2})(?::\d{2})?",
        markdown,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1), match.group(2)
    return None, None


def _clean_markdown_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().strip("|")).strip()


def _extract_section(markdown: str, keyword: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+[^\n]*{re.escape(keyword)}[^\n]*\n(?P<body>.*?)(?=^##\s+|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group("body").strip() if match else None


def _extract_summary(markdown: str) -> str | None:
    for keyword in ("核心结论", "Executive Summary", "Summary"):
        section = _extract_section(markdown, keyword)
        if not section:
            continue
        for line in section.splitlines():
            text = _clean_markdown_line(line)
            if text and not text.startswith(("#", "|", "---")):
                return text

    for line in markdown.splitlines():
        text = _clean_markdown_line(line)
        if not text or text.startswith(("#", "|", "---")):
            continue
        if text.startswith(("信息截至", "主要来源")):
            continue
        return text[:280]
    return None


def _coerce_markets(value: Any, filename: str, markdown: str) -> list[str]:
    raw_values: list[str] = []
    if isinstance(value, str):
        raw_values.extend(part.strip() for part in re.split(r"[,，\s]+", value))
    elif isinstance(value, list):
        raw_values.extend(str(item).strip() for item in value)

    haystack = f"{filename} {markdown[:500]}".lower()
    if "us" in haystack or "美股" in haystack:
        raw_values.append("us")
    if "cn" in haystack or "a股" in haystack or "ashare" in haystack:
        raw_values.append("cn")

    markets: list[str] = []
    for value in raw_values:
        normalized = value.lower()
        if normalized in {"us", "usa", "nyse", "nasdaq", "美股"}:
            normalized = "us"
        elif normalized in {"cn", "china", "a", "ashare", "a-share", "a股"}:
            normalized = "cn"
        if normalized in {"cn", "us"} and normalized not in markets:
            markets.append(normalized)
    return markets or ["us"]


def _extract_markdown_links(markdown: str) -> list[str]:
    urls = set(re.findall(r"\[[^\]]+\]\((https?://[^)\s]+)", markdown))
    urls.update(re.findall(r"(?<!\()https?://[^\s)>\]]+", markdown))
    return sorted(url.rstrip(".,;") for url in urls)


def _extract_h2_titles(markdown: str, *, limit: int = 5) -> list[str]:
    titles: list[str] = []
    for match in re.finditer(r"^##\s+(.+?)\s*$", markdown, flags=re.MULTILINE):
        title = match.group(1).strip()
        if not title or "核心结论" in title or "数据缺口" in title:
            continue
        titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def _extract_table_first_column(section: str | None, *, limit: int = 5) -> list[str]:
    if not section:
        return []
    values: list[str] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        columns = [_clean_markdown_line(column) for column in line.split("|")]
        columns = [column for column in columns if column]
        if not columns or set(columns[0]) <= {"-", ":"}:
            continue
        if columns[0] in {"风险", "信号", "方向"}:
            continue
        values.append(columns[0])
        if len(values) >= limit:
            break
    return values


def _build_summary(path: Path, markdown: str) -> dict[str, Any]:
    sidecar = _load_sidecar_metadata(path)
    frontmatter, body = _parse_frontmatter(markdown)
    metadata = {**frontmatter, **sidecar}
    cutoff_date, cutoff_time = _extract_information_cutoff(body)
    parsed_date = (
        _parse_date(metadata.get("trading_day"))
        or _parse_date(metadata.get("generated_at"))
        or _parse_date(cutoff_date)
        or _parse_date(path.name)
    )
    date_value = parsed_date.isoformat() if parsed_date else None
    time_value = (
        str(metadata.get("time") or "").strip()
        or cutoff_time
        or None
    )
    title = (
        str(metadata.get("title") or "").strip()
        or _first_heading(body)
        or "Premarket Brief"
    )
    summary = str(metadata.get("summary") or "").strip() or _extract_summary(body)
    source_urls = _extract_markdown_links(body)
    report_id = _report_id_from_path(path)
    generated_at = str(metadata.get("generated_at") or "").strip() or None
    if generated_at is None and date_value and time_value:
        generated_at = f"{date_value}T{time_value}:00"
    markets = _coerce_markets(metadata.get("markets"), path.name, body)
    risks = _extract_table_first_column(_extract_section(body, "风险"))
    signals = _extract_table_first_column(_extract_section(body, "开盘后"))

    return {
        "type": "premarket_brief",
        "report_id": report_id,
        "brief_id": str(metadata.get("provider_report_id") or report_id),
        "date": date_value,
        "time": time_value,
        "title": title,
        "summary": summary,
        "markets": markets,
        "trading_day": date_value,
        "generated_at": generated_at,
        "information_cutoff_at": generated_at,
        "data_quality_level": "external",
        "main_themes": _extract_h2_titles(body),
        "risks": risks,
        "opening_validation_signals": signals,
        "quality_warnings": [],
        "source_count": len(source_urls),
        "artifact_path": MARKET_BRIEF_COMPLETE_PATH,
        "provider": str(metadata.get("provider") or "multica"),
        "source_path": path.name,
    }


def _load_markdown(path: Path) -> str:
    if path.stat().st_size > MARKET_BRIEF_MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Market brief markdown is too large")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=404, detail="Market brief not found") from exc


def load_external_market_brief(report_id: str) -> ExternalMarketBrief | None:
    normalized = str(report_id or "").strip().upper()
    if not normalized.startswith(MARKET_BRIEF_REPORT_ID_PREFIX):
        return None
    for path in _markdown_files():
        if _report_id_from_path(path) != normalized:
            continue
        markdown = _load_markdown(path)
        return ExternalMarketBrief(
            path=path,
            markdown=markdown,
            summary=_build_summary(path, markdown),
        )
    return None


def get_external_report_structure(report_id: str) -> dict[str, Any] | None:
    brief = load_external_market_brief(report_id)
    if brief is None:
        return None
    summary = brief.summary
    return {
        "id": summary["report_id"],
        "ticker": MARKET_BRIEF_REPORT_TICKER,
        "date": summary["date"],
        "time": summary["time"],
        "has_complete": True,
        "categories": {},
        "artifacts": [
            {
                "type": "premarket_brief",
                "path": MARKET_BRIEF_ARTIFACT_PATH,
                "summary": summary.get("summary"),
            }
        ],
    }


def get_external_report_content(report_id: str, path: str) -> dict[str, str] | None:
    brief = load_external_market_brief(report_id)
    if brief is None:
        return None
    if path == MARKET_BRIEF_COMPLETE_PATH:
        return {"path": path, "content": brief.markdown}
    if path == MARKET_BRIEF_ARTIFACT_PATH:
        return {
            "path": path,
            "content": json.dumps(brief.summary, ensure_ascii=False, indent=2),
        }
    return None


def list_market_briefs(
    request: object | None = None,
    *,
    today: date | None = None,
    retention_days: int = MARKET_BRIEF_RETENTION_DAYS,
) -> dict[str, Any]:
    del request
    current_day = today or _today_in_market_timezone()
    cutoff_day = current_day - timedelta(days=max(retention_days, 1) - 1)
    summaries: list[dict[str, Any]] = []

    for path in _markdown_files():
        markdown = _load_markdown(path)
        summary = _build_summary(path, markdown)
        summary_day = _parse_date(summary.get("date"))
        if summary_day is None or summary_day < cutoff_day:
            continue
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("time") or "",
            item.get("report_id") or "",
        ),
        reverse=True,
    )
    return {
        "retention_days": retention_days,
        "today": current_day.isoformat(),
        "cutoff_date": cutoff_day.isoformat(),
        "latest": summaries[0] if summaries else None,
        "briefs": summaries,
    }


def verify_multica_webhook_signature(headers: Mapping[str, str], body: bytes) -> None:
    secret = os.environ.get("MULTICA_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="MULTICA_WEBHOOK_SECRET is not configured",
        )
    timestamp = headers.get("x-multica-timestamp") or headers.get(
        "X-Multica-Timestamp"
    )
    signature = headers.get("x-multica-signature") or headers.get(
        "X-Multica-Signature"
    )
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid webhook timestamp") from exc
    max_skew = int(os.environ.get("MULTICA_WEBHOOK_MAX_SKEW_SECONDS", "300"))
    now_value = int(datetime.now(MARKET_BRIEF_TIMEZONE).timestamp())
    if abs(now_value - timestamp_value) > max_skew:
        raise HTTPException(status_code=401, detail="Webhook timestamp expired")

    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _write_text_atomic(target: Path, content: str) -> None:
    root = target.parent.resolve()
    root.mkdir(parents=True, exist_ok=True)
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    tmp_path = inbox / f".{target.name}.{uuid.uuid4().hex}.tmp"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(target)


def ingest_external_market_brief(
    *,
    markdown: str,
    filename: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not markdown.strip():
        raise HTTPException(status_code=400, detail="Market brief markdown is required")
    if len(markdown.encode("utf-8")) > MARKET_BRIEF_MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Market brief markdown is too large")

    metadata_payload = dict(metadata or {})
    safe_filename = _safe_markdown_filename(
        filename,
        fallback_id=str(metadata_payload.get("provider_report_id") or ""),
    )
    root = _market_briefs_dir()
    target = (root / safe_filename).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid market brief filename") from exc

    existed = target.is_file()
    _write_text_atomic(target, markdown)
    if metadata_payload:
        sidecar = target.with_suffix(".meta.json")
        _write_text_atomic(
            sidecar,
            json.dumps(metadata_payload, ensure_ascii=False, indent=2),
        )

    loaded = load_external_market_brief(_report_id_from_path(target))
    if loaded is None:  # pragma: no cover - defensive path sanity
        raise HTTPException(status_code=500, detail="Market brief was not indexed")
    return {
        "created": not existed,
        "report_id": loaded.summary["report_id"],
        "filename": target.name,
        "brief": loaded.summary,
    }
