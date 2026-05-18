from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from web.backend import app_config
from web.backend.routers import market_briefs as market_briefs_router
from web.backend.services import market_briefs as market_brief_service


SAMPLE_MARKDOWN = """# 美股盘前市场简报｜2026-05-18

信息截至：2026-05-18 08:34 ET / 北京时间 20:34。今日对应美股交易日：2026-05-18。

## 一、100字以内核心结论

今日偏 risk-off 震荡：油价和收益率压估值，AI/半导体高位分歧。

## 七、今日风险提示

| 风险 | 可能影响 |
|---|---|
| 美债收益率再上台阶 | 压制AI、半导体、小盘。 |

## 八、开盘后前30分钟需要验证的5个信号

| 信号 | 为什么重要 |
|---|---|
| SPY/QQQ 是否守住跳空低点 | 判断盘前risk-off是可买回落。 |

来源：[NYSE](https://www.nyse.com/markets/hours-calendars)。
"""


def _set_market_brief_dir(tmp_path: Path):
    return patch.object(app_config, "MARKET_BRIEFS_DIR", tmp_path / "market_briefs")


def test_market_briefs_list_reads_external_markdown_directory(tmp_path):
    with _set_market_brief_dir(tmp_path):
        brief_dir = app_config.MARKET_BRIEFS_DIR
        brief_dir.mkdir(parents=True)
        (brief_dir / "2026-05-18-us-premarket-market-brief.md.md").write_text(
            SAMPLE_MARKDOWN,
            encoding="utf-8",
        )
        (brief_dir / "2026-05-08-us-premarket-market-brief.md").write_text(
            "# Old brief\n\n信息截至：2026-05-08 08:34 ET\n",
            encoding="utf-8",
        )

        payload = market_brief_service.list_market_briefs(today=date(2026, 5, 18))

    assert payload["retention_days"] == 7
    assert payload["cutoff_date"] == "2026-05-12"
    assert len(payload["briefs"]) == 1
    latest = payload["latest"]
    assert latest["report_id"] == "MARKET_BRIEF_2026_05_18_US_PREMARKET_MARKET_BRIEF"
    assert latest["date"] == "2026-05-18"
    assert latest["time"] == "08:34"
    assert latest["markets"] == ["us"]
    assert latest["source_count"] == 1
    assert "risk-off" in latest["summary"]
    assert "七、今日风险提示" in latest["main_themes"]
    assert "美债收益率再上台阶" in latest["risks"]
    assert "SPY/QQQ 是否守住跳空低点" in latest["opening_validation_signals"]


def test_external_market_brief_report_bridge_returns_markdown_content(tmp_path):
    with _set_market_brief_dir(tmp_path):
        brief_dir = app_config.MARKET_BRIEFS_DIR
        brief_dir.mkdir(parents=True)
        (brief_dir / "2026-05-18-us-premarket-market-brief.md").write_text(
            SAMPLE_MARKDOWN,
            encoding="utf-8",
        )

        report_id = "MARKET_BRIEF_2026_05_18_US_PREMARKET_MARKET_BRIEF"
        structure = market_brief_service.get_external_report_structure(report_id)
        content = market_brief_service.get_external_report_content(
            report_id,
            "complete_report.md",
        )
        artifact = market_brief_service.get_external_report_content(
            report_id,
            "artifacts/premarket_brief.json",
        )

    assert structure["ticker"] == "MARKET_BRIEF"
    assert structure["has_complete"] is True
    assert content["content"] == SAMPLE_MARKDOWN
    assert json.loads(artifact["content"])["report_id"] == report_id


def test_multica_webhook_validates_signature_and_writes_markdown(tmp_path, monkeypatch):
    secret = "test-secret"
    body = json.dumps(
        {
            "filename": "2026-05-18-us-premarket-market-brief.md",
            "provider_report_id": "multica-20260518-us-am",
            "markets": ["us"],
            "markdown": SAMPLE_MARKDOWN,
        }
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()

    async def _receive():
        return {"type": "http.request", "body": body, "more_body": False}

    headers = [
        (b"content-type", b"application/json"),
        (b"x-multica-timestamp", timestamp.encode("utf-8")),
        (b"x-multica-signature", f"sha256={signature}".encode("utf-8")),
    ]
    request = Request({"type": "http", "method": "POST", "headers": headers}, _receive)

    monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", secret)
    with _set_market_brief_dir(tmp_path):
        target = app_config.MARKET_BRIEFS_DIR / "2026-05-18-us-premarket-market-brief.md"
        response = asyncio.run(
            market_briefs_router.ingest_multica_market_brief(request)
        )
        assert target.is_file()

    assert response["created"] is True
    assert response["report_id"] == "MARKET_BRIEF_2026_05_18_US_PREMARKET_MARKET_BRIEF"


def test_multica_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("MULTICA_WEBHOOK_SECRET", "test-secret")
    timestamp = str(int(time.time()))
    try:
        market_brief_service.verify_multica_webhook_signature(
            {
                "x-multica-timestamp": timestamp,
                "x-multica-signature": "sha256=bad",
            },
            b"body",
        )
    except HTTPException as exc:
        assert exc.status_code == 401
    else:  # pragma: no cover
        raise AssertionError("bad webhook signature was accepted")
