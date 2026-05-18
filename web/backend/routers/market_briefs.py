from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from web.backend import auth
from web.backend.services import market_briefs as market_brief_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])
integration_router = APIRouter()


@router.get("/api/market-briefs")
def list_market_briefs(request: Request = None) -> dict:
    return market_brief_service.list_market_briefs(request)


def _webhook_payload_from_body(
    *,
    body: bytes,
    content_type: str,
    headers: dict[str, str],
) -> tuple[str, str | None, dict[str, Any]]:
    if "application/json" in content_type:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Webhook JSON must be an object")
        markdown = payload.get("markdown") or payload.get("content")
        if not isinstance(markdown, str):
            raise HTTPException(
                status_code=400,
                detail="Webhook JSON must include markdown content",
            )
        filename = payload.get("filename")
        metadata = {key: value for key, value in payload.items() if key != "markdown"}
        return markdown, str(filename) if filename else None, metadata

    try:
        markdown = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be UTF-8") from exc
    filename = (
        headers.get("x-multica-filename")
        or headers.get("content-disposition", "").split("filename=")[-1].strip('"')
        or None
    )
    metadata = {
        "provider": "multica",
        "provider_report_id": headers.get("x-multica-report-id"),
        "markets": headers.get("x-multica-markets"),
        "language": headers.get("x-multica-language"),
    }
    return markdown, filename, {key: value for key, value in metadata.items() if value}


@integration_router.post("/api/integrations/multica/market-brief")
async def ingest_multica_market_brief(request: Request) -> dict:
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    market_brief_service.verify_multica_webhook_signature(headers, body)
    markdown, filename, metadata = _webhook_payload_from_body(
        body=body,
        content_type=headers.get("content-type", ""),
        headers=headers,
    )
    return market_brief_service.ingest_external_market_brief(
        markdown=markdown,
        filename=filename,
        metadata=metadata,
    )
