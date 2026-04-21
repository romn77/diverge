from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from web.backend import auth
from web.backend.services import reports as report_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


@router.get("/api/reports")
def list_reports(request: Request = None) -> list[dict]:
    return report_service.list_reports(request)


@router.get("/api/reports/{report_id}/structure")
def get_structure(report_id: str, request: Request = None) -> dict:
    return report_service.get_structure(report_id, request)


@router.get("/api/reports/{report_id}/content")
def get_content(report_id: str, path: str, request: Request = None) -> dict:
    return report_service.get_content(report_id, path, request)
