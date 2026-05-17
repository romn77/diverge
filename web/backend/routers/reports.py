from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from web.backend import auth
from web.backend.services import reports as report_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


class ReportVisibilityUpdatePayload(BaseModel):
    visibility: Literal["private", "workspace"]


@router.get("/api/reports")
def list_reports(request: Request = None) -> list[dict]:
    return report_service.list_reports(request)


@router.get("/api/reports/{report_id}/structure")
def get_structure(report_id: str, request: Request = None) -> dict:
    return report_service.get_structure(report_id, request)


@router.get("/api/reports/{report_id}/content")
def get_content(report_id: str, path: str, request: Request = None) -> dict:
    return report_service.get_content(report_id, path, request)


@router.patch("/api/reports/{report_id}/visibility")
def update_visibility(
    report_id: str,
    payload: ReportVisibilityUpdatePayload,
    request: Request = None,
) -> dict:
    return report_service.update_report_visibility(
        report_id, payload.visibility, request
    )


@router.delete("/api/reports/{report_id}")
def delete_report(report_id: str, request: Request = None) -> dict:
    return report_service.delete_report_artifacts(report_id, request)
