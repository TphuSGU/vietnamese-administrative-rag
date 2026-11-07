"""Locality reference endpoints (Phase 9).

Public, read-only, file-backed:
- GET /api/v1/localities/an-phu/profile  — hồ sơ + 18 lịch làm việc
- GET /api/v1/procedures                 — TTHC theo địa phương + tìm `q`
- GET /api/v1/legal-documents            — văn bản trong manifest địa phương

No auth required (citizen-facing reference data), and no URL is ever
returned (plan §8.3: UI không render link ra ngoài).
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.locality import (
    LegalDocumentListResponse,
    ProcedureListResponse,
    ProfileResponse,
)
from app.services import locality_data

router = APIRouter(prefix="/api/v1", tags=["localities"])


@router.get(
    "/localities/an-phu/profile",
    response_model=ProfileResponse,
    summary="Hồ sơ Phường An Phú (liên hệ, giờ làm việc, lịch làm việc)",
)
async def get_an_phu_profile() -> ProfileResponse:
    try:
        profile = locality_data.get_profile("an-phu")
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy hồ sơ địa phương"
        ) from exc
    return ProfileResponse.model_validate(profile)


@router.get(
    "/procedures",
    response_model=ProcedureListResponse,
    summary="Danh sách thủ tục hành chính theo địa phương",
)
async def list_procedures(
    locality_code: str = Query("25975", max_length=20),
    q: Optional[str] = Query(None, max_length=200, description="Tìm theo tên/mô tả/cơ quan"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ProcedureListResponse:
    items, total = locality_data.list_procedures(
        locality_code, q=q, limit=limit, offset=offset
    )
    return ProcedureListResponse(
        items=items,
        total=total,
        locality_code=locality_code,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/legal-documents",
    response_model=LegalDocumentListResponse,
    summary="Danh sách văn bản của địa phương",
)
async def list_legal_documents(
    locality_code: str = Query("25975", max_length=20),
    q: Optional[str] = Query(None, max_length=200, description="Tìm theo tên/số hiệu/cơ quan"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> LegalDocumentListResponse:
    items, total = locality_data.list_legal_documents(
        locality_code, q=q, limit=limit, offset=offset
    )
    return LegalDocumentListResponse(
        items=items,
        total=total,
        locality_code=locality_code,
        q=q,
        limit=limit,
        offset=offset,
    )
